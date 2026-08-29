from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ToolStatus(str, Enum):
    SUCCESS = "success"
    FAILURE = "failure"


class AgentToolCall(BaseModel):
    """Standardized request to invoke an agent tool."""
    tool_name: str = Field(..., description="Name of the tool to invoke")
    arguments: Dict[str, Any] = Field(default_factory=dict, description="Tool-specific arguments as a JSON object")


class AgentToolResult(BaseModel):
    """Standardized response from an agent tool invocation."""
    tool_name: str = Field(..., description="Name of the tool that was invoked")
    status: ToolStatus = Field(..., description="success or failure")
    result: Dict[str, Any] = Field(default_factory=dict, description="Structured tool output as JSON")
    message: str = Field(..., description="Human-readable status message")
    warnings: List[str] = Field(default_factory=list, description="Non-fatal warnings")
    error: Optional[str] = Field(None, description="Error message if status is failure")


class ToolDefinition(BaseModel):
    """Registry entry describing an agent-accessible tool."""
    name: str = Field(..., description="Unique tool identifier")
    description: str = Field(..., description="Brief summary of what the tool does")
    purpose: str = Field(..., description="Detailed purpose and use-case for the agent")
    input_schema: Dict[str, Any] = Field(..., description="JSON Schema for the tool's input parameters")
    output_schema: Dict[str, Any] = Field(..., description="JSON Schema for the tool's output structure")
    required_parameters: List[str] = Field(..., description="List of required parameter names")
    failure_conditions: List[str] = Field(..., description="List of conditions under which the tool fails")
