"""Agent integration schemas for Master Agent contract (M15).

This module defines the stable data contracts between the SatQuery backend
and the team's external Master Agent. The backend exposes these schemas;
the Master Agent consumes them without needing to parse raw API responses.

Key principle: Backend owns infrastructure/storage/GIS; Master Agent owns
intelligence/orchestration/routing.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ImageModality(str, Enum):
    """Supported image modalities."""
    OPTICAL = "optical"
    SAR = "sar"
    THERMAL = "thermal"
    MULTISPECTRAL = "multispectral"
    HYPERSPECTRAL = "hyperspectral"
    RGB = "rgb"
    UNKNOWN = "unknown"


class ImageContextData(BaseModel):
    """Stable reference to a single image in a session."""
    image_id: str = Field(..., description="Unique image identifier")
    filename: str = Field(..., description="Original filename")
    storage_key: str = Field(..., description="Safe storage reference (no traversal)")
    modality: ImageModality = Field(..., description="Image type")
    timestamp: Optional[str] = Field(None, description="Acquisition timestamp if available")
    crs: Optional[str] = Field(None, description="Coordinate reference system (EPSG code)")
    width: Optional[int] = Field(None, description="Width in pixels")
    height: Optional[int] = Field(None, description="Height in pixels")
    band_count: Optional[int] = Field(None, description="Number of bands")
    bounds_wgs84: Optional[Dict[str, float]] = Field(None, description="WGS84 bounds {minx, miny, maxx, maxy}")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Full metadata from image")


class SpatialContextData(BaseModel):
    """Spatial compatibility information for the session's images."""
    common_crs: Optional[str] = Field(None, description="CRS all images share or can be aligned to")
    bounds_intersection: Optional[Dict[str, float]] = Field(None, description="Intersection of all image bounds")
    all_georeferenced: bool = Field(False, description="True if all images have CRS and geotransform")
    compatible_for_temporal: bool = Field(False, description="True if images can be compared temporally")
    image_pairs_compatible: List[tuple] = Field(default_factory=list, description="Compatible image pairs")


class ArtifactReferenceData(BaseModel):
    """Safe reference to a generated artifact."""
    artifact_id: str = Field(..., description="Unique artifact identifier")
    analysis_id: Optional[str] = Field(None, description="Analysis that generated this artifact")
    artifact_type: str = Field(..., description="Type (e.g., ndvi_raster, change_mask, geojson)")
    filename: str = Field(..., description="Artifact filename")
    storage_key: str = Field(..., description="Safe storage reference")
    mime_type: str = Field("application/octet-stream", description="MIME type")
    file_size: int = Field(0, description="File size in bytes")
    checksum: Optional[str] = Field(None, description="SHA256 checksum for integrity")


class AgentContextData(BaseModel):
    """Complete session context exposed to Master Agent.
    
    This is the primary contract. The Master Agent requests this once per session
    and uses it to:
    1. Understand what images are available
    2. Know spatial compatibility
    3. Decide which tools to invoke
    4. Know where to find artifacts
    
    The backend never changes this schema without explicit discussion with team.
    """
    session_id: str = Field(..., description="Session identifier")
    created_at: str = Field(..., description="ISO8601 session creation timestamp")
    image_count: int = Field(..., description="Number of images in session")
    images: List[ImageContextData] = Field(default_factory=list, description="All images in session")
    modalities: List[ImageModality] = Field(default_factory=list, description="Unique modalities present")
    timestamps: List[str] = Field(default_factory=list, description="Unique timestamps")
    spatial_context: SpatialContextData = Field(..., description="Spatial compatibility")
    artifacts: List[ArtifactReferenceData] = Field(default_factory=list, description="Generated artifacts")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Session-level metadata")


class EvidenceData(BaseModel):
    """Standardized evidence item for grounding.
    
    Every finding in a report must reference evidence. Evidence types:
    - computed: Comes from deterministic backend algorithm
    - visual: Comes from vision service or human observation
    - metadata: Comes from image metadata
    - inference: Comes from LLM or reasoning (explicitly marked)
    """
    evidence_id: str = Field(..., description="Unique evidence identifier")
    evidence_type: str = Field(..., description="computed, visual, metadata, or inference")
    source: str = Field(..., description="Tool or service that produced this evidence")
    value: Any = Field(None, description="The evidence value")
    unit: Optional[str] = Field(None, description="Unit for numeric values")
    confidence: Optional[float] = Field(None, description="Confidence (0.0-1.0) if applicable")
    artifact_id: Optional[str] = Field(None, description="Reference to supporting artifact")
    explanation: Optional[str] = Field(None, description="How this evidence was derived")


class QuantitativeResultData(BaseModel):
    """Numeric result from analysis."""
    metric: str = Field(..., description="Metric name (e.g., mean_ndvi, change_area_m2)")
    value: float = Field(..., description="Numeric value")
    unit: Optional[str] = Field(None, description="Unit (ha, m2, pixels, etc.)")
    evidence_ids: List[str] = Field(default_factory=list, description="Supporting evidence IDs")


class FindingData(BaseModel):
    """Single finding in a report, must be grounded in evidence."""
    text: str = Field(..., description="Human-readable finding")
    evidence_ids: List[str] = Field(..., description="Evidence IDs that support this finding")
    confidence: Optional[str] = Field(None, description="Confidence level")


class AgentResponseData(BaseModel):
    """Response from team's Master Agent back to backend.
    
    The backend receives this and adapts it to the existing Report schema.
    This schema is controlled by the team's LangGraph implementation.
    The backend must be able to accept any structure matching this contract.
    """
    session_id: str = Field(..., description="Session this response relates to")
    query: str = Field(..., description="Original user query")
    answer: str = Field(..., description="Natural language answer")
    findings: List[FindingData] = Field(default_factory=list, description="Structured findings")
    quantitative_results: List[QuantitativeResultData] = Field(
        default_factory=list,
        description="Numeric metrics"
    )
    visual_observations: List[str] = Field(default_factory=list, description="Visual-only observations")
    evidence: List[EvidenceData] = Field(default_factory=list, description="All evidence used")
    artifacts: List[ArtifactReferenceData] = Field(default_factory=list, description="Generated artifacts")
    limitations: List[str] = Field(default_factory=list, description="Known limitations")
    confidence: str = Field("unknown", description="Overall confidence level")
    execution_trace: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata")


class SpecialistResultData(BaseModel):
    """Result from a specialist tool (T1-T5) execution.
    
    The Master Agent calls specialist tools via the backend.
    This is the contract for what a specialist returns.
    """
    tool: str = Field(..., description="Tool name (T1_VQA, T2_Caption, etc.)")
    status: str = Field(..., description="success, partial, or failed")
    result: Dict[str, Any] = Field(default_factory=dict, description="Tool output")
    evidence: List[EvidenceData] = Field(default_factory=list, description="Evidence produced")
    artifacts: List[ArtifactReferenceData] = Field(default_factory=list, description="Artifacts produced")
    metrics: Dict[str, float] = Field(default_factory=dict, description="Quantitative metrics")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
    errors: List[str] = Field(default_factory=list, description="Errors if status is failed")
    execution_time_ms: float = Field(0.0, description="Time in milliseconds")
