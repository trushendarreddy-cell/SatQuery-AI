"""Schemas for the LLM-powered query-intelligence layer (M9).

The LLM only interprets *what the user is asking for* -- it never performs
satellite analysis. All structured output here is validated before it reaches
the deterministic planner/orchestrator.
"""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class AnalysisType(str, Enum):
    """Capabilities the backend can actually execute."""

    NDVI = "ndvi"
    EVI = "evi"
    NDWI = "ndwi"
    SAVI = "savi"
    NDBI = "ndbi"
    CHANGE_DETECTION = "change_detection"
    SPATIAL_OVERLAP = "spatial_overlap"
    COMPATIBILITY = "compatibility"
    IMAGE_INSPECTION = "image_inspection"
    METADATA = "metadata"
    CLOUD_ASSESSMENT = "cloud_shadow_assessment"
    AREA_CALCULATION = "area_calculation"
    SCENE_CLASSIFICATION = "scene_classification"
    SEASONAL_RISK = "seasonal_risk"
    UNSUPPORTED = "unsupported"


class ImageSelection(str, Enum):
    FIRST = "first"
    LAST = "last"
    ALL = "all"
    PAIR = "pair"
    FIRST_AND_LAST = "first_and_last"


class BandRequirement(BaseModel):
    """A spectral band the analysis needs, if any."""

    name: str = Field(..., description="Band role, e.g. red, nir, blue, green, swir")
    required: bool = Field(..., description="Whether the band is mandatory for this analysis")
    default_index: Optional[int] = Field(None, description="1-based default band index when not specified")


class QueryInterpretation(BaseModel):
    """Validated structured interpretation of a natural-language query."""

    analysis_type: AnalysisType = Field(..., description="Capability the backend can execute")
    image_selection: ImageSelection = Field(..., description="Which session images are relevant")
    image_count_required: int = Field(0, description="How many images the analysis needs")
    required_bands: List[BandRequirement] = Field(default_factory=list, description="Spectral band roles needed")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="Optional numeric/string parameters")
    confidence: float = Field(0.0, description="0.0-1.0 confidence in the interpretation")
    needs_clarification: bool = Field(False, description="Whether the query is too ambiguous to execute")
    clarification_question: Optional[str] = Field(None, description="Question to ask when clarification is needed")
    reasoning: str = Field("", description="Short explanation of the interpretation")
    raw_response: Optional[str] = Field(None, description="Raw LLM content, for transparency")

    @field_validator("confidence")
    @classmethod
    def _clamp_confidence(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))

    @field_validator("image_count_required")
    @classmethod
    def _non_negative_count(cls, v: int) -> int:
        return max(0, int(v))


class LLMInterpretationRequest(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    query: str = Field(..., description="Natural-language query")
    use_llm: bool = Field(True, description="Whether to attempt LLM interpretation")


class LLMInterpretationResponse(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    query: str = Field(..., description="Original query text")
    interpretation: QueryInterpretation = Field(..., description="Validated structured interpretation")
    provider: str = Field(..., description="LLM provider used, or 'deterministic_fallback'")
    fallback_reason: Optional[str] = Field(None, description="Why the deterministic planner was used instead")