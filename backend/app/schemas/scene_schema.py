from enum import Enum
from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

from app.schemas.metadata_schema import UnifiedImageMetadata, SensorModality, ImageCategory


class SceneConfiguration(str, Enum):
    """Categorization of how images in the current session relate to one another."""
    SINGLE_IMAGE = "single_image"                          # Exactly 1 image uploaded
    BI_TEMPORAL_PAIR = "bi_temporal_pair"                  # 2 georeferenced scenes representing different dates
    OPTICAL_SAR_PAIR = "optical_sar_pair"                  # 1 Optical + 1 SAR Radar scene
    VISUAL_PAIR_UNREFERENCED = "visual_pair_unreferenced"  # 2 standard photos (JPG/PNG) with unverified relationship
    MULTI_IMAGE = "multi_image"                            # 3+ images of homogeneous or multi-date nature
    HETEROGENEOUS_COLLECTION = "heterogeneous_collection"  # Mixed set (e.g. 1 GeoTIFF + 1 JPG)
    UNKNOWN = "unknown"                                    # Empty or inconclusive relationship


class TemporalRelationship(BaseModel):
    """Temporal sequence and interval information derived from metadata."""
    has_temporal_information: bool = Field(..., description="True if acquisition timestamps were found")
    earlier_image_id: Optional[str] = Field(None, description="Image ID with earlier timestamp (T1)")
    later_image_id: Optional[str] = Field(None, description="Image ID with later timestamp (T2)")
    time_delta_days: Optional[float] = Field(None, description="Time interval between T1 and T2 in days")
    timestamps: Dict[str, Optional[str]] = Field(default_factory=dict, description="Map of image_id -> timestamp string")


class ModalityRelationship(BaseModel):
    """Sensor modalities present across the session."""
    is_multimodal: bool = Field(..., description="True if multiple distinct modalities are present (e.g. Optical + SAR)")
    optical_image_ids: List[str] = Field(default_factory=list, description="IDs of optical/multispectral images")
    sar_image_ids: List[str] = Field(default_factory=list, description="IDs of SAR radar images")
    visual_image_ids: List[str] = Field(default_factory=list, description="IDs of standard unreferenced visual images")


class SpatialCompatibilityOverview(BaseModel):
    """Initial spatial consistency assessment across georeferenced rasters."""
    all_georeferenced: bool = Field(..., description="True if all images in session have CRS and spatial coordinates")
    shared_crs: Optional[bool] = Field(None, description="True if all georeferenced images share the exact same CRS")
    crs_list: List[Optional[str]] = Field(default_factory=list, description="List of CRS strings for each image")
    resolution_ratio: Optional[float] = Field(None, description="Ratio of largest to smallest pixel resolution")
    notes: List[str] = Field(default_factory=list, description="Observational notes on spatial alignment requirements")


class SceneClassificationResult(BaseModel):
    """Evidence-based relationship classification report for the session."""
    session_id: str = Field(..., description="Unique session identifier")
    scene_config: SceneConfiguration = Field(..., description="Identified scene configuration")
    image_count: int = Field(..., description="Number of images in the session")
    image_ids: List[str] = Field(default_factory=list, description="Ordered list of image IDs")
    images: List[UnifiedImageMetadata] = Field(default_factory=list, description="Metadata for each image in session")
    temporal_relationship: Optional[TemporalRelationship] = Field(None, description="Temporal relationship details")
    modality_relationship: ModalityRelationship = Field(..., description="Modality breakdown")
    spatial_overview: SpatialCompatibilityOverview = Field(..., description="Spatial compatibility summary")
    confidence: str = Field(..., description="Confidence level: 'high', 'medium', 'low', or 'unverified'")
    messages: List[str] = Field(default_factory=list, description="Informational summary messages")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings or ambiguities detected")


class SessionStateResponse(BaseModel):
    """Full session state returned to clients."""
    session_id: str = Field(..., description="Session identifier")
    created_at: str = Field(..., description="Session creation ISO timestamp")
    updated_at: str = Field(..., description="Session last updated ISO timestamp")
    image_count: int = Field(..., description="Total active images in session")
    classification: SceneClassificationResult = Field(..., description="Scene classification result")
