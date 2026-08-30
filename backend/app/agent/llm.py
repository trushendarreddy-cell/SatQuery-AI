"""LLM provider abstraction for the SatQuery AI backend (M9).

Supports pluggable providers (Gemini, OpenAI-compatible, and a deterministic
mock). All providers expose the same ``chat(messages, tools)`` contract.
"""

from __future__ import annotations

import json
import time
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from app.core.config import settings


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Send a chat completion request. Returns ``{"choices": [...], "tool_calls": [...]}``."""
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """Human-readable provider name."""
        ...


class MockLLMProvider(LLMProvider):
    """Deterministic keyword-based provider used when the real provider is unavailable."""

    @property
    def name(self) -> str:
        return "mock"

    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
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


class OpenAICompatibleProvider(LLMProvider):
    """Generic OpenAI-compatible HTTP provider (works with OpenAI and OpenAI-compatible gateways)."""

    def __init__(self, api_key: str, model: str, base_url: str, max_tokens: int = 1024,
                 temperature: float = 0.0, timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "openai-compatible"

    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            import httpx
        except ImportError:
            raise RuntimeError("httpx is required for OpenAI-compatible providers.")

        if not self.api_key:
            raise RuntimeError("LLM API key is not configured.")

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }
        if tools:
            payload["tools"] = tools

        try:
            with httpx.Client(timeout=self.timeout) as client:
                resp = client.post(
                    f"{self.base_url}/chat/completions",
                    headers=headers,
                    json=payload,
                )
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError(f"LLM provider timed out after {self.timeout}s: {exc}") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError(f"LLM provider HTTP error: {exc}") from exc

        if "error" in data:
            raise RuntimeError(f"LLM provider error: {data['error']}")
        return data


class GeminiProvider(LLMProvider):
    """Google Gemini-compatible provider using the OpenAI-compatible endpoint.

    Gemini exposes an OpenAI-compatible API at ``base_url`` when configured
    with a Gemini API key, so this is a thin specialization of the OpenAI
    provider with a default base URL of the Gemini OpenAI-compatible gateway.
    """

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash",
                 base_url: str = "", max_tokens: int = 1024, temperature: float = 0.0,
                 timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.max_tokens = max_tokens
        self.temperature = temperature
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "gemini"

    def chat(self, messages: List[Dict[str, Any]], tools: List[Dict[str, Any]]) -> Dict[str, Any]:
        delegate = OpenAICompatibleProvider(
            api_key=self.api_key,
            model=self.model,
            base_url=self.base_url,
            max_tokens=self.max_tokens,
            temperature=self.temperature,
            timeout=self.timeout,
        )
        return delegate.chat(messages, tools)


def get_llm_provider() -> Optional[LLMProvider]:
    """Return a configured LLM provider, or None when no provider is usable.

    Always falls back to the deterministic mock when the provider is disabled,
    missing an API key, or otherwise unusable. Callers may check ``is None``
    to run fully offline.
    """
    provider_name = (settings.LLM_PROVIDER or "").strip().lower()

    if provider_name in ("", "mock", "none", "off", "disabled"):
        return None

    if not settings.LLM_API_KEY:
        return None

    common = dict(
        api_key=settings.LLM_API_KEY,
        model=settings.LLM_MODEL,
        max_tokens=settings.LLM_MAX_TOKENS,
        temperature=settings.LLM_TEMPERATURE,
    )

    if provider_name == "gemini":
        return GeminiProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL or GeminiProvider.DEFAULT_BASE_URL,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
        )

    if provider_name in ("openai", "openai-compatible", "openai_compatible"):
        return OpenAICompatibleProvider(
            api_key=settings.LLM_API_KEY,
            model=settings.LLM_MODEL,
            base_url=settings.LLM_BASE_URL,
            max_tokens=settings.LLM_MAX_TOKENS,
            temperature=settings.LLM_TEMPERATURE,
        )

    # Unknown provider name -> treat as disabled.
    return None