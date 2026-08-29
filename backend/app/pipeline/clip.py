import uuid
from typing import Optional

import rasterio

from app.core.session_cache import session_manager
from app.geospatial.clip import compute_common_pixel_grid
from app.pipeline.alignment import GridAlignmentEngine
from app.pipeline.metadata import UniversalMetadataExtractor
from app.schemas.metadata_schema import ImageCategory, UnifiedImageMetadata
from app.schemas.spatial_schema import ClipResult


def _failed_clip(
    session_id: str,
    image_id_1: str,
    image_id_2: str,
    resampling_method: str,
    message: str,
    warnings: Optional[list] = None,
) -> ClipResult:
    return ClipResult(
        success=False,
        session_id=session_id,
        image_id_1=image_id_1,
        image_id_2=image_id_2,
        clipped_image_id_1="",
        clipped_image_id_2="",
        artifact_filename_1="",
        artifact_filename_2="",
        target_crs="",
        resolution=[],
        width=0,
        height=0,
        resampling=resampling_method,
        intersection_bounds=None,
        intersection_bounds_wgs84=None,
        clipped_metadata_1=None,
        clipped_metadata_2=None,
        message=message,
        messages=[],
        warnings=warnings or [],
    )


def clip_to_common_extent(
    session_id: str,
    image_id_1: str,
    image_id_2: str,
    resampling_method: str = "bilinear",
) -> ClipResult:
    """
    Warp both georeferenced rasters onto a shared pixel grid covering their overlap.

    Image 1 defines the destination CRS and pixel alignment. Visual/unreferenced
    images are rejected; no CRS or coordinates are invented.
    """
    session = session_manager.get_session(session_id)
    if not session:
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            f"Session '{session_id}' not found.",
        )

    meta1 = session.images.get(image_id_1)
    meta2 = session.images.get(image_id_2)

    if not meta1:
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            f"Image '{image_id_1}' not found in session '{session_id}'.",
        )
    if not meta2:
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            f"Image '{image_id_2}' not found in session '{session_id}'.",
        )

    if not meta1.has_geospatial_metadata or not meta1.geospatial:
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            f"Image '{meta1.filename}' is an unreferenced visual image. Cannot clip to a geospatial extent.",
            warnings=[f"Image '{meta1.filename}' (ID: {meta1.image_id}) lacks geospatial metadata."],
        )
    if not meta2.has_geospatial_metadata or not meta2.geospatial:
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            f"Image '{meta2.filename}' is an unreferenced visual image. Cannot clip to a geospatial extent.",
            warnings=[f"Image '{meta2.filename}' (ID: {meta2.image_id}) lacks geospatial metadata."],
        )

    path1 = session_manager.get_image_file_path(session_id, image_id_1)
    path2 = session_manager.get_image_file_path(session_id, image_id_2)
    if not path1 or not path1.exists() or not path2 or not path2.exists():
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            "Underlying raster file paths could not be located on disk.",
        )

    try:
        with rasterio.open(path1) as ref_ds, rasterio.open(path2) as src_ds:
            if not ref_ds.crs or not src_ds.crs:
                return _failed_clip(
                    session_id, image_id_1, image_id_2, resampling_method,
                    "Both rasters must possess valid CRS metadata.",
                )
            grid = compute_common_pixel_grid(ref_ds, src_ds)
            target_crs = ref_ds.crs
    except Exception as exc:
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            f"Failed to compute common spatial extent: {str(exc)}",
        )

    if grid is None:
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            "Scenes do not share a common spatial region; clipping produced an empty extent.",
            warnings=["No spatial overlap found between the selected scenes."],
        )

    clip_uuid = uuid.uuid4().hex[:8]
    artifact_1 = f"clipped_{image_id_1}_{clip_uuid}.tif"
    artifact_2 = f"clipped_{image_id_2}_{clip_uuid}.tif"
    out1 = session.session_dir / artifact_1
    out2 = session.session_dir / artifact_2

    try:
        info1 = GridAlignmentEngine.reproject_to_grid(
            src_path=path1,
            output_path=out1,
            dst_crs=target_crs,
            dst_transform=grid.transform,
            width=grid.width,
            height=grid.height,
            resampling_method=resampling_method,
        )
        info2 = GridAlignmentEngine.reproject_to_grid(
            src_path=path2,
            output_path=out2,
            dst_crs=target_crs,
            dst_transform=grid.transform,
            width=grid.width,
            height=grid.height,
            resampling_method=resampling_method,
        )

        id1 = uuid.uuid4().hex[:8]
        id2 = uuid.uuid4().hex[:8]
        clipped_meta_1 = UniversalMetadataExtractor.extract(
            file_path=out1,
            category=ImageCategory.GEOSPATIAL_GEOTIFF,
            image_id=id1,
            compute_stats=True,
        )
        clipped_meta_2 = UniversalMetadataExtractor.extract(
            file_path=out2,
            category=ImageCategory.GEOSPATIAL_GEOTIFF,
            image_id=id2,
            compute_stats=True,
        )
        session_manager.add_image(session_id, out1, clipped_meta_1)
        session_manager.add_image(session_id, out2, clipped_meta_2)

        crs_str = info1["target_crs"]
        return ClipResult(
            success=True,
            session_id=session_id,
            image_id_1=image_id_1,
            image_id_2=image_id_2,
            clipped_image_id_1=id1,
            clipped_image_id_2=id2,
            artifact_filename_1=artifact_1,
            artifact_filename_2=artifact_2,
            target_crs=crs_str,
            resolution=info1["resolution"],
            width=int(grid.width),
            height=int(grid.height),
            resampling=resampling_method,
            intersection_bounds=grid.bounds_native,
            intersection_bounds_wgs84=grid.bounds_wgs84,
            clipped_metadata_1=clipped_meta_1,
            clipped_metadata_2=clipped_meta_2,
            message=(
                f"Both rasters clipped to a shared {grid.width}x{grid.height} grid "
                f"in {crs_str}."
            ),
            messages=[
                f"Common extent uses image '{image_id_1}' CRS and pixel alignment.",
                f"Second raster bands preserved: {info2['band_count']}.",
            ],
            warnings=[],
        )
    except Exception as exc:
        for leftover in (out1, out2):
            if leftover.exists():
                try:
                    leftover.unlink()
                except OSError:
                    pass
        return _failed_clip(
            session_id, image_id_1, image_id_2, resampling_method,
            f"Common-extent clipping failed: {str(exc)}",
        )
