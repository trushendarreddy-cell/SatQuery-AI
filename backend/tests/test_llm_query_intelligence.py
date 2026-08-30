import json

import pytest

from app.agent.query_intelligence import QueryIntelligenceService
from app.pipeline.orchestrator import AnalysisOrchestrator, orchestrate_analysis
from app.schemas.query_intelligence_schema import AnalysisType


class FakeProvider:
    def __init__(self, payload):
        self.payload = payload
        self.name = "fake"

    def chat(self, messages, tools):
        return {"choices": [{"message": {"content": json.dumps(self.payload)}}]}


class FakeProviderFailure:
    @property
    def name(self):
        return "fake"

    def chat(self, messages, tools):
        raise RuntimeError("provider unavailable")


class FakeProviderMalformed:
    @property
    def name(self):
        return "fake"

    def chat(self, messages, tools):
        return {"choices": [{"message": {"content": "not-json"}}]}


@pytest.mark.parametrize(
    "query,payload,expected",
    [
        ("Calculate NDVI for this image.", {"analysis_type": "ndvi", "image_selection": "first", "image_count_required": 1, "required_bands": [{"name": "red", "required": True, "default_index": 3}, {"name": "nir", "required": True, "default_index": 4}], "confidence": 0.97, "needs_clarification": False, "reasoning": "NDVI requested"}, AnalysisType.NDVI),
        ("Calculate SAVI using red band 3 and NIR band 4.", {"analysis_type": "savi", "image_selection": "first", "image_count_required": 1, "required_bands": [{"name": "red", "required": True, "default_index": 3}, {"name": "nir", "required": True, "default_index": 4}], "confidence": 0.95, "needs_clarification": False, "reasoning": "SAVI requested"}, AnalysisType.SAVI),
        ("Find built-up areas in this image.", {"analysis_type": "ndbi", "image_selection": "first", "image_count_required": 1, "confidence": 0.92, "needs_clarification": False, "reasoning": "Built-up area detection"}, AnalysisType.NDBI),
        ("Compare these two satellite images and detect changes.", {"analysis_type": "change_detection", "image_selection": "pair", "image_count_required": 2, "confidence": 0.96, "needs_clarification": False, "reasoning": "Pairwise change detection"}, AnalysisType.CHANGE_DETECTION),
        ("Compare the two uploaded images.", {"analysis_type": "change_detection", "image_selection": "pair", "image_count_required": 2, "confidence": 0.85, "needs_clarification": False, "reasoning": "Compare two uploaded scenes"}, AnalysisType.CHANGE_DETECTION),
        ("Do something impossible with this dataset.", {"analysis_type": "unsupported", "image_selection": "first", "image_count_required": 1, "confidence": 0.15, "needs_clarification": False, "reasoning": "Unsupported request"}, AnalysisType.UNSUPPORTED),
        ("I need more context on the requested analysis.", {"analysis_type": "unsupported", "image_selection": "first", "image_count_required": 1, "confidence": 0.4, "needs_clarification": True, "clarification_question": "Which band combination do you want?", "reasoning": "Clarification needed"}, AnalysisType.UNSUPPORTED),
    ],
)
def test_query_intelligence_interpretation(query, payload, expected):
    service = QueryIntelligenceService(provider=FakeProvider(payload))
    result = service.interpret("llm_session", query)
    assert result.interpretation.analysis_type == expected
    assert result.provider == "fake"
    assert result.query == query


def test_query_intelligence_handles_missing_api_key(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.LLM_API_KEY", "", raising=False)
    service = QueryIntelligenceService(provider=None)
    result = service.interpret("missing_key", "Calculate NDVI for this image.")
    assert result.provider == "deterministic_fallback"
    assert result.fallback_reason is not None


def test_query_intelligence_handles_provider_exception():
    service = QueryIntelligenceService(provider=FakeProviderFailure())
    result = service.interpret("llm_session", "Calculate SAVI.")
    assert result.provider == "deterministic_fallback"
    assert result.fallback_reason


def test_query_intelligence_handles_malformed_response():
    service = QueryIntelligenceService(provider=FakeProviderMalformed())
    result = service.interpret("llm_session", "Calculate NDVI.")
    assert result.provider == "deterministic_fallback"
    assert result.fallback_reason


def test_orchestrator_uses_llm_interpretation_when_available(geotiff_date1_path):
    from app.core.session_cache import session_manager

    session_manager.clear_all()
    session_manager.get_or_create_session("llm_orch")
    from app.pipeline.metadata import UniversalMetadataExtractor
    from app.pipeline.validator import UniversalImageValidator

    meta = UniversalMetadataExtractor.extract(geotiff_date1_path, category=UniversalImageValidator.validate(geotiff_date1_path).category)
    session_manager.add_image("llm_orch", geotiff_date1_path, meta)

    fake_provider = FakeProvider({
        "analysis_type": "ndvi",
        "image_selection": "first",
        "image_count_required": 1,
        "required_bands": [{"name": "red", "required": True, "default_index": 3}, {"name": "nir", "required": True, "default_index": 4}],
        "confidence": 0.99,
        "needs_clarification": False,
        "reasoning": "NDVI requested"
    })
    service = QueryIntelligenceService(provider=fake_provider)
    orchestrator = AnalysisOrchestrator(intelligence_service=service)
    response = orchestrator.orchestrate("llm_orch", "Calculate NDVI for this image.")
    assert response.execution.intent == "vegetation_analysis"
    assert response.execution.status in {"success", "partial", "failed"}
    assert response.execution.llm_interpretation is not None
    assert response.execution.llm_interpretation["analysis_type"] == "ndvi"


def test_orchestrate_analysis_degrades_to_deterministic_fallback_on_invalid_structured_response():
    fake_provider = FakeProviderMalformed()
    service = QueryIntelligenceService(provider=fake_provider)
    orchestrator = AnalysisOrchestrator(intelligence_service=service)
    response = orchestrator.orchestrate("missing_session", "Calculate NDBI.")
    assert response.execution.status == "failed"
    assert response.execution.llm_interpretation is not None
