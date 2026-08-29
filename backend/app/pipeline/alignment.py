import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
import rasterio
from rasterio.warp import reproject, Resampling
from rasterio.errors import RasterioIOError

from app.core.session_cache import session_manager
from app.pipeline.metadata import UniversalMetadataExtractor
from app.schemas.metadata_schema import ImageCategory, UnifiedImageMetadata
from app.schemas.spatial_schema import AlignmentResult


class GridAlignmentEngine:
    """Warps and aligns a target satellite raster onto a reference raster's pixel grid and CRS."""

    RESAMPLING_MAP = {
        "nearest": Resampling.nearest,
        "bilinear": Resampling.bilinear,
        "cubic": Resampling.cubic,
        "lanczos": Resampling.lanczos,
        "average": Resampling.average,
        "mode": Resampling.mode,
    }

    @classmethod
    def align_rasters(
        cls,
        ref_path: Path,
        src_path: Path,
        output_path: Path,
        resampling_method: str = "bilinear",
    ) -> Dict[str, Any]:
        """
        Executes GDAL/Rasterio reprojection to match reference grid.
        
        Guarantees:
        - Output raster matches ref CRS, affine transform, width, and height.
        - Preserves spectral band count and data types.
        - Original files are never modified.
        """
        with rasterio.open(ref_path) as ref:
            if not ref.crs:
                raise ValueError("Both reference and target rasters must possess valid CRS metadata.")

            return cls.reproject_to_grid(
                src_path=src_path,
                output_path=output_path,
                dst_crs=ref.crs,
                dst_transform=ref.transform,
                width=ref.width,
                height=ref.height,
                resampling_method=resampling_method,
            )

    @classmethod
    def reproject_to_grid(
        cls,
        src_path: Path,
        output_path: Path,
        dst_crs,
        dst_transform,
        width: int,
        height: int,
        resampling_method: str = "bilinear",
    ) -> Dict[str, Any]:
        """Warps a source raster onto an explicit destination pixel grid without modifying the source."""
        if width < 1 or height < 1:
            raise ValueError("Destination grid must have positive width and height.")

        resamp = cls.RESAMPLING_MAP.get(resampling_method.lower(), Resampling.bilinear)

        with rasterio.open(src_path) as src:
            if not src.crs:
                raise ValueError("Source raster must possess valid CRS metadata.")

            profile = src.profile.copy()
            profile.update(
                crs=dst_crs,
                transform=dst_transform,
                width=width,
                height=height,
                driver="GTiff",
            )

            with rasterio.open(output_path, "w", **profile) as dst:
                for b in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, b),
                        destination=rasterio.band(dst, b),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        dst_transform=dst_transform,
                        dst_crs=dst_crs,
                        resampling=resamp,
                        src_nodata=src.nodatavals[b - 1],
                        dst_nodata=src.nodatavals[b - 1] or 0,
                    )

            return {
                "source_crs": src.crs.to_string(),
                "target_crs": dst_crs.to_string() if hasattr(dst_crs, "to_string") else str(dst_crs),
                "resolution": [float(abs(dst_transform.a)), float(abs(dst_transform.e))],
                "width": int(width),
                "height": int(height),
                "band_count": int(src.count),
                "dtype": str(src.dtypes[0]),
                "resampling": resampling_method,
            }


