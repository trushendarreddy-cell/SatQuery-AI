"""Minimal multimodal / vision abstraction for M10.

This layer is intentionally thin and provider-independent. It never performs
geospatial computations; it only interprets the user query in the context of the
already-uploaded image metadata and visual content.
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

import httpx

from app.core.config import settings
from app.core.session_cache import session_manager
from app.schemas.vision_schema import VisionRequest, VisionResult


class VisionProvider:
    """Abstract interface for multimodal image interpretation providers."""

    @property
    def name(self) -> str:
        return "vision_provider"

    def analyze(self, query: str, image_context: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None, image_path: Optional[str] = None) -> Dict[str, Any]:
        raise NotImplementedError


class MockVisionProvider(VisionProvider):
    """Deterministic mock provider for offline mode, tests, and fallback."""

    @property
    def name(self) -> str:
        return "mock"

    def analyze(self, query: str, image_context: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None, image_path: Optional[str] = None) -> Dict[str, Any]:
        q = (query or "").lower()
        filename = image_context.get("filename", "image")

        if "urban" in q or "built" in q or "expansion" in q or "city" in q:
            return {
                "supported": True,
                "confidence": 0.82,
                "observations": [f"The image for {filename} contains visually dense built-up structures and street-like patterns."],
                "visual_features": ["built-up clusters", "road network", "urban texture"],
                "interpretation": "These visual cues are consistent with urbanized or expanding built-up land, but this is a visual interpretation only.",
                "limitations": ["No quantitative built-up index was computed; this is not a measurement."],
                "warnings": ["No deterministic geospatial metric was executed in the vision step."],
            }

        if "vegetation" in q or "green" in q or "healthy" in q or "crop" in q:
            return {
                "supported": True,
                "confidence": 0.8,
                "observations": [f"The image for {filename} shows dense green and vegetated texture in the visible scene."],
                "visual_features": ["vegetation canopy", "green patches", "land cover texture"],
                "interpretation": "The visual pattern suggests vegetated cover, but the exact vegetation index still requires the deterministic pipeline.",
                "limitations": ["This is only a visual approximation of vegetation density."],
                "warnings": ["No NDVI or SAVI computation ran in this step."],
            }

        return {
            "supported": True,
            "confidence": 0.7,
            "observations": [f"The image for {filename} is visually interpretable and available for analysis."],
            "visual_features": ["general land cover", "texture", "surface pattern"],
            "interpretation": "The image can be inspected visually, but the exact quantitative interpretation should be confirmed by the deterministic analysis pipeline.",
            "limitations": ["Visual-only observation without computed metrics."],
            "warnings": ["No quantitative raster analysis was performed in this step."],
        }


class OpenAICompatibleVisionProvider(VisionProvider):
    """OpenAI-compatible multimodal provider that accepts image content in data URLs."""

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

    @staticmethod
    def _read_image_data(image_path: Optional[str], image_context: Optional[Dict[str, Any]]) -> str:
        if image_path:
            path = Path(image_path)
            if path.exists():
                payload = path.read_bytes()
                return base64.b64encode(payload).decode("utf-8")
        if isinstance(image_context, dict):
            for key in ("image_base64", "base64", "data"):
                value = image_context.get(key)
                if value:
                    return str(value)
        synthetic = base64.b64encode(b"synthetic-image-bytes")
        return synthetic.decode("utf-8")

    @staticmethod
    def _mime_type_for_filename(filename: str) -> str:
        lower = (filename or "").lower()
        if lower.endswith(".png"):
            return "image/png"
        if lower.endswith(".jpg") or lower.endswith(".jpeg"):
            return "image/jpeg"
        if lower.endswith(".webp"):
            return "image/webp"
        return "image/png"

    @staticmethod
    def _normalize_response(payload: Any) -> Dict[str, Any]:
        if isinstance(payload, dict):
            if "supported" in payload:
                return payload
            if "choices" in payload:
                content = payload["choices"][0]["message"].get("content")
                if isinstance(content, str):
                    try:
                        parsed = json.loads(content)
                    except json.JSONDecodeError:
                        return {
                            "supported": True,
                            "confidence": 0.7,
                            "observations": [content],
                            "visual_features": ["general visual interpretation"],
                            "interpretation": content,
                            "limitations": ["This is a model-generated visual interpretation only."],
                            "warnings": ["No deterministic metric was computed."],
                        }
                    if isinstance(parsed, list):
                        parsed = parsed[0] if parsed else {}
                    if isinstance(parsed, dict):
                        if "supported" not in parsed:
                            parsed["supported"] = True
                        return parsed
            if "text" in payload:
                return {
                    "supported": True,
                    "confidence": 0.7,
                    "observations": [str(payload["text"])],
                    "visual_features": ["general visual interpretation"],
                    "interpretation": str(payload["text"]),
                    "limitations": ["This is a model-generated visual interpretation only."],
                    "warnings": ["No deterministic metric was computed."],
                }
        if isinstance(payload, str):
            try:
                parsed = json.loads(payload)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            return {
                "supported": True,
                "confidence": 0.7,
                "observations": [payload],
                "visual_features": ["general visual interpretation"],
                "interpretation": payload,
                "limitations": ["This is a model-generated visual interpretation only."],
                "warnings": ["No deterministic metric was computed."],
            }
        raise ValueError("Vision provider returned an invalid response format.")

    def analyze(self, query: str, image_context: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None, image_path: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Vision API key is not configured.")

        image_filename = (image_context or {}).get("filename") or (metadata or {}).get("filename") or "image.png"
        mime_type = self._mime_type_for_filename(image_filename)
        encoded = self._read_image_data(image_path or image_context.get("image_path"), image_context)

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": query},
                    {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                ],
            }],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

        try:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            except TypeError:
                with httpx.Client() as client:
                    resp = client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError("Vision provider timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError("Vision provider returned an HTTP error.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Vision provider request failed.") from exc

        return self._normalize_response(data)


class GeminiVisionProvider(VisionProvider):
    """Google Gemini vision provider with a conservative response fallback."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", base_url: str = "",
                 image_mime_type: str = "image/png", timeout: float = 30.0):
        self.api_key = api_key
        self.model = model
        self.base_url = (base_url or self.DEFAULT_BASE_URL).rstrip("/")
        self.image_mime_type = image_mime_type
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "gemini"

    @staticmethod
    def _read_image_data(image_path: Optional[str], image_context: Optional[Dict[str, Any]]) -> str:
        if image_path:
            path = Path(image_path)
            if path.exists():
                return base64.b64encode(path.read_bytes()).decode("utf-8")
        if isinstance(image_context, dict):
            for key in ("image_base64", "base64", "data"):
                value = image_context.get(key)
                if value:
                    return str(value)
        return base64.b64encode(b"synthetic-image-bytes").decode("utf-8")

    @staticmethod
    def _normalize_response(payload: Any) -> Dict[str, Any]:
        if not isinstance(payload, dict):
            raise ValueError("Gemini vision provider returned an invalid response.")

        text = None
        candidates = payload.get("candidates") or []
        if candidates:
            content = candidates[0].get("content", {})
            parts = content.get("parts") or []
            if parts:
                text = parts[0].get("text")
        if text:
            try:
                parsed = json.loads(text)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            return {
                "supported": True,
                "confidence": 0.75,
                "observations": [text],
                "visual_features": ["general visual interpretation"],
                "interpretation": text,
                "limitations": ["This is a model-generated visual interpretation only."],
                "warnings": ["No deterministic metric was computed."],
            }
        raise ValueError("Gemini vision provider returned no usable content.")

    def analyze(self, query: str, image_context: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None, image_path: Optional[str] = None) -> Dict[str, Any]:
        if not self.api_key:
            raise RuntimeError("Vision API key is not configured.")

        filename = (image_context or {}).get("filename") or (metadata or {}).get("filename") or "image.png"
        mime_type = OpenAICompatibleVisionProvider._mime_type_for_filename(filename)
        encoded = self._read_image_data(image_path or image_context.get("image_path"), image_context)
        payload = {
            "contents": [{
                "parts": [
                    {"text": query},
                    {"inline_data": {"mime_type": mime_type, "data": encoded}},
                ]
            }]
        }

        headers = {"Content-Type": "application/json"}
        url = f"{self.base_url}/{self.model}:generateContent?key={self.api_key}"
        try:
            try:
                with httpx.Client(timeout=self.timeout) as client:
                    resp = client.post(url, headers=headers, json=payload)
            except TypeError:
                with httpx.Client() as client:
                    resp = client.post(url, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()
        except httpx.TimeoutException as exc:
            raise RuntimeError("Vision provider timed out.") from exc
        except httpx.HTTPStatusError as exc:
            raise RuntimeError("Vision provider returned an HTTP error.") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("Vision provider request failed.") from exc

        return self._normalize_response(data)


def get_vision_provider() -> Optional[VisionProvider]:
    """Return the configured real provider, otherwise a safe mock fallback."""
    provider_name = (settings.VISION_PROVIDER or "").strip().lower()
    if provider_name in ("", "mock", "none", "off", "disabled"):
        return MockVisionProvider()
    if not settings.VISION_API_KEY:
        return MockVisionProvider()

    if provider_name == "gemini":
        return GeminiVisionProvider(
            api_key=settings.VISION_API_KEY,
            model=settings.VISION_MODEL,
            base_url=settings.VISION_BASE_URL or GeminiVisionProvider.DEFAULT_BASE_URL,
            image_mime_type="image/png",
        )

    if provider_name in ("openai", "openai-compatible", "openai_compatible"):
        return OpenAICompatibleVisionProvider(
            api_key=settings.VISION_API_KEY,
            model=settings.VISION_MODEL,
            base_url=settings.VISION_BASE_URL,
            max_tokens=settings.VISION_MAX_TOKENS,
            temperature=settings.VISION_TEMPERATURE,
        )

    return MockVisionProvider()


class VisionService:
    """Thin wrapper around a provider-independent multimodal service."""

    def __init__(self, provider: Optional[Any] = None):
        self.provider = provider or self._resolve_provider()

    def _resolve_provider(self) -> Optional[VisionProvider]:
        try:
            provider = get_vision_provider()
            return provider or MockVisionProvider()
        except Exception:
            return MockVisionProvider()

    def _coerce_context(self, image_id: str, metadata: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if metadata is None:
            return None
        if not isinstance(metadata, dict):
            return None
        if image_id and metadata.get("image_id") not in (None, image_id):
            metadata = {**metadata, "image_id": image_id}
        return metadata

    def _validate_response(self, payload: Dict[str, Any], context: Dict[str, Any]) -> VisionResult:
        if not isinstance(payload, dict):
            raise ValueError("Vision provider returned a non-dictionary response.")

        if "supported" not in payload:
            raise ValueError("Vision provider response missing 'supported'.")

        valid = payload.get("supported") in (True, False)
        if not valid:
            raise ValueError("Vision provider response 'supported' must be boolean.")

        result = VisionResult(
            supported=bool(payload.get("supported", False)),
            confidence=float(payload.get("confidence", 0.0) or 0.0),
            observations=list(payload.get("observations") or []),
            visual_features=list(payload.get("visual_features") or []),
            interpretation=str(payload.get("interpretation") or ""),
            limitations=list(payload.get("limitations") or []),
            warnings=list(payload.get("warnings") or []),
            provider=getattr(self.provider, "name", "vision_provider"),
            metadata=context,
        )
        return result

    def analyze(
        self,
        session_id: str,
        image_id: str,
        query: str,
        metadata: Optional[Dict[str, Any]] = None,
        context: Optional[str] = None,
    ) -> VisionResult:
        image_context = self._coerce_context(image_id, metadata)
        if image_context is None:
            return VisionResult(
                supported=False,
                confidence=0.0,
                observations=[],
                visual_features=[],
                interpretation="",
                limitations=["Image context is missing or invalid; visual reasoning cannot safely proceed."],
                warnings=["Vision skipped because there was no valid image context."],
                provider=getattr(self.provider, "name", "vision_provider"),
                metadata=None,
            )

        if not image_context.get("filename"):
            return VisionResult(
                supported=False,
                confidence=0.0,
                observations=[],
                visual_features=[],
                interpretation="",
                limitations=["The image has no usable filename or metadata for a safe vision check."],
                warnings=["Vision interpretation was blocked by incomplete image context."],
                provider=getattr(self.provider, "name", "vision_provider"),
                metadata=image_context,
            )

        try:
            payload = self.provider.analyze(query, image_context, metadata=image_context)
            result = self._validate_response(payload or {}, image_context)
            return result
        except Exception as exc:
            return VisionResult(
                supported=False,
                confidence=0.0,
                observations=[],
                visual_features=[],
                interpretation="",
                limitations=[f"Vision analysis could not run: {exc}"],
                warnings=["The deterministic pipeline will continue without visual reasoning."],
                provider=getattr(self.provider, "name", "vision_provider"),
                metadata=image_context,
            )


vision_service = VisionService()
