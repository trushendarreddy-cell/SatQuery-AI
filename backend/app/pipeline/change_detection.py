import uuid
from pathlib import Path
from typing import Optional
import numpy as np
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.errors import RasterioIOError

from app.core.session_cache import session_manager
from app.pipeline.clip import clip_to_common_extent
from app.pipeline.metadata import UniversalMetadataExtractor
from app.schemas.metadata_schema import ImageCategory
from app.schemas.change_detection_schema import (
    ChangeDetectionMethod,
    ChangeDetectionRequest,
    ChangeDetectionResult,
)


_RESAMPLING_MAP = {
    "nearest": Resampling.nearest,
    "bilinear": Resampling.bilinear,
    "cubic": Resampling.cubic,
    "lanczos": Resampling.lanczos,
    "average": Resampling.average,
    "mode": Resampling.mode,
}


def _failed_result(
    session_id: str,
    image_id_1: str,
    image_id_2: str,
    threshold: float,
    method: str,
    message: str,
    warnings: Optional[list] = None,
) -> ChangeDetectionResult:
    return ChangeDetectionResult(
        success=False,
        session_id=session_id,
        analysis_type="change_detection",
        image_id_1=image_id_1,
        image_id_2=image_id_2,
        change_mask_image_id="",
        artifact_filename="",
        width=0,
        height=0,
        band_count=1,
        crs="",
        transform=[0, 1, 0, 0, 0, 1],
        changed_pixel_count=0,
        valid_pixel_count=0,
        change_percentage=0.0,
        min_change=0.0,
        max_change=0.0,
        mean_change=0.0,
        threshold_used=threshold,
        threshold_method=method,
        message=message,
        messages=[],
        warnings=warnings or [],
    )


def _reject_visuals(
    meta1,
    meta2,
    session_id: str,
    image_id_1: str,
    image_id_2: str,
    threshold: float,
    method: str,
) -> Optional[ChangeDetectionResult]:
    if not meta1.has_geospatial_metadata or not meta1.geospatial:
        return _failed_result(
            session_id, image_id_1, image_id_2, threshold, method,
            f"Image '{meta1.filename}' is an unreferenced visual image. Change detection requires georeferenced rasters.",
            warnings=[f"Image '{meta1.filename}' (ID: {meta1.image_id}) lacks geospatial metadata."],
        )
    if not meta2.has_geospatial_metadata or not meta2.geospatial:
        return _failed_result(
            session_id, image_id_1, image_id_2, threshold, method,
            f"Image '{meta2.filename}' is an unreferenced visual image. Change detection requires georeferenced rasters.",
            warnings=[f"Image '{meta2.filename}' (ID: {meta2.image_id}) lacks geospatial metadata."],
        )
    return None


