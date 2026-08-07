"""Tests for AI service (open_ai.py) — provider initialization, all public methods, error paths.

Mocks all external dependencies (OpenAI, Pydantic AI Gateway, Agent, etc.)
to avoid real network calls. Uses singleton reset between test groups.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.asyncio(scope="module")

from app.services.open_ai import (  # noqa: E402
    AIService,
    ChatCompletionResult,
    get_ai_service,
    get_model,
    is_ai_available,
    is_using_gateway,
)

# ============================================================================
# Helpers — reset singleton state and create fresh uninitialized instances
# ============================================================================


def reset_singleton() -> None:
    """Reset AIService singleton before each test that needs a fresh instance."""
    AIService._instance = None


def _make_fresh_service(*, skip_init: bool = True) -> AIService:
    """Create a fresh AIService without triggering _initialize_provider.

    Since __init__ calls _initialize_provider() which tries to connect to real
    providers, we mock _initialize_provider to a no-op during construction.
    """
    reset_singleton()
    if skip_init:
        with patch.object(AIService, "_initialize_provider", return_value=None):
            svc = AIService()
    else:
        svc = AIService()
    return svc


# ============================================================================
# Singleton & Basic Properties
# ============================================================================


@pytest.mark.asyncio
class TestSingletonPattern:
    """Tests for singleton pattern, properties, and initialization gating."""

    def test_returns_same_instance(self) -> None:
        reset_singleton()
        with patch.object(AIService, "_initialize_provider", return_value=None):
            x = AIService()
            y = AIService()
            assert x is y

    def test_initialized_flag_prevents_reinit(self) -> None:
        """__init__ skips re-initialization if _initialized is True."""
        svc = _make_fresh_service()
        svc._initialized = True
        svc._model = MagicMock()
        # Call __init__ again; should not reset _model
        AIService.__init__(svc)
        assert svc._model is not None  # unchanged

    def test_get_model_classmethod(self) -> None:
        """get_model() class method returns model property."""
        svc = _make_fresh_service()
        svc._model = "fake_model"
        assert svc.get_model() == "fake_model"

    def test_model_property_none_by_default(self) -> None:
        """model returns None when not configured (init skipped)."""
        svc = _make_fresh_service()
        assert svc.model is None

    def test_client_property_none_by_default(self) -> None:
        """client returns None when not configured (init skipped)."""
        svc = _make_fresh_service()
        assert svc.client is None

    def test_using_gateway_false_by_default(self) -> None:
        """using_gateway returns False when not configured (init skipped)."""
        svc = _make_fresh_service()
        assert svc.using_gateway is False


# ============================================================================
# is_available / ensure_* guards
# ============================================================================


@pytest.mark.asyncio
class TestAvailabilityGuards:
    """Tests for is_available, _ensure_model_available, _ensure_client_available."""

    def test_is_available_true_when_model_set(self) -> None:
        svc = _make_fresh_service()
        svc._model = "some_model"
        assert svc.is_available() is True

    def test_is_available_false_when_model_none(self) -> None:
        svc = _make_fresh_service()
        svc._model = None
        assert svc.is_available() is False

    def test_ensure_model_available_raises_when_none(self) -> None:
        svc = _make_fresh_service()
        svc._model = None
        with pytest.raises(RuntimeError, match="AI model not configured"):
            svc._ensure_model_available()

    def test_ensure_model_available_passes_when_set(self) -> None:
        svc = _make_fresh_service()
        svc._model = "some_model"
        svc._ensure_model_available()

    def test_ensure_client_available_raises_when_none(self) -> None:
        svc = _make_fresh_service()
        svc._client = None
        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            svc._ensure_client_available()

    def test_ensure_client_available_passes_when_set(self) -> None:
        svc = _make_fresh_service()
        svc._client = MagicMock()
        svc._ensure_client_available()


# ============================================================================
# Provider Initialization — Disabled
# ============================================================================


@pytest.mark.asyncio
class TestInitializationDisabled:
    """Tests for disabled provider mode."""

    def test_disabled_mode_logs_warning(self) -> None:
        svc = _make_fresh_service()
        with (
            patch("app.services.open_ai.settings") as mock_settings,
            patch("app.services.open_ai.logger") as mock_logger,
        ):
            mock_settings.ai_provider_mode = "disabled"
            svc._initialize_provider()
            mock_logger.warning.assert_called_once()


# ============================================================================
# Provider Initialization — Gateway
# ============================================================================


@pytest.mark.asyncio
class TestInitializationGateway:
    """Tests for gateway provider initialization."""

    def test_gateway_initializes_model_and_client(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.PYDANTIC_AI_GATEWAY_API_KEY", "gw-test-key")
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "openai")
        monkeypatch.setattr("app.services.open_ai.settings.AI_MODEL", "gpt-4o")
        monkeypatch.setattr("app.services.open_ai.settings.OPENAI_API_KEY", "sk-test-key")

        mock_provider = MagicMock()
        mock_model = MagicMock()
        mock_client = MagicMock()

        svc = _make_fresh_service()
        with (
            patch("app.services.open_ai.gateway_provider", return_value=mock_provider) as mock_gw_provider,
            patch("app.services.open_ai.OpenAIChatModel", return_value=mock_model) as mock_chat_model,
            patch("app.services.open_ai.openai.Client", return_value=mock_client) as mock_openai_client,
        ):
            svc._initialize_gateway()
            assert svc._model is mock_model
            assert svc._client is mock_client
            assert svc._using_gateway is True
            mock_gw_provider.assert_called_once_with("openai", api_key="gw-test-key")
            mock_chat_model.assert_called_once_with(model_name="gpt-4o", provider=mock_provider)
            mock_openai_client.assert_called_once_with(api_key="sk-test-key")

    def test_gateway_skips_when_no_api_key(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.PYDANTIC_AI_GATEWAY_API_KEY", None)
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "openai")
        svc = _make_fresh_service()
        svc._model = "should_stay"
        svc._initialize_gateway()
        assert svc._model == "should_stay"

    def test_gateway_handles_exception(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.PYDANTIC_AI_GATEWAY_API_KEY", "gw-test-key")
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "openai")
        svc = _make_fresh_service()
        with patch("app.services.open_ai.gateway_provider", side_effect=Exception("connection error")):
            svc._initialize_gateway()
            assert svc._model is None
            assert svc._using_gateway is False


# ============================================================================
# Provider Initialization — Direct (Deprecated)
# ============================================================================


@pytest.mark.asyncio
class TestInitializationDirect:
    """Tests for direct provider initialization (deprecated path)."""

    def test_direct_openai_initializes_model_and_client(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "openai")
        monkeypatch.setattr("app.services.open_ai.settings.OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr("app.services.open_ai.settings.AI_MODEL", "gpt-4o")

        mock_provider = MagicMock()
        mock_model = MagicMock()
        mock_client = MagicMock()

        svc = _make_fresh_service()
        with (
            patch("app.services.open_ai.openai.Client", return_value=mock_client),
            patch("pydantic_ai.providers.openai.OpenAIProvider", return_value=mock_provider),
            patch("app.services.open_ai.OpenAIChatModel", return_value=mock_model),
            patch("app.services.open_ai.warnings.warn") as mock_warn,
        ):
            svc._initialize_direct_provider()
            assert svc._model is mock_model
            assert svc._client is mock_client
            mock_warn.assert_called_once()
            assert "deprecated" in str(mock_warn.call_args[0][0]).lower()

    def test_direct_openai_without_key_skips(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "openai")
        monkeypatch.setattr("app.services.open_ai.settings.OPENAI_API_KEY", None)
        svc = _make_fresh_service()
        svc._initialize_direct_provider()
        assert svc._model is None
        assert svc._client is None

    def test_direct_anthropic_with_key_raises(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "anthropic")
        monkeypatch.setattr("app.services.open_ai.settings.ANTHROPIC_API_KEY", "sk-ant-test")
        svc = _make_fresh_service()
        with pytest.raises(RuntimeError, match="Direct Anthropic API access is not supported"):
            svc._initialize_direct_provider()

    def test_direct_anthropic_without_key_logs_warning(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "anthropic")
        monkeypatch.setattr("app.services.open_ai.settings.ANTHROPIC_API_KEY", None)
        svc = _make_fresh_service()
        with patch("app.services.open_ai.logger") as mock_logger:
            svc._initialize_direct_provider()
            mock_logger.warning.assert_called_once()

    def test_direct_unknown_provider_logs_warning(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "ollama")
        svc = _make_fresh_service()
        with patch("app.services.open_ai.logger") as mock_logger:
            svc._initialize_direct_provider()
            mock_logger.warning.assert_called_once()

    def test_direct_provider_emits_deprecation_warning(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_PROVIDER", "openai")
        monkeypatch.setattr("app.services.open_ai.settings.OPENAI_API_KEY", None)
        svc = _make_fresh_service()
        with pytest.warns(DeprecationWarning, match="Direct provider API keys are deprecated"):
            svc._initialize_direct_provider()


# ============================================================================
# Provider Initialization — Ollama
# ============================================================================


@pytest.mark.asyncio
class TestInitializationOllama:
    """Tests for Ollama provider initialization."""

    def test_ollama_initializes_model(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.OLLAMA_BASE_URL", "http://localhost:11434/v1")
        monkeypatch.setattr("app.services.open_ai.settings.AI_MODEL", "llama2")

        mock_provider = MagicMock()
        mock_model = MagicMock()

        svc = _make_fresh_service()
        with (
            patch("pydantic_ai.providers.ollama.OllamaProvider", return_value=mock_provider),
            patch("app.services.open_ai.OpenAIChatModel", return_value=mock_model),
        ):
            svc._initialize_ollama()
            assert svc._model is mock_model

    def test_ollama_without_url_skips(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.OLLAMA_BASE_URL", "")
        svc = _make_fresh_service()
        svc._initialize_ollama()
        assert svc._model is None


# ============================================================================
# Provider Initialization — Routing (_initialize_provider)
# ============================================================================


@pytest.mark.asyncio
class TestInitializeProviderRouting:
    """Tests that _initialize_provider routes to the correct sub-initializer."""

    def test_routes_to_gateway(self) -> None:
        svc = _make_fresh_service()
        with patch("app.services.open_ai.settings") as mock_settings:
            mock_settings.ai_provider_mode = "gateway"
            svc._initialize_gateway = MagicMock()
            svc._initialize_provider()
            svc._initialize_gateway.assert_called_once()

    def test_routes_to_direct(self) -> None:
        svc = _make_fresh_service()
        with patch("app.services.open_ai.settings") as mock_settings:
            mock_settings.ai_provider_mode = "direct"
            svc._initialize_direct_provider = MagicMock()
            svc._initialize_provider()
            svc._initialize_direct_provider.assert_called_once()

    def test_routes_to_ollama(self) -> None:
        svc = _make_fresh_service()
        with patch("app.services.open_ai.settings") as mock_settings:
            mock_settings.ai_provider_mode = "ollama"
            svc._initialize_ollama = MagicMock()
            svc._initialize_provider()
            svc._initialize_ollama.assert_called_once()

    def test_routes_to_disabled(self) -> None:
        svc = _make_fresh_service()
        with (
            patch("app.services.open_ai.settings") as mock_settings,
            patch("app.services.open_ai.logger") as mock_logger,
        ):
            mock_settings.ai_provider_mode = "disabled"
            svc._initialize_provider()
            mock_logger.warning.assert_called_once()


# ============================================================================
# generate_image
# ============================================================================


@pytest.mark.asyncio
class TestGenerateImage:
    """Tests for generate_image method."""

    @staticmethod
    def _make_svc_with_client(using_gateway: bool = False) -> AIService:
        svc = _make_fresh_service()
        svc._client = MagicMock()
        svc._using_gateway = using_gateway
        return svc

    async def test_generate_image_with_b64_json_return_bytes(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = self._make_svc_with_client()

        mock_data = MagicMock()
        mock_data.b64_json = "dGVzdA=="
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        svc._client.images.generate.return_value = mock_response

        result = await svc.generate_image(prompt="test", return_bytes=True)
        assert result == b"test"
        svc._client.images.generate.assert_called_once_with(
            model="gpt-image-1", prompt="test", size="1024x1024", quality="auto", n=1
        )

    async def test_generate_image_with_url_return_bytes(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = self._make_svc_with_client()

        mock_data = MagicMock()
        mock_data.b64_json = None
        mock_data.url = "https://example.com/img.png"
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        svc._client.images.generate.return_value = mock_response

        with patch("app.services.open_ai.image_url_to_bytes", return_value=b"fake_bytes"):
            result = await svc.generate_image(prompt="test", return_bytes=True)
            assert result == b"fake_bytes"

    async def test_generate_image_url_fetch_fails(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = self._make_svc_with_client()

        mock_data = MagicMock()
        mock_data.b64_json = None
        mock_data.url = "https://example.com/img.png"
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        svc._client.images.generate.return_value = mock_response

        with (
            patch("app.services.open_ai.image_url_to_bytes", return_value=None),
            pytest.raises(RuntimeError, match="Failed to fetch image from URL"),
        ):
            await svc.generate_image(prompt="test", return_bytes=True)

    async def test_generate_image_no_data_return_bytes(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = self._make_svc_with_client()

        mock_data = MagicMock()
        mock_data.b64_json = None
        mock_data.url = None
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        svc._client.images.generate.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to generate image"):
            await svc.generate_image(prompt="test", return_bytes=True)

    async def test_generate_image_returns_url(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = self._make_svc_with_client()

        mock_data = MagicMock()
        mock_data.url = "https://example.com/img.png"
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        svc._client.images.generate.return_value = mock_response

        result = await svc.generate_image(prompt="test")
        assert result == "https://example.com/img.png"

    async def test_generate_image_no_url_raises(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = self._make_svc_with_client()

        mock_data = MagicMock()
        mock_data.url = None
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        svc._client.images.generate.return_value = mock_response

        with pytest.raises(RuntimeError, match="Image generation did not return a URL"):
            await svc.generate_image(prompt="test")

    async def test_generate_image_raises_without_client(self) -> None:
        svc = _make_fresh_service()
        svc._client = None
        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            await svc.generate_image(prompt="test")

    async def test_generate_image_through_gateway_logs_debug(self, monkeypatch) -> None:
        monkeypatch.setattr("app.services.open_ai.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = self._make_svc_with_client(using_gateway=True)

        mock_data = MagicMock()
        mock_data.url = "https://example.com/img.png"
        mock_response = MagicMock()
        mock_response.data = [mock_data]
        svc._client.images.generate.return_value = mock_response

        with patch("app.services.open_ai.logger") as mock_logger:
            result = await svc.generate_image(prompt="test")
            assert result == "https://example.com/img.png"
            mock_logger.debug.assert_called_once()
            assert "Gateway" in mock_logger.debug.call_args[0][0]


# ============================================================================
# generate_audio
# ============================================================================


@pytest.mark.asyncio
class TestGenerateAudio:
    """Tests for generate_audio method."""

    @staticmethod
    def _make_svc_with_client(using_gateway: bool = False) -> AIService:
        svc = _make_fresh_service()
        svc._client = MagicMock()
        svc._using_gateway = using_gateway
        return svc

    async def test_generate_audio_success(self) -> None:
        svc = self._make_svc_with_client()
        with patch.object(svc, "_sync_generate_audio", return_value=b"audio_data"):
            result = await svc.generate_audio(text="Hello", voice="alloy", model="tts-1")
            assert result == b"audio_data"

    async def test_generate_audio_uses_defaults(self) -> None:
        svc = self._make_svc_with_client()
        with patch.object(svc, "_sync_generate_audio", return_value=b"audio_data") as mock_sync:
            result = await svc.generate_audio(text="Hello")
            assert result == b"audio_data"
            mock_sync.assert_called_once_with("tts-1", "alloy", "Hello")

    async def test_generate_audio_propagates_exception(self) -> None:
        svc = self._make_svc_with_client()
        with (
            patch.object(svc, "_sync_generate_audio", side_effect=ValueError("TTS error")),
            pytest.raises(ValueError, match="TTS error"),
        ):
            await svc.generate_audio(text="Hello")

    async def test_generate_audio_raises_without_client(self) -> None:
        svc = _make_fresh_service()
        svc._client = None
        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            await svc.generate_audio(text="Hello")

    async def test_generate_audio_through_gateway_logs_debug(self) -> None:
        svc = self._make_svc_with_client(using_gateway=True)
        with (
            patch.object(svc, "_sync_generate_audio", return_value=b"audio_data"),
            patch("app.services.open_ai.logger") as mock_logger,
        ):
            await svc.generate_audio(text="Hello")
            mock_logger.debug.assert_called_once()
            assert "Gateway" in mock_logger.debug.call_args[0][0]

    def test_sync_generate_audio_calls_client(self) -> None:
        svc = self._make_svc_with_client()
        mock_response = MagicMock()
        mock_response.read.return_value = b"test_audio"
        mock_ctx = MagicMock()
        mock_ctx.__enter__.return_value = mock_response
        svc._client.audio.speech.with_streaming_response.create.return_value = mock_ctx

        result = svc._sync_generate_audio("tts-1", "alloy", "Hello world")
        assert result == b"test_audio"
        svc._client.audio.speech.with_streaming_response.create.assert_called_once_with(
            model="tts-1", voice="alloy", input="Hello world"
        )


# ============================================================================
# generate_completion
# ============================================================================


@pytest.mark.asyncio
class TestGenerateCompletion:
    """Tests for generate_completion method."""

    @staticmethod
    def _make_svc_with_client() -> AIService:
        svc = _make_fresh_service()
        svc._client = MagicMock()
        return svc

    async def test_generate_completion_success(self) -> None:
        svc = self._make_svc_with_client()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello, world!"
        svc._client.chat.completions.create.return_value = mock_response

        result = await svc.generate_completion(messages=[{"role": "user", "content": "Hi"}])
        assert result == "Hello, world!"
        svc._client.chat.completions.create.assert_called_once_with(
            model="gpt-3.5-turbo", messages=[{"role": "user", "content": "Hi"}]
        )

    async def test_generate_completion_empty_content_raises(self) -> None:
        svc = self._make_svc_with_client()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        svc._client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to generate completion"):
            await svc.generate_completion(messages=[{"role": "user", "content": "Hi"}])

    async def test_generate_completion_raises_without_client(self) -> None:
        svc = _make_fresh_service()
        svc._client = None
        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            await svc.generate_completion(messages=[])


# ============================================================================
# generate_completion_json
# ============================================================================


@pytest.mark.asyncio
class TestGenerateCompletionJson:
    """Tests for generate_completion_json method."""

    @staticmethod
    def _make_svc_with_client() -> AIService:
        svc = _make_fresh_service()
        svc._client = MagicMock()
        return svc

    async def test_generate_completion_json_success(self) -> None:
        svc = self._make_svc_with_client()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"key": "value"}'
        svc._client.chat.completions.create.return_value = mock_response

        result = await svc.generate_completion_json(prompt="make json")
        assert result == '{"key": "value"}'
        call_args = svc._client.chat.completions.create.call_args
        assert call_args[1]["model"] == "gpt-3.5-turbo"
        assert len(call_args[1]["messages"]) == 2
        assert call_args[1]["messages"][0]["role"] == "system"

    async def test_generate_completion_json_empty_content_raises(self) -> None:
        svc = self._make_svc_with_client()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None
        svc._client.chat.completions.create.return_value = mock_response

        with pytest.raises(RuntimeError, match="Failed to generate JSON completion"):
            await svc.generate_completion_json(prompt="make json")

    async def test_generate_completion_json_raises_without_client(self) -> None:
        svc = _make_fresh_service()
        svc._client = None
        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            await svc.generate_completion_json(prompt="make json")


# ============================================================================
# generate_speech_from_text
# ============================================================================


@pytest.mark.asyncio
class TestGenerateSpeechFromText:
    """Tests for generate_speech_from_text method."""

    @staticmethod
    def _make_svc_with_client() -> AIService:
        svc = _make_fresh_service()
        svc._client = MagicMock()
        return svc

    async def test_generate_speech_from_text_success(self) -> None:
        svc = self._make_svc_with_client()
        mock_response = MagicMock()
        svc._client.audio.speech.create.return_value = mock_response

        result = await svc.generate_speech_from_text(text_input="Hello", speech_file_path="/tmp/speech.mp3")
        assert result == "/tmp/speech.mp3"
        svc._client.audio.speech.create.assert_called_once_with(model="tts-1", voice="echo", input="Hello")
        mock_response.stream_to_file.assert_called_once_with("/tmp/speech.mp3")

    async def test_generate_speech_from_text_raises_without_client(self) -> None:
        svc = _make_fresh_service()
        svc._client = None
        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            await svc.generate_speech_from_text(text_input="Hello", speech_file_path="/tmp/speech.mp3")


# ============================================================================
# transcribe_audio
# ============================================================================


@pytest.mark.asyncio
class TestTranscribeAudio:
    """Tests for transcribe_audio method."""

    @staticmethod
    def _make_svc_with_client(using_gateway: bool = False) -> AIService:
        svc = _make_fresh_service()
        svc._client = MagicMock()
        svc._using_gateway = using_gateway
        return svc

    async def test_transcribe_audio_string_response(self) -> None:
        svc = self._make_svc_with_client()
        svc._client.audio.transcriptions.create.return_value = "  Hello world  "

        result = await svc.transcribe_audio(audio_bytes=b"fake_audio")
        assert result == "Hello world"

    async def test_transcribe_audio_object_response(self) -> None:
        svc = self._make_svc_with_client()
        mock_text = MagicMock()
        mock_text.text = "  Transcribed text  "
        svc._client.audio.transcriptions.create.return_value = mock_text

        result = await svc.transcribe_audio(audio_bytes=b"fake_audio")
        assert result == "Transcribed text"

    async def test_transcribe_audio_custom_filename(self) -> None:
        svc = self._make_svc_with_client()
        svc._client.audio.transcriptions.create.return_value = "done"

        with patch("io.BytesIO") as mock_bytesio:
            mock_bytesio_instance = MagicMock()
            mock_bytesio.return_value = mock_bytesio_instance
            await svc.transcribe_audio(audio_bytes=b"fake", filename="custom.wav")
            mock_bytesio.assert_called_once_with(b"fake")
            assert mock_bytesio_instance.name == "custom.wav"

    async def test_transcribe_audio_propagates_exception(self) -> None:
        svc = self._make_svc_with_client()
        svc._client.audio.transcriptions.create.side_effect = ValueError("Whisper error")

        with pytest.raises(ValueError, match="Whisper error"):
            await svc.transcribe_audio(audio_bytes=b"fake")

    async def test_transcribe_audio_raises_without_client(self) -> None:
        svc = _make_fresh_service()
        svc._client = None
        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            await svc.transcribe_audio(audio_bytes=b"fake")

    async def test_transcribe_audio_through_gateway_logs_debug(self) -> None:
        svc = self._make_svc_with_client(using_gateway=True)
        svc._client.audio.transcriptions.create.return_value = "done"

        with patch("app.services.open_ai.logger") as mock_logger:
            await svc.transcribe_audio(audio_bytes=b"fake")
            mock_logger.debug.assert_called_once()
            assert "Gateway" in mock_logger.debug.call_args[0][0]


# ============================================================================
# chat_completion / chat_completion_with_usage
# ============================================================================


@pytest.mark.asyncio
class TestChatCompletion:
    """Tests for chat_completion and chat_completion_with_usage methods."""

    @staticmethod
    def _make_svc_with_model() -> AIService:
        svc = _make_fresh_service()
        svc._model = MagicMock()
        return svc

    async def test_chat_completion_delegates_to_with_usage(self) -> None:
        svc = self._make_svc_with_model()
        mock_agent_result = MagicMock()
        mock_agent_result.output = "Hello from agent"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 5
        mock_usage.output_tokens = 7
        mock_usage.total_tokens = 12
        mock_agent_result.usage.return_value = mock_usage

        with patch("pydantic_ai.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent_cls.return_value = mock_agent

            result = await svc.chat_completion(messages=[{"role": "user", "content": "Hi"}])
            assert result == "Hello from agent"

    async def test_chat_completion_with_usage_system_prompt(self) -> None:
        svc = self._make_svc_with_model()
        mock_agent_result = MagicMock()
        mock_agent_result.output = "Response"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 10
        mock_usage.output_tokens = 20
        mock_usage.total_tokens = 30
        mock_agent_result.usage.return_value = mock_usage

        with patch("pydantic_ai.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent_cls.return_value = mock_agent

            result = await svc.chat_completion_with_usage(
                messages=[
                    {"role": "system", "content": "You are helpful."},
                    {"role": "user", "content": "Hi"},
                ]
            )
            assert result.text == "Response"
            assert result.prompt_tokens == 10
            assert result.completion_tokens == 20
            assert result.total_tokens == 30
            mock_agent_cls.assert_called_once()
            assert mock_agent_cls.call_args[1]["system_prompt"] == "You are helpful."

    async def test_chat_completion_with_usage_no_system_prompt(self) -> None:
        svc = self._make_svc_with_model()
        mock_agent_result = MagicMock()
        mock_agent_result.output = "Response"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 5
        mock_usage.output_tokens = 6
        mock_usage.total_tokens = 11
        mock_agent_result.usage.return_value = mock_usage

        with patch("pydantic_ai.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent_cls.return_value = mock_agent

            result = await svc.chat_completion_with_usage(messages=[{"role": "user", "content": "Hi"}])
            assert result.text == "Response"
            assert "system_prompt" not in mock_agent_cls.call_args[1]

    async def test_chat_completion_with_usage_usage_extraction_fails(self) -> None:
        svc = self._make_svc_with_model()
        mock_agent_result = MagicMock()
        mock_agent_result.output = "Response"
        mock_agent_result.usage.side_effect = Exception("usage failed")

        with (
            patch("pydantic_ai.Agent") as mock_agent_cls,
            patch("app.services.open_ai.logger") as mock_logger,
        ):
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent_cls.return_value = mock_agent

            result = await svc.chat_completion_with_usage(messages=[{"role": "user", "content": "Hi"}])
            assert result.text == "Response"
            assert result.prompt_tokens is None
            assert result.completion_tokens is None
            assert result.total_tokens is None
            mock_logger.warning.assert_called_once()

    async def test_chat_completion_without_model_raises(self) -> None:
        svc = _make_fresh_service()
        svc._model = None
        with pytest.raises(RuntimeError, match="AI model not configured"):
            await svc.chat_completion_with_usage(messages=[{"role": "user", "content": "Hi"}])

    async def test_chat_completion_with_usage_empty_messages(self) -> None:
        svc = self._make_svc_with_model()
        mock_agent_result = MagicMock()
        mock_agent_result.output = ""
        mock_usage = MagicMock()
        mock_usage.input_tokens = 0
        mock_usage.output_tokens = 0
        mock_usage.total_tokens = 0
        mock_agent_result.usage.return_value = mock_usage

        with patch("pydantic_ai.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent_cls.return_value = mock_agent

            result = await svc.chat_completion_with_usage(messages=[])
            assert result.text == ""

    async def test_chat_completion_with_usage_multiple_user_messages(self) -> None:
        svc = self._make_svc_with_model()
        mock_agent_result = MagicMock()
        mock_agent_result.output = "Combined"
        mock_usage = MagicMock()
        mock_usage.input_tokens = 3
        mock_usage.output_tokens = 4
        mock_usage.total_tokens = 7
        mock_agent_result.usage.return_value = mock_usage

        with patch("pydantic_ai.Agent") as mock_agent_cls:
            mock_agent = MagicMock()
            mock_agent.run = AsyncMock(return_value=mock_agent_result)
            mock_agent_cls.return_value = mock_agent

            await svc.chat_completion_with_usage(
                messages=[
                    {"role": "user", "content": "First"},
                    {"role": "user", "content": "Second"},
                ]
            )
            mock_agent.run.assert_called_once_with("First\nSecond")


# ============================================================================
# Module-level helper functions
# ============================================================================


@pytest.mark.asyncio
class TestModuleLevelFunctions:
    """Tests for module-level functions that wrap the singleton."""

    def test_get_ai_service_returns_singleton(self) -> None:
        reset_singleton()
        svc = get_ai_service()
        assert isinstance(svc, AIService)
        assert svc is AIService()

    def test_is_ai_available_when_model_set(self) -> None:
        svc = _make_fresh_service()
        svc._model = "fake_model"
        assert is_ai_available() is True

    def test_is_ai_available_when_model_none(self) -> None:
        svc = _make_fresh_service()
        svc._model = None
        assert is_ai_available() is False

    def test_get_model_returns_singleton_model(self) -> None:
        svc = _make_fresh_service()
        svc._model = "test_model"
        assert get_model() == "test_model"

    def test_get_model_returns_none(self) -> None:
        svc = _make_fresh_service()
        svc._model = None
        assert get_model() is None

    def test_is_using_gateway_true(self) -> None:
        svc = _make_fresh_service()
        svc._using_gateway = True
        assert is_using_gateway() is True

    def test_is_using_gateway_false(self) -> None:
        svc = _make_fresh_service()
        svc._using_gateway = False
        assert is_using_gateway() is False


# ============================================================================
# ChatCompletionResult dataclass
# ============================================================================


class TestChatCompletionResult:
    """Tests for the ChatCompletionResult dataclass."""

    def test_default_values(self) -> None:
        """ChatCompletionResult defaults token fields to None."""
        result = ChatCompletionResult(text="test")
        assert result.text == "test"
        assert result.prompt_tokens is None
        assert result.completion_tokens is None
        assert result.total_tokens is None

    def test_full_fields(self) -> None:
        """ChatCompletionResult stores all fields."""
        result = ChatCompletionResult(
            text="hello",
            prompt_tokens=10,
            completion_tokens=20,
            total_tokens=30,
        )
        assert result.text == "hello"
        assert result.prompt_tokens == 10
        assert result.completion_tokens == 20
        assert result.total_tokens == 30
