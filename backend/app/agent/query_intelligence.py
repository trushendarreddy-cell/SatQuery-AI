"""Query-intelligence layer for M9.

The LLM is responsible only for understanding the user's intent. It never
executes analysis tools or computes geospatial results.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.agent.llm import MockLLMProvider, get_llm_provider
from app.schemas.query_intelligence_schema import (
    AnalysisType,
    BandRequirement,
    ImageSelection,
    LLMInterpretationResponse,
    QueryInterpretation,
)


def _first_json_object(text: str) -> str:
    """Return the first complete, parseable JSON object found in ``text``.

    Walks the string tracking brace depth and string state instead of using a
    regex. A greedy ``\{.*\}`` matches from the first brace to the last one in
    the entire reply, so any response mentioning two objects captured the
    span between them and failed to parse. Candidates that do not parse are
    skipped so the scan can continue to the next opening brace.
    """
    depth = 0
    start = -1
    in_string = False
    escaped = False

    for index, char in enumerate(text):
        if in_string:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                in_string = False
            continue

        if char == '"':
            in_string = True
        elif char == "{":
            if depth == 0:
                start = index
            depth += 1
        elif char == "}":
            if depth > 0:
                depth -= 1
                if depth == 0 and start >= 0:
                    candidate = text[start : index + 1]
                    try:
                        json.loads(candidate)
                    except json.JSONDecodeError:
                        continue
                    return candidate

    raise ValueError("Malformed LLM response: not valid JSON")


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
            # The provider returned prose around the JSON. Recover the first
            # complete object with a brace-depth scan rather than a regex:
            # a greedy \{.*\} spans from the first brace to the last one in
            # the whole reply, so a response containing two objects captured
            # junk and lost the model's answer entirely.
            loaded = json.loads(_first_json_object(text))

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
