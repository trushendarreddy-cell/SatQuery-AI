from enum import Enum
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
from app.schemas.metadata_schema import UnifiedImageMetadata


class OverlapStatus(str, Enum):
    """Categorical spatial relationship between two image footprints."""
    UNKNOWN = "UNKNOWN"
    NO_OVERLAP = "NO_OVERLAP"
    PARTIAL_OVERLAP = "PARTIAL_OVERLAP"
    FULL_OVERLAP = "FULL_OVERLAP"


class ResolutionCompatibilityStatus(str, Enum):
    """How two raster resolutions can be compared."""
    DIRECTLY_COMPATIBLE = "directly_compatible"
    COMPATIBLE_AFTER_RESAMPLING = "compatible_after_resampling"
    INCOMPATIBLE = "incompatible"
    UNKNOWN = "unknown"


class SpatialOverlapRequest(BaseModel):
    """Request to compute spatial overlap between two images in a session."""
    session_id: str = Field(..., description="Active session ID")
    image_id_1: str = Field(..., description="ID of the first image (reference)")
    image_id_2: str = Field(..., description="ID of the second image")


class SpatialOverlapResult(BaseModel):
    """Result of geometric intersection and spatial overlap calculation."""
    status: OverlapStatus = Field(OverlapStatus.UNKNOWN, description="UNKNOWN, NO_OVERLAP, PARTIAL_OVERLAP, or FULL_OVERLAP")
    intersects: Optional[bool] = Field(None, description="True/False for known geospatial comparison, null when unavailable")
    overlap_exists: bool = Field(..., description="True if scenes geographically intersect")
    overlap_percentage: float = Field(..., description="Intersection over Union (IoU) percentage")
    overlap_percentage_image_1: float = Field(..., description="Intersection area as % of image 1 area")
    overlap_percentage_image_2: float = Field(..., description="Intersection area as % of image 2 area")
    intersection_geojson: Optional[Dict[str, Any]] = Field(None, description="GeoJSON Polygon geometry of overlap in EPSG:4326")
    intersection_bounds: Optional[Dict[str, float]] = Field(None, description="Intersection bounds in the comparison CRS; currently EPSG:4326 lon/lat")
    intersection_bounds_wgs84: Optional[Dict[str, float]] = Field(None, description="Bounding coordinates of intersection in WGS84")
    intersection_area_sqkm: Optional[float] = Field(None, description="Approximate geodesic intersection area in sq. km")
    messages: List[str] = Field(default_factory=list, description="Descriptive status messages")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings if any")


class CRSAnalysis(BaseModel):
    """CRS compatibility and reprojection planning result."""
    crs_compatible: bool = Field(..., description="True if both CRS definitions can be used in a common comparison CRS")
    same_crs: Optional[bool] = Field(None, description="True when both CRS definitions are identical")
    source_crs_a: Optional[str] = Field(None, description="CRS of image A")
    source_crs_b: Optional[str] = Field(None, description="CRS of image B")
    target_crs: Optional[str] = Field(None, description="Preferred CRS for comparison/alignment")
    reprojection_required: bool = Field(..., description="True when at least one image must be reprojected")
    transformable: bool = Field(..., description="True when pyproj can parse both CRS definitions")
    transformation_required: Optional[str] = Field(None, description="Human-readable transformation plan")
    warnings: List[str] = Field(default_factory=list, description="CRS warnings")


class AlignmentRequest(BaseModel):
    """Request to align and reproject a target image onto a reference image's grid."""
    session_id: str = Field(..., description="Active session ID")
    reference_image_id: str = Field(..., description="ID of the image defining the target grid/CRS")
    target_image_id: str = Field(..., description="ID of the image to warp and align")
    resampling_method: Optional[str] = Field("bilinear", description="Resampling method: 'nearest', 'bilinear', 'cubic', 'lanczos'")


class AlignmentResult(BaseModel):
    """Result of CRS alignment and pixel grid reprojection."""
    success: bool = Field(..., description="True if alignment and warping succeeded")
    session_id: str = Field(..., description="Active session ID")
    reference_image_id: str = Field(..., description="Reference image ID")
    source_image_id: str = Field(..., description="Original target image ID before alignment")
    aligned_image_id: str = Field(..., description="New artifact ID representing the aligned raster")
    artifact_filename: str = Field(..., description="Safe filename of the aligned raster artifact")
    source_crs: str = Field(..., description="Original CRS of the target image")
    target_crs: str = Field(..., description="Target CRS matching the reference grid")
    resolution: List[float] = Field(..., description="[x_resolution, y_resolution] in target units")
    width: int = Field(..., description="Pixel columns of aligned raster (matching reference)")
    height: int = Field(..., description="Pixel rows of aligned raster (matching reference)")
    band_count: int = Field(..., description="Number of spectral bands in aligned raster")
    dtype: str = Field(..., description="Pixel data type of aligned raster")
    resampling: str = Field(..., description="Resampling algorithm used")
    message: str = Field(..., description="Status summary message")
    aligned_metadata: Optional[UnifiedImageMetadata] = Field(None, description="Full metadata of the newly registered aligned raster")


