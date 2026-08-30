"""Schemas for the analysis orchestration layer (M8)."""

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.schemas.query_schema import QueryIntent, QueryPlan


class ExecutionStatus(str, Enum):
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"


class ExecutionStepStatus(str, Enum):
    SUCCESS = "success"
    FAILED = "failure"
    SKIPPED = "skipped"


class ExecutionStep(BaseModel):
    step_index: int = Field(..., description="0-based position in the plan")
    tool_name: str = Field(..., description="Tool that was (or would have been) invoked")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Arguments as planned")
    status: ExecutionStepStatus = Field(..., description="success, failure, or skipped")
    message: str = Field("", description="Human-readable outcome")
    error: Optional[str] = Field(None, description="Structured error when status is failure")
    result: Dict[str, Any] = Field(default_factory=dict, description="Raw tool output")


class ExecutionResult(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    query: str = Field(..., description="Original query text")
    intent: QueryIntent = Field(..., description="Detected query intent")
    status: ExecutionStatus = Field(..., description="overall success/partial/failed")
    plan_steps: int = Field(..., description="Number of steps in the plan")
    steps_executed: int = Field(0, description="Number of steps actually invoked")
    steps_succeeded: int = Field(0, description="Number of steps that succeeded")
    steps_failed: int = Field(0, description="Number of steps that failed")
    steps_skipped: int = Field(0, description="Number of steps skipped after a failure")
    steps: List[ExecutionStep] = Field(default_factory=list, description="Per-step outcomes")
    results: List[Dict[str, Any]] = Field(default_factory=list, description="Tool outputs in plan order")
    artifacts: List[Dict[str, Any]] = Field(default_factory=list, description="Generated artifact records")
    statistics: Dict[str, Any] = Field(default_factory=dict, description="Aggregated quantitative metrics")
    llm_interpretation: Optional[Dict[str, Any]] = Field(None, description="Structured LLM interpretation, when available")
    message: str = Field("", description="Summary of the execution")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
    errors: List[str] = Field(default_factory=list, description="Structured errors")


class OrchestrationRequest(BaseModel):
    session_id: str = Field(..., description="Active session identifier")
    query: str = Field(..., description="Natural-language query to plan and execute")
    use_llm: bool = Field(True, description="Whether to attempt LLM-based query understanding before deterministic planning")


class OrchestrationResponse(BaseModel):
    execution: ExecutionResult = Field(..., description="The structured execution result")