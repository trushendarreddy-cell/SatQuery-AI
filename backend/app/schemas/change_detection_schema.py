from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class ChangeDetectionMethod(str, Enum):
    ABSOLUTE_DIFFERENCE = "absolute_difference"
    RELATIVE_NORMALIZED = "relative_normalized"


class ChangeDetectionRequest(BaseModel):
    session_id: str = Field(..., description="Active session ID")
    image_id_1: str = Field(..., description="First image identifier (reference)")
    image_id_2: str = Field(..., description="Second image identifier (target)")
    threshold: float = Field(0.1, description="Change detection threshold. For relative_normalized, values are in [0,1] range. Pixels >= threshold are classified as changed.")
    threshold_method: ChangeDetectionMethod = Field(ChangeDetectionMethod.RELATIVE_NORMALIZED, description="Algorithm: relative_normalized or absolute_difference")
    band_index: Optional[int] = Field(None, description="1-based band index to compare. If None, all common bands are aggregated.")
    resampling_method: str = Field("bilinear", description="Resampling method for alignment if needed")


class ChangeDetectionResult(BaseModel):
    success: bool = Field(..., description="True if change detection completed successfully")
    session_id: str = Field(..., description="Active session ID")
    analysis_type: str = Field("change_detection", description="Analysis type identifier")
    image_id_1: str = Field(..., description="First image ID")
    image_id_2: str = Field(..., description="Second image ID")
    change_mask_image_id: str = Field(..., description="Registered change mask raster ID")
    artifact_filename: str = Field(..., description="Change mask GeoTIFF filename")
    width: int = Field(..., description="Pixel columns of output mask")
    height: int = Field(..., description="Pixel rows of output mask")
    band_count: int = Field(1, description="Number of bands in change mask (always 1)")
    crs: str = Field(..., description="CRS of the change mask raster")
    transform: List[float] = Field(..., description="Affine transform coefficients [a, b, c, d, e, f]")
    changed_pixel_count: int = Field(..., description="Number of pixels classified as changed")
    valid_pixel_count: int = Field(..., description="Number of valid overlapping pixels")
    change_percentage: float = Field(..., description="Percentage of valid pixels that changed")
    min_change: float = Field(..., description="Minimum change magnitude among valid pixels")
    max_change: float = Field(..., description="Maximum change magnitude among valid pixels")
    mean_change: float = Field(..., description="Mean change magnitude over valid pixels")
    threshold_used: float = Field(..., description="Threshold value applied")
    threshold_method: str = Field(..., description="Thresholding method used")
    message: str = Field(..., description="Status summary")
    messages: List[str] = Field(default_factory=list, description="Informational messages")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
