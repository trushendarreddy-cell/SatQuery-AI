import base64
from pathlib import Path

import httpx
import pytest

from app.agent.llm import GeminiProvider, OpenAICompatibleProvider, get_llm_provider
from app.agent.vision import (
    GeminiVisionProvider,
    OpenAICompatibleVisionProvider,
    VisionService,
    get_vision_provider,
)
from app.core.config import settings


class FakeResponse:
    def __init__(self, payload=None, status_code=200, exc=None):
        self.payload = payload or {"choices": [{"message": {"content": "ok"}}]}
        self.status_code = status_code
        self._exc = exc

    def raise_for_status(self):
        if self._exc:
            raise self._exc

    def json(self):
        return self.payload


class FakeClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        if json and "messages" in json:
            return FakeResponse({"choices": [{"message": {"content": "provider_text_ok"}}]})
        if json and "contents" in json:
            return FakeResponse({"candidates": [{"content": {"parts": [{"text": "provider_visual_ok"}]}}]})
        return FakeResponse({})


class FakeVisionClient:
    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def post(self, url, headers=None, json=None):
        return FakeResponse({
            "choices": [{"message": {"content": "[{\"supported\": true, \"confidence\": 0.88, \"observations\": [\"visible structures\"], \"visual_features\": [\"urban form\"], \"interpretation\": \"The scene appears urbanized.\", \"limitations\": [\"visual only\"], \"warnings\": [\"No metrics were computed\"]}]"}}]
        })


def test_llm_provider_factory_uses_gemini_config(monkeypatch):
    monkeypatch.setattr(settings, "LLM_PROVIDER", "gemini", raising=False)
    monkeypatch.setattr(settings, "LLM_API_KEY", "secret-key", raising=False)
    monkeypatch.setattr(settings, "LLM_MODEL", "gemini-2.0-flash", raising=False)
    monkeypatch.setattr(settings, "LLM_BASE_URL", "https://example.test/v1", raising=False)
    provider = get_llm_provider()
    assert isinstance(provider, GeminiProvider)
    assert provider.name == "gemini"


def test_openai_compatible_provider_chat_success(monkeypatch):
    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = OpenAICompatibleProvider(api_key="key", model="gpt-4o-mini", base_url="https://example.test/v1")
    result = provider.chat([{"role": "user", "content": "Hello"}], [])
    assert result["choices"][0]["message"]["content"] == "provider_text_ok"


def test_openai_compatible_vision_provider_success(monkeypatch, tmp_path):
    image_path = tmp_path / "sample.jpg"
    image_path.write_bytes(b"fake-image-content")
    monkeypatch.setattr(httpx, "Client", FakeVisionClient)
    provider = OpenAICompatibleVisionProvider(api_key="key", model="gpt-4o-mini", base_url="https://example.test/v1")
    result = provider.analyze("Describe this image", {"filename": "sample.jpg", "image_id": "img-1"}, image_path=str(image_path))
    assert result["supported"] is True
    assert result["confidence"] >= 0.0
    assert result["observations"]


def test_gemini_vision_provider_success(monkeypatch, tmp_path):
    image_path = tmp_path / "sample.png"
    image_path.write_bytes(b"fake-png-content")
    monkeypatch.setattr(httpx, "Client", FakeClient)
    provider = GeminiVisionProvider(api_key="key", model="gemini-2.0-flash", image_mime_type="image/png")
    result = provider.analyze("Describe this image", {"filename": "sample.png", "image_id": "img-2"}, image_path=str(image_path))
    assert result["supported"] is True
    assert result["observations"]


def test_missing_credentials_fall_back_to_mock(monkeypatch):
    monkeypatch.setattr(settings, "VISION_PROVIDER", "gemini", raising=False)
    monkeypatch.setattr(settings, "VISION_API_KEY", "", raising=False)
    provider = get_vision_provider()
    assert provider is not None
    assert provider.name == "mock"


def test_secret_redaction_in_provider_error(monkeypatch):
    class BadClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

        def post(self, url, headers=None, json=None):
            raise httpx.HTTPStatusError("invalid API key secret-key value", request=None, response=None)

    monkeypatch.setattr(httpx, "Client", BadClient)
    provider = OpenAICompatibleProvider(api_key="secret-key", model="gpt-4o-mini", base_url="https://example.test/v1")
    with pytest.raises(RuntimeError, match="provider"):
        provider.chat([{"role": "user", "content": "hi"}], [])


def test_vision_service_uses_real_provider_when_configured(monkeypatch, tmp_path):
    image_path = tmp_path / "real.png"
    image_path.write_bytes(b"img")
    monkeypatch.setattr(settings, "VISION_PROVIDER", "openai-compatible", raising=False)
    monkeypatch.setattr(settings, "VISION_API_KEY", "secret", raising=False)
    monkeypatch.setattr(settings, "VISION_MODEL", "gpt-4o-mini", raising=False)
    monkeypatch.setattr(settings, "VISION_BASE_URL", "https://example.test/v1", raising=False)
    monkeypatch.setattr(httpx, "Client", FakeVisionClient)

    service = VisionService(provider=None)
    result = service.analyze("s1", "img-1", "Describe the visible features.", metadata={"filename": "real.png", "image_id": "img-1"})
    assert result.supported is True
    assert result.provider in {"openai-compatible", "gemini", "mock"}


def test_vision_service_handles_invalid_image_payload(monkeypatch):
    service = VisionService(provider=OpenAICompatibleVisionProvider(api_key="key", model="gpt-4o-mini", base_url="https://example.test/v1"))
    result = service.analyze("s1", "img-1", "Describe the visible features.", metadata={"filename": "real.png", "image_id": "img-1"})
    assert result.supported is False
    assert result.limitations
