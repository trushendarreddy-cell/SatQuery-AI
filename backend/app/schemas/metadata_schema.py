from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field


class ImageCategory(str, Enum):
    """Broad classification of the incoming image format."""
    VISUAL_STANDARD = "visual_standard"        # Standard photos: JPG, PNG, BMP (No CRS)
    GEOSPATIAL_GEOTIFF = "geospatial_geotiff"  # Remote sensing: GeoTIFF, COG (With CRS & Geotransform)


class SensorModality(str, Enum):
    """Evidence-based modality classification derived from band count and metadata."""
    OPTICAL_RGB = "optical_rgb"                      # 3-channel georeferenced satellite optical RGB
    OPTICAL_MULTISPECTRAL = "optical_multispectral"  # 4+ bands (e.g. RGB + NIR + RedEdge + SWIR)
    SAR_RADAR = "sar_radar"                          # Synthetic Aperture Radar (identified via tags or polarization)
    GRAYSCALE_SINGLE_BAND = "grayscale_single_band"  # 1-channel grayscale / DEM / single band
    VISUAL_STANDARD = "visual_standard"              # Standard unreferenced photographic image (JPG/PNG)
    UNKNOWN = "unknown"                              # Unclassified modality


class BoundingBoxNative(BaseModel):
    """Bounding box in the raster's native coordinate reference system."""
    min_x: float = Field(..., description="Westernmost/left coordinate in native CRS")
    min_y: float = Field(..., description="Southernmost/bottom coordinate in native CRS")
    max_x: float = Field(..., description="Easternmost/right coordinate in native CRS")
    max_y: float = Field(..., description="Northernmost/top coordinate in native CRS")


class BoundingBoxWGS84(BaseModel):
    """Bounding box converted to standard WGS84 (EPSG:4326) Lat/Lon for map display."""
    min_lon: float = Field(..., description="Minimum Longitude in degrees")
    min_lat: float = Field(..., description="Minimum Latitude in degrees")
    max_lon: float = Field(..., description="Maximum Longitude in degrees")
    max_lat: float = Field(..., description="Maximum Latitude in degrees")


class Resolution(BaseModel):
    """Spatial resolution (pixel size / ground sampling distance)."""
    x_resolution: float = Field(..., description="Pixel width in native units (often meters or degrees)")
    y_resolution: float = Field(..., description="Pixel height in native units")
    unit: str = Field(..., description="Unit of measurement (e.g. 'metre', 'degree')")


class BandSummary(BaseModel):
    """Summary of an individual spectral band in a GeoTIFF."""
    band_index: int = Field(..., description="1-based band index")
    data_type: str = Field(..., description="Data type of the band (e.g., uint16, float32)")
    nodata_value: Optional[float] = Field(None, description="NoData pixel value if specified")
    min_value: Optional[float] = Field(None, description="Minimum pixel value")
    max_value: Optional[float] = Field(None, description="Maximum pixel value")
    mean_value: Optional[float] = Field(None, description="Mean pixel value")


class GeospatialProfile(BaseModel):
    """Detailed geospatial profile. Populated ONLY for GeoTIFF/COG with valid CRS."""
    crs: str = Field(..., description="Coordinate Reference System string (e.g. EPSG:4326, EPSG:32643)")
    is_projected: bool = Field(..., description="True if CRS is projected (e.g. UTM), False if geographic")
    bounds_native: BoundingBoxNative = Field(..., description="Bounding box in native coordinates")
    bounds_wgs84: Optional[BoundingBoxWGS84] = Field(None, description="Bounding box in WGS84 Lat/Lon")
    resolution: Resolution = Field(..., description="Ground sampling distance per pixel")
    bands: List[BandSummary] = Field(default_factory=list, description="Per-band spectral summary")
    acquisition_date: Optional[str] = Field(None, description="Acquisition date/timestamp if available in metadata")


class VisualProfile(BaseModel):
    """Visual profile for standard photographic images (JPG/PNG)."""
    color_mode: str = Field(..., description="Pillow color mode, e.g. 'RGB', 'RGBA', 'L'")
    channel_count: int = Field(..., description="Number of color channels")
    bit_depth: Optional[int] = Field(None, description="Bit depth per channel if detected")


class UnifiedImageMetadata(BaseModel):
    """Unified metadata model supporting both visual images and georeferenced rasters."""
    image_id: str = Field(..., description="Unique identifier for the image within session")
    filename: str = Field(..., description="Original filename")
    format: str = Field(..., description="Detected image format (e.g. 'JPEG', 'PNG', 'GTiff')")
    category: ImageCategory = Field(..., description="Broad category: visual_standard vs geospatial_geotiff")
    modality: SensorModality = Field(..., description="Evidence-based sensor modality")
    has_geospatial_metadata: bool = Field(..., description="Explicit flag: True for GeoTIFF with CRS, False for JPG/PNG")
    width: int = Field(..., description="Image width in pixels")
    height: int = Field(..., description="Image height in pixels")
    channels: int = Field(..., description="Total channel/band count")
    file_size_bytes: int = Field(..., description="File size on disk in bytes")
    acquisition_date: Optional[str] = Field(None, description="Acquisition timestamp if present in metadata")
    geospatial: Optional[GeospatialProfile] = Field(None, description="Geospatial metadata (None for JPG/PNG)")
    visual: Optional[VisualProfile] = Field(None, description="Visual color metadata (None for GeoTIFF)")


class ValidationResult(BaseModel):
    """Validation report returned by the validator."""
    is_valid: bool = Field(..., description="True if the file is readable and structurally valid")
    category: ImageCategory = Field(..., description="Detected image category")
    errors: List[str] = Field(default_factory=list, description="List of validation error messages if any")
    warnings: List[str] = Field(default_factory=list, description="List of non-blocking warning messages")


class InspectResponse(BaseModel):
    """Standard API response for the /inspect endpoint."""
    success: bool = Field(..., description="Indicates whether the inspection succeeded")
    message: str = Field(..., description="Status or summary message")
    validation: ValidationResult = Field(..., description="Validation outcome")
    metadata: Optional[UnifiedImageMetadata] = Field(None, description="Extracted unified metadata if valid")
