import json

import pytest

from app.agent.vision import VisionService


class FakeVisionProvider:
    def __init__(self, payload=None, error=None):
        self.payload = payload or {
            "supported": True,
            "confidence": 0.92,
            "observations": ["Dense built-up clusters appear around the central area."],
            "visual_features": ["built-up blocks", "road network", "vegetation patches"],
            "interpretation": "The image suggests urban expansion around the center with vegetation fragments remaining.",
            "limitations": ["This is a visual interpretation only."],
            "warnings": ["No quantitative index was computed."],
        }
        self.error = error
        self.name = "fake"

    def analyze(self, query, image_context, metadata=None):
        if self.error:
            raise RuntimeError(self.error)
        return self.payload


class FakeMalformedVisionProvider(FakeVisionProvider):
    def __init__(self):
        super().__init__({"unexpected": "value"})


def make_image_context(filename="sample.jpg", modality="visual_standard", has_geospatial=False):
    return {
        "image_id": "img_001",
        "filename": filename,
        "modality": modality,
        "width": 1024,
        "height": 768,
        "channels": 3,
        "has_geospatial_metadata": has_geospatial,
        "acquisition_date": "2025-01-15",
        "geospatial": None,
        "visual": {"color_mode": "RGB", "channel_count": 3, "bit_depth": 8},
    }


def test_vision_service_successful_visual_interpretation():
    service = VisionService(provider=FakeVisionProvider())
    result = service.analyze(
        session_id="s1",
        image_id="img_001",
        query="Are there visible signs of urban expansion?",
        metadata=make_image_context(),
    )

    assert result.supported is True
    assert result.confidence > 0.0
    assert result.observations
    assert result.interpretation
    assert result.provider == "fake"


def test_vision_service_rejects_invalid_image_context():
    service = VisionService(provider=FakeVisionProvider())
    result = service.analyze(
        session_id="missing_session",
        image_id="missing_img",
        query="What is visible here?",
        metadata=None,
    )

    assert result.supported is False
    assert result.limitations
    assert "image context" in " ".join(result.limitations).lower()


def test_vision_service_handles_malformed_provider_response():
    service = VisionService(provider=FakeMalformedVisionProvider())
    result = service.analyze(
        session_id="s1",
        image_id="img_001",
        query="What is visible?",
        metadata=make_image_context(),
    )

    assert result.supported is False
    assert result.limitations
    assert result.provider == "fake"


def test_vision_service_handles_provider_unavailable_and_timeout():
    service = VisionService(provider=FakeVisionProvider(error="provider unavailable"))
    result = service.analyze(
        session_id="s1",
        image_id="img_001",
        query="Describe the visible features.",
        metadata=make_image_context(),
    )

    assert result.supported is False
    assert result.limitations
    assert result.warnings


def test_vision_service_uses_mock_provider_when_no_provider_configured(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.LLM_API_KEY", "", raising=False)
    service = VisionService(provider=None)
    result = service.analyze(
        session_id="s1",
        image_id="img_001",
        query="What features are visible?",
        metadata=make_image_context(),
    )

    assert result.supported is True
    assert result.provider in {"mock", "deterministic_fallback"}


def test_agent_tool_analyze_image_visually_registers_and_runs():
    from app.agent.tools import invoke_agent_tool
    from app.agent.schemas import AgentToolCall
    from app.core.session_cache import session_manager

    session_manager.clear_all()
    session = session_manager.get_or_create_session("s1")
    session.images["img_001"] = type("Meta", (), {
        "image_id": "img_001",
        "filename": "sample.jpg",
        "modality": "visual_standard",
        "has_geospatial_metadata": False,
        "width": 1024,
        "height": 768,
        "channels": 3,
        "acquisition_date": "2025-01-15",
        "geospatial": None,
        "visual": {"color_mode": "RGB", "channel_count": 3, "bit_depth": 8},
        "model_dump": lambda self: {
            "image_id": "img_001",
            "filename": "sample.jpg",
            "modality": "visual_standard",
            "has_geospatial_metadata": False,
            "width": 1024,
            "height": 768,
            "channels": 3,
            "acquisition_date": "2025-01-15",
            "geospatial": None,
            "visual": {"color_mode": "RGB", "channel_count": 3, "bit_depth": 8},
        },
    })()

    call = AgentToolCall(
        tool_name="analyze_image_visually",
        arguments={
            "session_id": "s1",
            "image_id": "img_001",
            "query": "Are there visible signs of urban expansion?",
        },
    )
    result = invoke_agent_tool(call)

    assert result.status.value == "success"
    assert result.result["success"] is True
    assert "visual" in str(result.result).lower()


def test_orchestrator_appends_visual_reasoning_when_query_is_visual():
    from app.pipeline.orchestrator import AnalysisOrchestrator
    from app.core.session_cache import session_manager

    session_manager.clear_all()
    session = session_manager.get_or_create_session("vision_session")
    session.images["img_001"] = type("Meta", (), {
        "image_id": "img_001",
        "filename": "sample.jpg",
        "modality": "visual_standard",
        "has_geospatial_metadata": False,
        "width": 1024,
        "height": 768,
        "channels": 3,
        "acquisition_date": "2025-01-15",
        "geospatial": None,
        "visual": {"color_mode": "RGB", "channel_count": 3, "bit_depth": 8},
        "model_dump": lambda self: {
            "image_id": "img_001",
            "filename": "sample.jpg",
            "modality": "visual_standard",
            "has_geospatial_metadata": False,
            "width": 1024,
            "height": 768,
            "channels": 3,
            "acquisition_date": "2025-01-15",
            "geospatial": None,
            "visual": {"color_mode": "RGB", "channel_count": 3, "bit_depth": 8},
        },
    })()

    response = AnalysisOrchestrator().orchestrate("vision_session", "What is visible in this image?")

    assert response.execution is not None
    assert response.execution.visual_reasoning is not None
    assert response.execution.visual_reasoning["supported"] in {True, False}


def test_orchestrator_still_works_when_vision_is_unavailable():
    from app.pipeline.orchestrator import AnalysisOrchestrator
    from app.core.session_cache import session_manager

    session_manager.clear_all()
    session = session_manager.get_or_create_session("vision_session_2")
    session.images["img_001"] = type("Meta", (), {
        "image_id": "img_001",
        "filename": "sample.jpg",
        "modality": "visual_standard",
        "has_geospatial_metadata": False,
        "width": 1024,
        "height": 768,
        "channels": 3,
        "acquisition_date": "2025-01-15",
        "geospatial": None,
        "visual": {"color_mode": "RGB", "channel_count": 3, "bit_depth": 8},
        "model_dump": lambda self: {
            "image_id": "img_001",
            "filename": "sample.jpg",
            "modality": "visual_standard",
            "has_geospatial_metadata": False,
            "width": 1024,
            "height": 768,
            "channels": 3,
            "acquisition_date": "2025-01-15",
            "geospatial": None,
            "visual": {"color_mode": "RGB", "channel_count": 3, "bit_depth": 8},
        },
    })()

    org = AnalysisOrchestrator()
    response = org.orchestrate("vision_session_2", "Get the image metadata.")

    assert response.execution.status in {"success", "partial", "failed"}
    assert response.execution.visual_reasoning is None or response.execution.visual_reasoning.get("supported") is False
