from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class EvidenceType(str, Enum):
    COMPUTED = "computed"
    VISUAL = "visual"
    METADATA = "metadata"
    INFERENCE = "inference"


class ReportFinding(BaseModel):
    evidence_type: EvidenceType = Field(..., description="Type of evidence used for this finding")
    text: str = Field(..., description="Human-readable finding, grounded in execution results")
    source: Optional[str] = Field(None, description="Optional source label such as a tool or provider")


class QuantitativeResult(BaseModel):
    metric: str = Field(..., description="Metric name such as mean_value or change_percentage")
    value: Any = Field(..., description="Numeric or string value extracted from the execution statistics")
    unit: Optional[str] = Field(None, description="Unit for the metric, when known")
    evidence_type: EvidenceType = Field(default=EvidenceType.COMPUTED, description="This is computed evidence")


class MetadataItem(BaseModel):
    key: str = Field(..., description="Metadata field name")
    value: Any = Field(..., description="Metadata value from execution or session context")
    evidence_type: EvidenceType = Field(default=EvidenceType.METADATA, description="This metadata item is from execution metadata")


class ReportArtifact(BaseModel):
    artifact_id: Optional[str] = Field(None, description="Artifact identifier")
    filename: Optional[str] = Field(None, description="Artifact filename")
    path: Optional[str] = Field(None, description="Artifact path or reference")
    type: Optional[str] = Field(None, description="Artifact type")
    crs: Optional[str] = Field(None, description="Artifact CRS")
    dimensions: Optional[str] = Field(None, description="Artifact dimensions (e.g. 128x128)")
    description: Optional[str] = Field(None, description="Artifact description")


class Report(BaseModel):
    title: str = Field(..., description="Short report title")
    user_query: str = Field(..., description="Original user query")
    summary: str = Field(..., description="Short summary of the outcome")
    analysis_type: str = Field("unsupported", description="Analysis type or unsupported")
    findings: List[ReportFinding] = Field(default_factory=list, description="Structured, evidence-tagged findings")
    quantitative_results: List[QuantitativeResult] = Field(default_factory=list, description="Structured quantitative statistics")
    visual_observations: List[str] = Field(default_factory=list, description="Visual-only observations retained separately from numeric metrics")
    metadata: List[MetadataItem] = Field(default_factory=list, description="Metadata extracted for this report")
    artifacts: List[ReportArtifact] = Field(default_factory=list, description="Generated artifacts referenced by the execution")
    limitations: List[str] = Field(default_factory=list, description="Documented limitations from results or warnings")
    confidence: str = Field("unknown", description="Confidence level or unknown if not justified")
    methodology: List[str] = Field(default_factory=list, description="Execution-based methodology")


class ReportRequest(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    query: str = Field(..., description="Natural-language query to analyze")
    use_llm: bool = Field(True, description="Whether to attempt LLM-backed query understanding")
    use_vision: bool = Field(True, description="Whether to include vision observations when available")


class ReportResponse(BaseModel):
    success: bool = Field(..., description="Whether a report was successfully generated")
    report: Report = Field(..., description="Evidence-grounded analysis report")
