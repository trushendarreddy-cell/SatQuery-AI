from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.metadata_schema import UnifiedImageMetadata, BandSummary


class CloudMaskStatus(str, Enum):
    PERFORMED = "performed"
    NOT_PERFORMED = "not_performed"


class SeasonalRisk(str, Enum):
    NONE = "none"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    UNKNOWN = "unknown"


class CloudMaskRequest(BaseModel):
    session_id: str = Field(..., description="Active session ID")
    image_id: str = Field(..., description="Georeferenced image to mask")


class CloudMaskResult(BaseModel):
    success: bool = Field(..., description="True when a cloud/shadow mask was produced from QA/SCL evidence")
    status: CloudMaskStatus = Field(..., description="performed or not_performed")
    session_id: str = Field(..., description="Active session ID")
    image_id: str = Field(..., description="Source image ID")
    mask_image_id: str = Field("", description="Registered mask raster ID when produced")
    artifact_filename: str = Field("", description="Mask GeoTIFF filename")
    qa_band_index: Optional[int] = Field(None, description="1-based QA/SCL/cloud band used")
    qa_band_name: Optional[str] = Field(None, description="Detected QA/SCL/cloud band label")
    cloud_pixel_count: int = Field(0, description="Pixels classified as cloud")
    shadow_pixel_count: int = Field(0, description="Pixels classified as cloud shadow")
    clear_pixel_count: int = Field(0, description="Pixels classified as clear")
    cloud_fraction: float = Field(0.0, description="Cloud pixels / valid pixels")
    shadow_fraction: float = Field(0.0, description="Shadow pixels / valid pixels")
    message: str = Field(..., description="Status summary")
    messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    mask_metadata: Optional[UnifiedImageMetadata] = None


class SeasonalFilterRequest(BaseModel):
    session_id: str = Field(..., description="Active session ID")
    image_id_1: str = Field(..., description="Earlier or first scene ID")
    image_id_2: str = Field(..., description="Later or second scene ID")
    mask_image_id: Optional[str] = Field(None, description="Optional binary change-mask image ID")


class SeasonalFilterResult(BaseModel):
    success: bool = Field(..., description="True when temporal evidence could be evaluated")
    session_id: str = Field(..., description="Active session ID")
    image_id_1: str
    image_id_2: str
    mask_image_id: Optional[str] = None
    seasonal_risk: SeasonalRisk = Field(..., description="Phenological false-positive risk")
    same_phenological_window: Optional[bool] = Field(None, description="True when day-of-year offset is small")
    day_of_year_delta: Optional[int] = Field(None, description="Circular day-of-year separation")
    time_delta_days: Optional[float] = Field(None, description="Calendar separation in days")
    event_confirmed: bool = Field(False, description="True only with independent confirmation evidence (never inferred from season alone)")
    mask_modified: bool = Field(False, description="True only if pixels were removed using phenology evidence")
    filtered_mask_image_id: Optional[str] = None
    message: str
    messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class MaskToGeoJSONRequest(BaseModel):
    session_id: str = Field(..., description="Active session ID")
    image_id: str = Field(..., description="Binary/classified mask raster ID")
    band_index: int = Field(1, description="1-based band to polygonize")
    min_value: float = Field(1.0, description="Pixels >= this value are treated as valid mask")


class MaskToGeoJSONResult(BaseModel):
    success: bool
    session_id: str
    image_id: str
    feature_count: int = Field(..., description="Number of polygon features")
    geojson: Dict[str, Any] = Field(..., description="EPSG:4326 FeatureCollection")
    area_m2: float = Field(0.0)
    area_ha: float = Field(0.0)
    area_sqkm: float = Field(0.0)
    source_crs: str = Field("")
    message: str
    messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class AreaRequest(BaseModel):
    geojson: Dict[str, Any] = Field(..., description="GeoJSON Feature, FeatureCollection, Polygon, or MultiPolygon")


class AreaResult(BaseModel):
    success: bool
    feature_count: int = 0
    area_m2: float = 0.0
    area_ha: float = 0.0
    area_sqkm: float = 0.0
    message: str
    messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class ZonalStatsRequest(BaseModel):
    session_id: str
    image_id: str = Field(..., description="Raster to summarize")
    mask_image_id: Optional[str] = Field(None, description="Optional binary mask raster in the same session")
    geometry: Optional[Dict[str, Any]] = Field(None, description="Optional GeoJSON geometry/feature in EPSG:4326 or native CRS")
    band_index: Optional[int] = Field(None, description="If set, only this 1-based band is summarized")


class ZonalBandStats(BaseModel):
    band_index: int
    valid_pixel_count: int
    nodata_pixel_count: int
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    mean_value: Optional[float] = None
    std_value: Optional[float] = None
    sum_value: Optional[float] = None


class ZonalStatsResult(BaseModel):
    success: bool
    session_id: str
    image_id: str
    mask_image_id: Optional[str] = None
    used_geometry: bool = False
    used_mask: bool = False
    bands: List[ZonalBandStats] = Field(default_factory=list)
    message: str
    messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class SpectralIndexType(str, Enum):
    NDVI = "ndvi"


class SpectralIndexRequest(BaseModel):
    session_id: str = Field(..., description="Active session ID")
    image_id: str = Field(..., description="Multispectral GeoTIFF to process")
    index_type: SpectralIndexType = Field(SpectralIndexType.NDVI, description="Spectral index to compute")
    red_band: int = Field(3, description="1-based red band index")
    nir_band: int = Field(4, description="1-based NIR band index")


class SpectralIndexResult(BaseModel):
    success: bool = Field(..., description="True if the index raster was produced")
    session_id: str = Field(..., description="Active session ID")
    image_id: str = Field(..., description="Source image ID")
    index_type: str = Field(..., description="Index computed (e.g., ndvi)")
    index_image_id: str = Field(..., description="Registered index raster ID")
    artifact_filename: str = Field(..., description="Index raster GeoTIFF filename")
    width: int = Field(..., description="Pixel columns")
    height: int = Field(..., description="Pixel rows")
    band_count: int = Field(1, description="Number of bands in index raster")
    crs: str = Field(..., description="CRS of the index raster")
    transform: List[float] = Field(..., description="Affine transform coefficients [c, a, b, d, e, f]")
    red_band: int = Field(..., description="Red band index used")
    nir_band: int = Field(..., description="NIR band index used")
    valid_pixel_count: int = Field(..., description="Pixels with valid spectral data")
    nodata_pixel_count: int = Field(..., description="Pixels excluded as NoData")
    min_value: Optional[float] = Field(None, description="Minimum index value")
    max_value: Optional[float] = Field(None, description="Maximum index value")
    mean_value: Optional[float] = Field(None, description="Mean index value")
    message: str = Field(..., description="Status summary")
    messages: List[str] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    index_metadata: Optional[UnifiedImageMetadata] = Field(None, description="Metadata of the generated index raster")