class TemporalCompatibility(BaseModel):
    """Temporal comparison breakdown."""
    has_dates: bool = Field(..., description="True if both images have valid acquisition dates")
    time_delta_days: Optional[float] = Field(None, description="Time difference in days")
    earlier_image_id: Optional[str] = Field(None, description="ID of the earlier scene")
    later_image_id: Optional[str] = Field(None, description="ID of the later scene")
    timestamps: Dict[str, Optional[str]] = Field(default_factory=dict, description="Image ID to timestamp map")


class ResolutionCompatibility(BaseModel):
    """Spatial resolution comparison breakdown."""
    image_1_resolution: List[float] = Field(..., description="Pixel resolution of image 1")
    image_2_resolution: List[float] = Field(..., description="Pixel resolution of image 2")
    ratio: float = Field(..., description="Ratio of maximum to minimum resolution")
    unit: str = Field(..., description="Unit of measurement ('metre', 'degree')")
    compatible: bool = Field(..., description="True if resolution ratio is within operable threshold")
    level: str = Field(..., description="Compatibility level: 'high', 'medium', or 'low'")
    status: ResolutionCompatibilityStatus = Field(
        ResolutionCompatibilityStatus.UNKNOWN,
        description="directly_compatible, compatible_after_resampling, incompatible, or unknown",
    )
    requires_resampling: bool = Field(False, description="True when comparison should resample one raster")


class CRSCompatibility(BaseModel):
    """CRS comparison breakdown."""
    same_crs: bool = Field(..., description="True if both rasters share identical CRS")
    image_1_crs: str = Field(..., description="CRS of image 1")
    image_2_crs: str = Field(..., description="CRS of image 2")
    reprojection_required: bool = Field(..., description="True if alignment/warping is needed")
    crs_compatible: bool = Field(True, description="True if CRS values are parseable/transformable")
    target_crs: Optional[str] = Field(None, description="Preferred target CRS for comparison")


class SpatialOverlapOverview(BaseModel):
    """Spatial overlap summary for compatibility."""
    status: OverlapStatus = Field(OverlapStatus.UNKNOWN, description="UNKNOWN, NO_OVERLAP, PARTIAL_OVERLAP, or FULL_OVERLAP")
    intersects: Optional[bool] = Field(None, description="True/False for known geospatial comparison, null when unavailable")
    overlap_exists: bool = Field(..., description="True if images geographically intersect")
    overlap_percentage: float = Field(..., description="Overlap percentage")
    intersection_bounds: Optional[Dict[str, float]] = Field(None, description="Intersection bounds in WGS84")
    intersection_area_sqkm: Optional[float] = Field(None, description="Intersection area in sq. km")


class GridAlignmentOverview(BaseModel):
    """Grid alignment summary."""
    is_aligned: bool = Field(..., description="True if grids and dimensions are already identical")
    same_dimensions: bool = Field(..., description="True if width and height match")
    same_transform: bool = Field(..., description="True if affine transforms match")


class CompatibilityRequest(BaseModel):
    """Request to assess compatibility between two images."""
    session_id: str = Field(..., description="Active session ID")
    image_id_1: str = Field(..., description="First image ID")
    image_id_2: str = Field(..., description="Second image ID")


class CompatibilityResult(BaseModel):
    """Comprehensive multi-factor compatibility evaluation."""
    compatible: bool = Field(..., description="Overall compatibility for change detection/comparison")
    session_id: str = Field(..., description="Active session ID")
    image_id_1: str = Field(..., description="First image ID")
    image_id_2: str = Field(..., description="Second image ID")
    temporal: TemporalCompatibility = Field(..., description="Temporal comparison")
    resolution: ResolutionCompatibility = Field(..., description="Resolution comparison")
    crs: CRSCompatibility = Field(..., description="CRS comparison")
    spatial: SpatialOverlapOverview = Field(..., description="Spatial overlap summary")
    grid: GridAlignmentOverview = Field(..., description="Grid alignment summary")
    recommendations: List[str] = Field(default_factory=list, description="Step-by-step processing recommendations")
    messages: List[str] = Field(default_factory=list, description="Informational messages")
    warnings: List[str] = Field(default_factory=list, description="Warnings regarding comparison caveats")


