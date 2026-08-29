"""Agent service that orchestrates LLM-driven tool execution."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agent.llm import get_llm_provider
from app.agent.schemas import AgentToolCall, AgentToolResult
from app.agent.tools import invoke_agent_tool, get_tool_registry


class AgentService:
    """Deterministic agent service that uses LLM for intent interpretation and tool selection."""

    def __init__(self, provider=None):
        self.provider = provider or get_llm_provider()

    def _build_tool_schemas(self) -> List[Dict[str, Any]]:
        schemas = []
        for tool in get_tool_registry():
            schemas.append({
                "type": "function",
                "function": {
                    "name": tool.name,
                    "description": tool.description,
                    "parameters": tool.input_schema,
                },
                "keywords": getattr(tool, "keywords", []),
            })
        return schemas

    def _build_messages(self, user_query: str, session_id: str, context: Optional[str] = None) -> List[Dict[str, str]]:
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a geospatial analysis assistant. "
                    "You have access to deterministic tools for satellite image analysis. "
                    "Never invent coordinates, metadata, NDVI values, change percentages, or areas. "
                    "All numerical facts must come from tool outputs. "
                    "If a tool is unavailable or evidence is insufficient, say so explicitly."
                ),
            },
        ]
        if context:
            messages.append({"role": "system", "content": context})
        messages.append({"role": "user", "content": user_query})
        return messages

    def execute(self, session_id: str, user_query: str, context: Optional[str] = None) -> Dict[str, Any]:
        messages = self._build_messages(user_query, session_id, context)
        tools = self._build_tool_schemas()
        llm_response = self.provider.chat(messages, tools)
        tool_calls = llm_response.get("tool_calls", [])
        tool_results: List[Dict[str, Any]] = []
        final_message = llm_response["choices"][0]["message"].get("content", "")

        for tc in tool_calls:
            tool_name = tc.get("name", "")
            raw_args = tc.get("arguments", "{}")
            try:
                import json
                arguments = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
            except Exception:
                arguments = {}
            arguments.setdefault("session_id", session_id)
            call = AgentToolCall(tool_name=tool_name, arguments=arguments)
            result = invoke_agent_tool(call)
            tool_results.append({
                "tool_name": tool_name,
                "status": result.status.value,
                "result": result.result,
                "message": result.message,
                "error": result.error,
            })
            messages.append({
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": tc.get("id", "call_0"),
                    "type": "function",
                    "function": {
                        "name": tool_name,
                        "arguments": raw_args,
                    },
                }],
            })
            messages.append({
                "role": "tool",
                "tool_call_id": tc.get("id", "call_0"),
                "content": result.model_dump_json(),
            })

        if tool_calls:
            follow_up = self.provider.chat(messages, [])
            final_message = follow_up["choices"][0]["message"].get("content", final_message)

        return {
            "session_id": session_id,
            "query": user_query,
            "response": final_message,
            "tool_calls": tool_results,
            "provider": type(self.provider).__name__,
        }
