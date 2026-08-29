"""LLM provider abstraction for the SatQuery AI backend."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send a chat completion request with optional tool definitions."""
        ...


class OpenAILLMProvider(LLMProvider):
    """OpenAI-compatible LLM provider."""

    def __init__(self, api_key: str, model: str, base_url: str = "https://api.openai.com/v1", max_tokens: int = 1024, temperature: float = 0.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature

    def chat(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            from openai import OpenAI
        except ImportError:
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": "LLM provider not available: openai package is not installed.",
                    }
                }],
                "tool_calls": [],
            }

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        response = client.chat.completions.create(
            model=self.model,
            messages=messages,
            tools=tools if tools else None,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
        )
        choice = response.choices[0]
        tool_calls = []
        if hasattr(choice.message, "tool_calls") and choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "id": tc.id,
                    "name": tc.function.name,
                    "arguments": tc.function.arguments,
                })
        return {
            "choices": [{
                "message": {
                    "role": choice.message.role,
                    "content": choice.message.content or "",
                }
            }],
            "tool_calls": tool_calls,
        }


class MockLLMProvider(LLMProvider):
    """Deterministic mock provider for testing without external API calls."""

    def chat(self, messages: List[Dict[str, str]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        last_user = ""
        for m in reversed(messages):
            if m.get("role") == "user":
                last_user = m.get("content", "").lower()
                break

        tool_map = {t["function"]["name"]: t for t in tools} if tools else {}
        selected_tool = None
        for name, tool in tool_map.items():
            keywords = tool["function"].get("keywords", [])
            if any(kw in last_user for kw in keywords):
                selected_tool = name
                break

        if selected_tool:
            return {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": f"I will use the {selected_tool} tool to help with that.",
                    }
                }],
                "tool_calls": [{
                    "id": "call_mock_001",
                    "name": selected_tool,
                    "arguments": "{}",
                }],
            }

        return {
            "choices": [{
                "message": {
                    "role": "assistant",
                    "content": "I can help you analyze geospatial data. Please upload images and ask about change detection, NDVI, cloud masking, or area calculations.",
                }
            }],
            "tool_calls": [],
        }


def get_llm_provider() -> LLMProvider:
    """Factory function returning the configured LLM provider."""
    from app.core.config import settings
    provider_name = settings.LLM_PROVIDER.lower()
    if provider_name == "openai":
        if not settings.LLM_API_KEY:
            return MockLLMProvider()
        return OpenAILLMProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
        )
    return MockLLMProvider()
