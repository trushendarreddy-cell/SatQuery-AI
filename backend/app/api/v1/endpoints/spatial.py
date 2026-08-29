from fastapi import APIRouter, status

from app.schemas.spatial_schema import (
    SpatialOverlapRequest,
    SpatialOverlapResult,
    AlignmentRequest,
    AlignmentResult,
    CompatibilityRequest,
    CompatibilityResult,
    ClipRequest,
    ClipResult,
)
from app.pipeline.overlap import check_spatial_overlap
from app.pipeline.alignment import align_images
from app.pipeline.compatibility import check_compatibility
from app.pipeline.clip import clip_to_common_extent

router = APIRouter()


@router.post(
    "/overlap",
    response_model=SpatialOverlapResult,
    status_code=status.HTTP_200_OK,
    summary="Compute spatial overlap & intersection polygon between two scenes",
    description=(
        "Calculates the geometric intersection polygon (GeoJSON in EPSG:4326), "
        "overlap percentage (IoU), and geodesic area in sq. km between two georeferenced GeoTIFFs."
    ),
)
async def get_spatial_overlap(payload: SpatialOverlapRequest):
    """Computes spatial overlap and intersection polygon for two images in a session."""
    return check_spatial_overlap(
        session_id=payload.session_id,
        image_id_1=payload.image_id_1,
        image_id_2=payload.image_id_2,
    )


@router.post(
    "/compatibility",
    response_model=CompatibilityResult,
    status_code=status.HTTP_200_OK,
    summary="Evaluate multi-factor compatibility between two scenes",
    description=(
        "Evaluates temporal intervals, spatial resolution ratio, CRS alignment, "
        "and spatial overlap to determine suitability for change detection/comparison."
    ),
)
async def get_compatibility(payload: CompatibilityRequest):
    """Evaluates multi-factor compatibility for two images in a session."""
    return check_compatibility(
        session_id=payload.session_id,
        image_id_1=payload.image_id_1,
        image_id_2=payload.image_id_2,
    )


@router.post(
    "/align",
    response_model=AlignmentResult,
    status_code=status.HTTP_200_OK,
    summary="Align & reproject target image onto reference raster grid",
    description=(
        "Warps and resamples target raster to match the reference raster's CRS, "
        "bounding extent, and pixel dimensions. Saves the aligned artifact in session cache."
    ),
)
async def align_spatial_rasters(payload: AlignmentRequest):
    """Aligns and reprojects target image onto reference grid within session."""
    return align_images(
        session_id=payload.session_id,
        reference_image_id=payload.reference_image_id,
        target_image_id=payload.target_image_id,
        resampling_method=payload.resampling_method or "bilinear",
    )


@router.post(
    "/clip",
    response_model=ClipResult,
    status_code=status.HTTP_200_OK,
    summary="Clip two rasters to their shared spatial extent",
    description=(
        "Warps both georeferenced GeoTIFFs onto a shared pixel grid covering their "
        "spatial intersection. Image 1 defines CRS and pixel alignment. Unreferenced "
        "visual images are rejected; no coordinates are invented."
    ),
)
async def clip_spatial_rasters(payload: ClipRequest):
    """Clips two session rasters to a common overlapping grid."""
    return clip_to_common_extent(
        session_id=payload.session_id,
        image_id_1=payload.image_id_1,
        image_id_2=payload.image_id_2,
        resampling_method=payload.resampling_method or "bilinear",
    )
