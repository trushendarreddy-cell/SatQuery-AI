from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class VisionResult(BaseModel):
    """Structured multimodal/visual interpretation result."""

    supported: bool = Field(..., description="Whether visual reasoning is available and appropriate")
    confidence: float = Field(0.0, description="Confidence in the interpretation, 0.0 to 1.0")
    observations: List[str] = Field(default_factory=list, description="Direct visual observations")
    visual_features: List[str] = Field(default_factory=list, description="Features detected in the image")
    interpretation: str = Field("", description="Reasoned interpretation without claiming computed metrics")
    limitations: List[str] = Field(default_factory=list, description="Known limitations of the visual analysis")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
    provider: str = Field("deterministic_fallback", description="Provider used for the visual reasoning")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Metadata used as context for the visual analysis")

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class VisionRequest(BaseModel):
    """Request for multimodal/vision reasoning."""

    session_id: str = Field(..., description="Active session identifier")
    image_id: str = Field(..., description="Image in the session to assess")
    query: str = Field(..., description="User question or contextual instruction")
    context: Optional[str] = Field(None, description="Additional context for the reasoning step")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Image/session metadata used to constrain the reasoning")


class VisionStatus(BaseModel):
    success: bool = Field(..., description="Whether the transformation succeeded")
    message: str = Field(..., description="Human-readable response")
    visual: VisionResult = Field(..., description="Structured visual reasoning output")