class CompatibilityAnalysisRequest(BaseModel):
    """Request for explicit pair compatibility analysis using images already in a session."""
    session_id: str = Field(..., description="Active session ID")
    image_a_id: str = Field(..., description="First image ID")
    image_b_id: str = Field(..., description="Second image ID")


class TemporalAnalysis(BaseModel):
    """Frontend/agent oriented temporal compatibility result."""
    available: bool = Field(..., description="True if both images have parseable acquisition timestamps")
    image_a_acquisition_date: Optional[str] = Field(None, description="Raw acquisition date from image A metadata")
    image_b_acquisition_date: Optional[str] = Field(None, description="Raw acquisition date from image B metadata")
    earlier_image_id: Optional[str] = Field(None, description="Earlier image ID when available")
    later_image_id: Optional[str] = Field(None, description="Later image ID when available")
    time_delta_days: Optional[float] = Field(None, description="Temporal separation in days")


class ResolutionAnalysis(BaseModel):
    """Frontend/agent oriented resolution compatibility result."""
    resolution_a: Optional[List[float]] = Field(None, description="[x_resolution, y_resolution] for image A")
    resolution_b: Optional[List[float]] = Field(None, description="[x_resolution, y_resolution] for image B")
    resolution_ratio: Optional[float] = Field(None, description="Largest mean pixel size divided by smallest")
    compatible: bool = Field(..., description="True if the images can be compared directly or after resampling")
    status: ResolutionCompatibilityStatus = Field(..., description="Compatibility category")
    requires_resampling: bool = Field(..., description="True if resolutions differ enough to require resampling")
    unit: Optional[str] = Field(None, description="Resolution unit")


class CompatibilityAnalysisResult(BaseModel):
    """Explicit two-image compatibility report for frontend and AI-agent use."""
    session_id: str = Field(..., description="Active session ID")
    image_a: str = Field(..., description="Image A ID")
    image_b: str = Field(..., description="Image B ID")
    temporal_relationship: TemporalAnalysis = Field(..., description="Temporal comparison")
    crs_analysis: CRSAnalysis = Field(..., description="CRS compatibility and reprojection plan")
    spatial_overlap: SpatialOverlapResult = Field(..., description="Spatial overlap report")
    resolution_analysis: ResolutionAnalysis = Field(..., description="Resolution compatibility")
    grid_alignment: GridAlignmentOverview = Field(..., description="Current pixel-grid alignment state")
    overall_compatibility: bool = Field(..., description="True if scenes can be compared directly or after required preprocessing")
    messages: List[str] = Field(default_factory=list, description="Human-readable status messages")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")


class ClipRequest(BaseModel):
    """Request to clip two georeferenced rasters to their shared spatial extent."""
    session_id: str = Field(..., description="Active session ID")
    image_id_1: str = Field(..., description="Reference image ID (defines CRS and pixel alignment)")
    image_id_2: str = Field(..., description="Second image ID to clip onto the shared grid")
    resampling_method: Optional[str] = Field("bilinear", description="Resampling method: 'nearest', 'bilinear', 'cubic', 'lanczos'")


class ClipResult(BaseModel):
    """Result of clipping two rasters onto a common overlapping pixel grid."""
    success: bool = Field(..., description="True if both clipped artifacts were created")
    session_id: str = Field(..., description="Active session ID")
    image_id_1: str = Field(..., description="First source image ID")
    image_id_2: str = Field(..., description="Second source image ID")
    clipped_image_id_1: str = Field(..., description="Registered artifact ID for clipped image 1")
    clipped_image_id_2: str = Field(..., description="Registered artifact ID for clipped image 2")
    artifact_filename_1: str = Field(..., description="Filename of clipped raster 1")
    artifact_filename_2: str = Field(..., description="Filename of clipped raster 2")
    target_crs: str = Field(..., description="CRS of the shared output grid")
    resolution: List[float] = Field(..., description="[x_resolution, y_resolution] in target units")
    width: int = Field(..., description="Pixel columns of the shared clipped grid")
    height: int = Field(..., description="Pixel rows of the shared clipped grid")
    resampling: str = Field(..., description="Resampling algorithm used")
    intersection_bounds: Optional[Dict[str, float]] = Field(None, description="Intersection bounds in the reference CRS")
    intersection_bounds_wgs84: Optional[Dict[str, float]] = Field(None, description="Intersection bounds in EPSG:4326")
    clipped_metadata_1: Optional[UnifiedImageMetadata] = Field(None, description="Metadata of clipped raster 1")
    clipped_metadata_2: Optional[UnifiedImageMetadata] = Field(None, description="Metadata of clipped raster 2")
    message: str = Field(..., description="Status summary")
    messages: List[str] = Field(default_factory=list, description="Informational messages")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