def run_change_detection(
    payload: ChangeDetectionRequest,
) -> ChangeDetectionResult:
    """
    Detects changes between two georeferenced rasters within a session.

    Workflow:
    1. Validates session and both images are present and georeferenced.
    2. Reuses clip_to_common_extent to align both scenes on a shared pixel grid.
    3. Reads aligned rasters, computes per-pixel difference.
    4. Applies thresholding (absolute or relative normalized).
    5. Writes a single-band change-mask GeoTIFF and registers it in session.
    6. Returns change statistics.
    """
    session_id = payload.session_id
    image_id_1 = payload.image_id_1
    image_id_2 = payload.image_id_2
    threshold = payload.threshold
    method = payload.threshold_method.value
    band_index = payload.band_index
    resampling_method = payload.resampling_method or "bilinear"

    session = session_manager.get_session(session_id)
    if not session:
        return _failed_result(
            session_id, image_id_1, image_id_2, threshold, method,
            f"Session '{session_id}' not found.",
        )

    meta1 = session.images.get(image_id_1)
    meta2 = session.images.get(image_id_2)
    if not meta1 or not meta2:
        missing = image_id_1 if not meta1 else image_id_2
        return _failed_result(
            session_id, image_id_1, image_id_2, threshold, method,
            f"Image '{missing}' not found in session '{session_id}'.",
        )

    visual_reject = _reject_visuals(meta1, meta2, session_id, image_id_1, image_id_2, threshold, method)
    if visual_reject:
        return visual_reject

    path1 = session_manager.get_image_file_path(session_id, image_id_1)
    path2 = session_manager.get_image_file_path(session_id, image_id_2)
    if not path1 or not path1.exists() or not path2 or not path2.exists():
        return _failed_result(
            session_id, image_id_1, image_id_2, threshold, method,
            "Underlying raster file paths could not be located on disk.",
        )

    clip_result = clip_to_common_extent(
        session_id=session_id,
        image_id_1=image_id_1,
        image_id_2=image_id_2,
        resampling_method=resampling_method,
    )
    if not clip_result.success:
        return _failed_result(
            session_id, image_id_1, image_id_2, threshold, method,
            clip_result.message,
            warnings=clip_result.warnings,
        )

    clipped_path1 = session.session_dir / clip_result.artifact_filename_1
    clipped_path2 = session.session_dir / clip_result.artifact_filename_2

    try:
        with rasterio.open(clipped_path1) as ref_ds, rasterio.open(clipped_path2) as src_ds:
            if ref_ds.count == 0 or src_ds.count == 0:
                return _failed_result(
                    session_id, image_id_1, image_id_2, threshold, method,
                    "One or both rasters have zero bands after clipping.",
                )

            band1 = min(band_index, ref_ds.count) if band_index else 1
            band2 = min(band_index, src_ds.count) if band_index else 1

            arr1 = ref_ds.read(band1).astype(np.float64)
            arr2 = src_ds.read(band2).astype(np.float64)

            nodata1 = ref_ds.nodata
            nodata2 = src_ds.nodata

            if nodata1 is not None:
                mask1 = arr1 != nodata1
            else:
                mask1 = np.ones(arr1.shape, dtype=bool)

            if nodata2 is not None:
                mask2 = arr2 != nodata2
            else:
                mask2 = np.ones(arr2.shape, dtype=bool)

            valid_mask = mask1 & mask2
            valid_pixels = int(valid_mask.sum())

            if valid_pixels == 0:
                return _failed_result(
                    session_id, image_id_1, image_id_2, threshold, method,
                    "No valid overlapping pixels found after masking NoData.",
                )

            diff = np.abs(arr1 - arr2)

            if payload.threshold_method == ChangeDetectionMethod.RELATIVE_NORMALIZED:
                range1 = np.nanmax(arr1[valid_mask]) - np.nanmin(arr1[valid_mask])
                range2 = np.nanmax(arr2[valid_mask]) - np.nanmin(arr2[valid_mask])
                denom = max(range1, range2)
                if denom == 0:
                    relative_diff = np.zeros_like(diff)
                else:
                    relative_diff = diff / denom
                change_mask = (relative_diff >= threshold) & valid_mask
                change_magnitudes = relative_diff[valid_mask]
            else:
                change_mask = (diff >= threshold) & valid_mask
                change_magnitudes = diff[valid_mask]

            changed_pixels = int(change_mask.sum())
            change_percentage = (changed_pixels / valid_pixels) * 100.0 if valid_pixels > 0 else 0.0

            min_change = float(np.min(change_magnitudes)) if change_magnitudes.size > 0 else 0.0
            max_change = float(np.max(change_magnitudes)) if change_magnitudes.size > 0 else 0.0
            mean_change = float(np.mean(change_magnitudes)) if change_magnitudes.size > 0 else 0.0

            mask_uint8 = change_mask.astype(np.uint8)

            mask_uuid = uuid.uuid4().hex[:8]
            mask_filename = f"change_mask_{image_id_1}_{image_id_2}_{mask_uuid}.tif"
            mask_path = session.session_dir / mask_filename

            profile = ref_ds.profile.copy()
            profile.update({
                "count": 1,
                "dtype": "uint8",
                "nodata": 0,
                "compress": "deflate",
                "tiled": False,
                "interleave": "pixel",
            })
            for key in ("blockxsize", "blockysize", "tiled"):
                profile.pop(key, None)

            with rasterio.open(mask_path, "w", **profile) as dst:
                dst.write(mask_uint8, 1)

            mask_meta = UniversalMetadataExtractor.extract(
                file_path=mask_path,
                category=ImageCategory.GEOSPATIAL_GEOTIFF,
                image_id=mask_uuid,
                compute_stats=False,
            )
            session_manager.add_image(session_id, mask_path, mask_meta)

            transform_list = [
                float(ref_ds.transform.c),
                float(ref_ds.transform.a),
                float(ref_ds.transform.b),
                float(ref_ds.transform.d),
                float(ref_ds.transform.e),
                float(ref_ds.transform.f),
            ]

            return ChangeDetectionResult(
                success=True,
                session_id=session_id,
                analysis_type="change_detection",
                image_id_1=image_id_1,
                image_id_2=image_id_2,
                change_mask_image_id=mask_uuid,
                artifact_filename=mask_filename,
                width=clip_result.width,
                height=clip_result.height,
                band_count=1,
                crs=clip_result.target_crs,
                transform=transform_list,
                changed_pixel_count=changed_pixels,
                valid_pixel_count=valid_pixels,
                change_percentage=round(change_percentage, 4),
                min_change=round(min_change, 6),
                max_change=round(max_change, 6),
                mean_change=round(mean_change, 6),
                threshold_used=threshold,
                threshold_method=method,
                message=f"Change detection completed. {changed_pixels} of {valid_pixels} valid pixels changed ({change_percentage:.2f}%).",
                messages=[
                    f"Both scenes aligned to a {clip_result.width}x{clip_result.height} grid.",
                    f"Threshold method: {method}, threshold: {threshold}.",
                    f"Change mask written to '{mask_filename}'.",
                ],
                warnings=[],
            )
    except Exception as exc:
        return _failed_result(
            session_id, image_id_1, image_id_2, threshold, method,
            f"Change detection failed: {str(exc)}",
        )
