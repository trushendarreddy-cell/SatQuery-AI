"""Query-intelligence layer for M9.

The LLM is responsible only for understanding the user's intent. It never
executes analysis tools or computes geospatial results.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional

from app.agent.llm import MockLLMProvider, get_llm_provider
from app.schemas.query_intelligence_schema import (
    AnalysisType,
    BandRequirement,
    ImageSelection,
    LLMInterpretationResponse,
    QueryInterpretation,
)


class QueryIntelligenceService:
    """Validates LLM interpretation and falls back to deterministic rules."""

    def __init__(self, provider: Optional[Any] = None):
        self.provider = provider or get_llm_provider() or MockLLMProvider()

    def _build_prompt(self, query: str) -> List[Dict[str, str]]:
        return [
            {
                "role": "system",
                "content": (
                    "You are a geospatial query understanding component. "
                    "Return ONLY valid JSON matching the schema. "
                    "The value of 'analysis_type' must be one of: ndvi, savi, ndbi, "
                    "change_detection, spatial_overlap, compatibility, "
                    "image_inspection, metadata, cloud_shadow_assessment, "
                    "area_calculation, seasonal_risk, unsupported. "
                    "Never execute analysis or claim results that are not computed "
                    "by deterministic backend tools."
                ),
            },
            {
                "role": "user",
                "content": query,
            },
        ]

    def _extract_json(self, content: Any) -> Dict[str, Any]:
        if isinstance(content, dict):
            return content
        if not content:
            raise ValueError("LLM returned no content.")

        text = str(content).strip()
        if not text:
            raise ValueError("LLM returned empty content.")

        if text.startswith("```"):
            text = text.strip("`")
            if text.lower().startswith("json"):
                text = text[4:].lstrip()

        try:
            loaded = json.loads(text)
        except json.JSONDecodeError:
            # If the provider returns a plain text summary with a key-like phrase, try to
            # recover a valid dict from the first JSON object in the text.
            match = re.search(r"\{.*\}", text, re.DOTALL)
            if not match:
                raise ValueError("Malformed LLM response: not valid JSON")
            loaded = json.loads(match.group(0))

        if not isinstance(loaded, dict):
            raise ValueError("LLM response was not a JSON object.")
        return loaded

    def _fallback_interpretation(self, query: str, reason: str = "") -> QueryInterpretation:
        q = (query or "").lower()

        if any(term in q for term in ["ndvi", "vegetation health", "vegetation", "crop health", "green biomass"]):
            analysis_type = AnalysisType.NDVI
            required_bands = [
                BandRequirement(name="red", required=True, default_index=3),
                BandRequirement(name="nir", required=True, default_index=4),
            ]
            image_count = 1
        elif "savi" in q:
            analysis_type = AnalysisType.SAVI
            required_bands = [
                BandRequirement(name="red", required=True, default_index=3),
                BandRequirement(name="nir", required=True, default_index=4),
            ]
            image_count = 1
        elif any(term in q for term in ["ndbi", "built-up", "built up", "urban", "impervious"]):
            analysis_type = AnalysisType.NDBI
            required_bands = [
                BandRequirement(name="swir", required=True, default_index=3),
                BandRequirement(name="nir", required=True, default_index=4),
            ]
            image_count = 1
        elif any(term in q for term in ["change", "changed", "difference", "detect changes", "compare these two", "compare two"]):
            analysis_type = AnalysisType.CHANGE_DETECTION
            image_count = 2
            required_bands = []
        elif any(term in q for term in ["compare", "comparison", "versus", "vs", "pairwise"]):
            analysis_type = AnalysisType.CHANGE_DETECTION
            image_count = 2
            required_bands = []
        elif any(term in q for term in ["cloud", "shadow", "mask"]):
            analysis_type = AnalysisType.CLOUD_ASSESSMENT
            image_count = 1
            required_bands = []
        elif any(term in q for term in ["area", "hectare", "sq km", "square kilometers", "calculate the area"]):
            analysis_type = AnalysisType.AREA_CALCULATION
            image_count = 1
            required_bands = []
        elif any(term in q for term in ["metadata", "crs", "resolution", "bands", "acquisition date", "date"]):
            analysis_type = AnalysisType.METADATA
            image_count = 1
            required_bands = []
        elif any(term in q for term in ["inspect", "look", "show", "view", "this image"]):
            analysis_type = AnalysisType.IMAGE_INSPECTION
            image_count = 1
            required_bands = []
        else:
            analysis_type = AnalysisType.UNSUPPORTED
            image_count = 0
            required_bands = []

        return QueryInterpretation(
            analysis_type=analysis_type,
            image_selection=ImageSelection.PAIR if image_count >= 2 else ImageSelection.FIRST,
            image_count_required=image_count,
            required_bands=required_bands,
            parameters={},
            confidence=0.65 if analysis_type != AnalysisType.UNSUPPORTED else 0.1,
            needs_clarification=analysis_type == AnalysisType.UNSUPPORTED and "clarify" in q,
            clarification_question=(
                "Which specific analysis do you want to run on the uploaded scenes?"
                if analysis_type == AnalysisType.UNSUPPORTED else None
            ),
            reasoning=(reason or "Fallback deterministic interpretation applied."),
            raw_response=reason,
        )

    def interpret(self, session_id: str, query: str, use_llm: bool = True) -> LLMInterpretationResponse:
        if not use_llm:
            fallback = self._fallback_interpretation(query, "LLM interpretation disabled by request.")
            return LLMInterpretationResponse(
                session_id=session_id,
                query=query,
                interpretation=fallback,
                provider="deterministic_fallback",
                fallback_reason="LLM interpretation disabled by request.",
            )

        if self.provider is None:
            fallback = self._fallback_interpretation(query, "LLM provider is unavailable.")
            return LLMInterpretationResponse(
                session_id=session_id,
                query=query,
                interpretation=fallback,
                provider="deterministic_fallback",
                fallback_reason="LLM provider is unavailable.",
            )

        try:
            payload = self.provider.chat(self._build_prompt(query), [])
            message = payload.get("choices", [{}])[0].get("message", {})
            content = message.get("content")
            parsed = self._extract_json(content)

            if "interpretation" in parsed and isinstance(parsed["interpretation"], dict):
                candidate = parsed["interpretation"]
            else:
                candidate = parsed

            candidate.setdefault("analysis_type", "unsupported")
            candidate.setdefault("image_selection", "first")
            candidate.setdefault("image_count_required", 1)
            candidate.setdefault("required_bands", [])
            candidate.setdefault("parameters", {})
            candidate.setdefault("confidence", 0.0)
            candidate.setdefault("needs_clarification", False)
            candidate.setdefault("reasoning", "")

            interpretation = QueryInterpretation.model_validate(candidate)
            return LLMInterpretationResponse(
                session_id=session_id,
                query=query,
                interpretation=interpretation,
                provider=getattr(self.provider, "name", type(self.provider).__name__),
            )
        except Exception as exc:
            fallback = self._fallback_interpretation(query, str(exc))
            return LLMInterpretationResponse(
                session_id=session_id,
                query=query,
                interpretation=fallback,
                provider="deterministic_fallback",
                fallback_reason=str(exc),
            )