def align_images(
    session_id: str,
    reference_image_id: str,
    target_image_id: str,
    resampling_method: str = "bilinear",
) -> AlignmentResult:
    """
    Deterministic tool function to align and reproject target image onto reference grid.
    Callable by AI Agent, services, or API endpoints.
    """
    session = session_manager.get_session(session_id)
    if not session:
        return AlignmentResult(
            success=False,
            session_id=session_id,
            reference_image_id=reference_image_id,
            source_image_id=target_image_id,
            aligned_image_id="",
            artifact_filename="",
            source_crs="",
            target_crs="",
            resolution=[],
            width=0,
            height=0,
            band_count=0,
            dtype="",
            resampling=resampling_method,
            message=f"Session '{session_id}' not found.",
            aligned_metadata=None,
        )

    ref_meta = session.images.get(reference_image_id)
    src_meta = session.images.get(target_image_id)

    if not ref_meta:
        return AlignmentResult(
            success=False,
            session_id=session_id,
            reference_image_id=reference_image_id,
            source_image_id=target_image_id,
            aligned_image_id="",
            artifact_filename="",
            source_crs="",
            target_crs="",
            resolution=[],
            width=0,
            height=0,
            band_count=0,
            dtype="",
            resampling=resampling_method,
            message=f"Reference image '{reference_image_id}' not found in session.",
            aligned_metadata=None,
        )

    if not src_meta:
        return AlignmentResult(
            success=False,
            session_id=session_id,
            reference_image_id=reference_image_id,
            source_image_id=target_image_id,
            aligned_image_id="",
            artifact_filename="",
            source_crs="",
            target_crs="",
            resolution=[],
            width=0,
            height=0,
            band_count=0,
            dtype="",
            resampling=resampling_method,
            message=f"Target image '{target_image_id}' not found in session.",
            aligned_metadata=None,
        )

    # Validate georeferenced requirement
    if not ref_meta.has_geospatial_metadata or not ref_meta.geospatial:
        return AlignmentResult(
            success=False,
            session_id=session_id,
            reference_image_id=reference_image_id,
            source_image_id=target_image_id,
            aligned_image_id="",
            artifact_filename="",
            source_crs="",
            target_crs="",
            resolution=[],
            width=0,
            height=0,
            band_count=0,
            dtype="",
            resampling=resampling_method,
            message=f"Reference image '{ref_meta.filename}' lacks geospatial CRS. Cannot be used as grid reference.",
            aligned_metadata=None,
        )

    if not src_meta.has_geospatial_metadata or not src_meta.geospatial:
        return AlignmentResult(
            success=False,
            session_id=session_id,
            reference_image_id=reference_image_id,
            source_image_id=target_image_id,
            aligned_image_id="",
            artifact_filename="",
            source_crs="",
            target_crs="",
            resolution=[],
            width=0,
            height=0,
            band_count=0,
            dtype="",
            resampling=resampling_method,
            message=f"Target image '{src_meta.filename}' is an unreferenced visual image. Cannot reproject onto geospatial grid.",
            aligned_metadata=None,
        )

    ref_path = session_manager.get_image_file_path(session_id, reference_image_id)
    src_path = session_manager.get_image_file_path(session_id, target_image_id)

    if not ref_path or not ref_path.exists() or not src_path or not src_path.exists():
        return AlignmentResult(
            success=False,
            session_id=session_id,
            reference_image_id=reference_image_id,
            source_image_id=target_image_id,
            aligned_image_id="",
            artifact_filename="",
            source_crs="",
            target_crs="",
            resolution=[],
            width=0,
            height=0,
            band_count=0,
            dtype="",
            resampling=resampling_method,
            message="Underlying raster file paths could not be located on disk.",
            aligned_metadata=None,
        )

    aligned_uuid = uuid.uuid4().hex[:8]
    artifact_filename = f"aligned_{target_image_id}_to_{reference_image_id}_{aligned_uuid}.tif"
    output_aligned_path = session.session_dir / artifact_filename

    try:
        alignment_info = GridAlignmentEngine.align_rasters(
            ref_path=ref_path,
            src_path=src_path,
            output_path=output_aligned_path,
            resampling_method=resampling_method,
        )

        # Profile the newly generated aligned raster
        aligned_metadata = UniversalMetadataExtractor.extract(
            file_path=output_aligned_path,
            category=ImageCategory.GEOSPATIAL_GEOTIFF,
            image_id=aligned_uuid,
            compute_stats=True,
        )

        # Register aligned artifact in session
        session_manager.add_image(
            session_id=session_id,
            file_path=output_aligned_path,
            metadata=aligned_metadata,
        )

        return AlignmentResult(
            success=True,
            session_id=session_id,
            reference_image_id=reference_image_id,
            source_image_id=target_image_id,
            aligned_image_id=aligned_uuid,
            artifact_filename=artifact_filename,
            source_crs=alignment_info["source_crs"],
            target_crs=alignment_info["target_crs"],
            resolution=alignment_info["resolution"],
            width=alignment_info["width"],
            height=alignment_info["height"],
            band_count=alignment_info["band_count"],
            dtype=alignment_info["dtype"],
            resampling=alignment_info["resampling"],
            message=f"Target image successfully warped and aligned to reference grid ({alignment_info['target_crs']}, {alignment_info['width']}x{alignment_info['height']}).",
            aligned_metadata=aligned_metadata,
        )

    except Exception as exc:
        return AlignmentResult(
            success=False,
            session_id=session_id,
            reference_image_id=reference_image_id,
            source_image_id=target_image_id,
            aligned_image_id="",
            artifact_filename="",
            source_crs="",
            target_crs="",
            resolution=[],
            width=0,
            height=0,
            band_count=0,
            dtype="",
            resampling=resampling_method,
            message=f"Raster alignment failed: {str(exc)}",
            aligned_metadata=None,
        )
