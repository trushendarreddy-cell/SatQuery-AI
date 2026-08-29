from enum import Enum
from typing import List, Optional, Dict, Any

from pydantic import BaseModel, Field


class QueryIntent(str, Enum):
    IMAGE_INSPECTION = "image_inspection"
    IMAGE_COMPARISON = "image_comparison"
    CHANGE_DETECTION = "change_detection"
    BEFORE_AFTER_ANALYSIS = "before_after_analysis"
    AREA_CALCULATION = "area_calculation"
    SPATIAL_OVERLAP = "spatial_overlap"
    VEGETATION_ANALYSIS = "vegetation_analysis"
    CLOUD_SHADOW_ASSESSMENT = "cloud_shadow_assessment"
    MULTI_IMAGE_ANALYSIS = "multi_image_analysis"
    METADATA_QUESTION = "metadata_question"
    UNSUPPORTED = "unsupported"


class QueryStatus(str, Enum):
    READY = "ready"
    UNSUPPORTED = "unsupported"
    NEEDS_MORE_IMAGES = "needs_more_images"
    ERROR = "error"


class QueryRequest(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    query: str = Field(..., description="Natural-language question or instruction")


class QueryPlan(BaseModel):
    tool_name: str = Field(..., description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments for the tool")


class QueryResponse(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    query: str = Field(..., description="Original query text")
    intent: QueryIntent = Field(..., description="Detected query intent")
    required_images: List[str] = Field(default_factory=list, description="Image IDs needed for this query")
    required_tools: List[str] = Field(default_factory=list, description="Tools required to fulfill the query")
    reasoning: str = Field(..., description="Explanation of the plan")
    status: QueryStatus = Field(..., description="ready, unsupported, needs_more_images, or error")
    unsupported_reason: Optional[str] = Field(None, description="Explanation when status is unsupported")
    plan: List[QueryPlan] = Field(default_factory=list, description="Ordered execution plan")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Tool execution results")
