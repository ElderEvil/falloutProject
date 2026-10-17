"""Tests for ElevenLabsTtsService — success, errors, is_enabled."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.exceptions import ElevenLabsProviderException

pytestmark = pytest.mark.asyncio


class TestIsEnabled:
    """Verify is_enabled reflects the API key config."""

    def test_enabled_when_key_set(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.elevenlabs_service import ElevenLabsTtsService

        monkeypatch.setattr("app.services.elevenlabs_service.settings.ELEVENLABS_API_KEY", "sk-abc123")
        svc = ElevenLabsTtsService()
        assert svc.is_enabled is True

    def test_disabled_when_key_empty(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.elevenlabs_service import ElevenLabsTtsService

        monkeypatch.setattr("app.services.elevenlabs_service.settings.ELEVENLABS_API_KEY", "")
        svc = ElevenLabsTtsService()
        assert svc.is_enabled is False

    def test_disabled_when_key_whitespace(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.elevenlabs_service import ElevenLabsTtsService

        monkeypatch.setattr("app.services.elevenlabs_service.settings.ELEVENLABS_API_KEY", "   ")
        svc = ElevenLabsTtsService()
        assert svc.is_enabled is False


class TestGenerateSpeech:
    """HTTP-level behaviour of generate_speech."""

    async def test_success_returns_bytes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.elevenlabs_service import ElevenLabsTtsService

        monkeypatch.setattr("app.services.elevenlabs_service.settings.ELEVENLABS_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.content = b"mp3-audio-bytes"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr("app.services.elevenlabs_service.httpx.AsyncClient", lambda *a, **k: mock_client)

        svc = ElevenLabsTtsService()
        result = await svc.generate_speech("Hello world")
        assert result == b"mp3-audio-bytes"

        mock_client.post.assert_called_once()
        call_args = mock_client.post.call_args
        assert "xi-api-key" in call_args.kwargs.get("headers", {})
        payload = call_args.kwargs["json"]
        assert payload["text"] == "Hello world"
        assert payload["model_settings"]["stability"] == 0.5
        assert payload["model_settings"]["similarity_boost"] == 0.75

    async def test_401_raises_provider_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.elevenlabs_service import ElevenLabsTtsService

        monkeypatch.setattr("app.services.elevenlabs_service.settings.ELEVENLABS_API_KEY", "bad-key")

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr("app.services.elevenlabs_service.httpx.AsyncClient", lambda *a, **k: mock_client)

        svc = ElevenLabsTtsService()
        with pytest.raises(ElevenLabsProviderException, match="API key is invalid"):
            await svc.generate_speech("test")

    async def test_429_raises_provider_exception(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.elevenlabs_service import ElevenLabsTtsService

        monkeypatch.setattr("app.services.elevenlabs_service.settings.ELEVENLABS_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "Rate limited"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr("app.services.elevenlabs_service.httpx.AsyncClient", lambda *a, **k: mock_client)

        svc = ElevenLabsTtsService()
        with pytest.raises(ElevenLabsProviderException, match="rate limit"):
            await svc.generate_speech("test")

    async def test_other_error_status_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.elevenlabs_service import ElevenLabsTtsService

        monkeypatch.setattr("app.services.elevenlabs_service.settings.ELEVENLABS_API_KEY", "test-key")

        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_response.text = "Internal error"
        mock_client = AsyncMock()
        mock_client.post = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        monkeypatch.setattr("app.services.elevenlabs_service.httpx.AsyncClient", lambda *a, **k: mock_client)

        svc = ElevenLabsTtsService()
        with pytest.raises(ElevenLabsProviderException, match="HTTP 500"):
            await svc.generate_speech("test")

    async def test_disabled_key_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from app.services.elevenlabs_service import ElevenLabsTtsService

        monkeypatch.setattr("app.services.elevenlabs_service.settings.ELEVENLABS_API_KEY", "")

        svc = ElevenLabsTtsService()
        with pytest.raises(ElevenLabsProviderException, match="not configured"):
            await svc.generate_speech("test")
