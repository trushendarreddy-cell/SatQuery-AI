from fastapi import APIRouter, status

from app.schemas.change_detection_schema import (
    ChangeDetectionRequest,
    ChangeDetectionResult,
)
from app.pipeline.change_detection import run_change_detection

router = APIRouter()


@router.post(
    "/change-detection",
    response_model=ChangeDetectionResult,
    status_code=status.HTTP_200_OK,
    summary="Detect changes between two georeferenced rasters",
    description=(
        "Aligns two georeferenced GeoTIFFs to a common pixel grid and computes a change mask "
        "using absolute difference or relative normalized thresholding. Visual/JPG/PNG images "
        "are rejected. Returns a single-band change-mask raster registered in the session cache, "
        "plus changed-pixel statistics."
    ),
)
async def api_change_detection(payload: ChangeDetectionRequest):
    """Runs pixel-level change detection between two session rasters and returns a change mask raster."""
    return run_change_detection(payload)
