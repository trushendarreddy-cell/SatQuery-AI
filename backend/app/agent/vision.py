"""Minimal multimodal / vision abstraction for M10.

This layer is intentionally thin and provider-independent. It never performs
geospatial computations; it only interprets the user query in the context of the
already-uploaded image metadata and visual content.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agent.llm import MockLLMProvider, get_llm_provider
from app.core.session_cache import session_manager
from app.schemas.vision_schema import VisionRequest, VisionResult


class VisionProvider:
    """Abstract interface for multimodal image interpretation providers."""

    @property
    def name(self) -> str:
        return "vision_provider"

    def analyze(self, query: str, image_context: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        raise NotImplementedError


class MockVisionProvider(VisionProvider):
    """Deterministic mock provider for offline mode, tests, and fallback."""

    @property
    def name(self) -> str:
        return "mock"

    def analyze(self, query: str, image_context: Dict[str, Any], metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
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


class VisionService:
    """Thin wrapper around a provider-independent multimodal service."""

    def __init__(self, provider: Optional[Any] = None):
        self.provider = provider or self._resolve_provider()

    def _resolve_provider(self) -> Optional[VisionProvider]:
        try:
            llm_provider = get_llm_provider()
            if llm_provider is None:
                return MockVisionProvider()
            return MockVisionProvider()
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
