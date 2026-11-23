from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic import ValidationError

from app.core.config import Settings, settings
from app.services.ai_service import AIService, ChatCompletionResult, get_ai_service, is_ai_available, is_using_gateway

pytestmark = pytest.mark.asyncio(scope="module")

AI = "app.services.ai_service"
MESSAGES = [{"role": "user", "content": "Hi"}]


def _svc(**attrs) -> AIService:
    AIService._instance = None
    with patch.object(AIService, "_initialize_provider", return_value=None):
        service = AIService()
    for name, value in attrs.items():
        setattr(service, name, value)
    return service


def _image_svc(*, b64_json=None, url=None, using_gateway: bool = False) -> AIService:
    svc = _svc(_client=MagicMock(), _using_gateway=using_gateway)
    svc._client.images.generate.return_value = MagicMock(data=[MagicMock(b64_json=b64_json, url=url)])
    return svc


def _chat_svc(content) -> AIService:
    svc = _svc(_client=MagicMock())
    svc._client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=content))]
    )
    return svc


def _usage(prompt: int, completion: int) -> MagicMock:
    return MagicMock(input_tokens=prompt, output_tokens=completion, total_tokens=prompt + completion)


def _agent_run(output: str, usage: MagicMock | None = None) -> MagicMock:
    result = MagicMock(output=output)
    if usage is None:
        result.usage.side_effect = Exception("usage failed")
    else:
        result.usage.return_value = usage
    return MagicMock(run=AsyncMock(return_value=result))


class TestSingletonPattern:
    def test_get_model_classmethod(self) -> None:
        assert _svc(_model="fake_model").get_model() == "fake_model"


def test_lmstudio_keeps_openai_client_for_image_generation(monkeypatch) -> None:
    """Changing chat to LM Studio must not disable direct OpenAI image generation."""
    monkeypatch.setattr(f"{AI}.settings.LMSTUDIO_BASE_URL", "http://localhost:1234/v1")
    monkeypatch.setattr(f"{AI}.settings.AI_MODEL", "local-model")
    monkeypatch.setattr(f"{AI}.settings.OPENAI_API_KEY", "sk-test-key")
    svc = _svc()
    with patch(f"{AI}.OpenAIChatModel"), patch("openai.Client") as client:
        svc._initialize_lmstudio()
    client.assert_called_once_with(api_key="sk-test-key")
    assert svc.client is client.return_value


class TestInitializationGateway:
    def test_gateway_skips_when_no_api_key(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.PYDANTIC_AI_GATEWAY_API_KEY", None)
        monkeypatch.setattr(f"{AI}.settings.AI_PROVIDER", "openai")
        svc = _svc(_model="should_stay")
        svc._initialize_gateway()
        assert svc._model == "should_stay"

    def test_gateway_handles_exception(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.PYDANTIC_AI_GATEWAY_API_KEY", "gw-test-key")
        monkeypatch.setattr(f"{AI}.settings.AI_PROVIDER", "openai")
        svc = _svc()
        with patch(f"{AI}.gateway_provider", side_effect=Exception("connection error")):
            svc._initialize_gateway()
        assert svc._model is None
        assert svc._using_gateway is False


class TestInitializationDirect:
    def test_direct_openai_initializes_model_and_client(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_PROVIDER", "openai")
        monkeypatch.setattr(f"{AI}.settings.OPENAI_API_KEY", "sk-test-key")
        monkeypatch.setattr(f"{AI}.settings.AI_MODEL", "gpt-4o")
        model, client = MagicMock(), MagicMock()
        svc = _svc()
        with (
            patch(f"{AI}.openai.Client", return_value=client),
            patch("pydantic_ai.providers.openai.OpenAIProvider", return_value=MagicMock()),
            patch(f"{AI}.OpenAIChatModel", return_value=model),
            patch(f"{AI}.warnings.warn") as warn,
        ):
            svc._initialize_direct_provider()
        assert svc._model is model
        assert svc._client is client
        warn.assert_called_once()
        assert "deprecated" in str(warn.call_args[0][0]).lower()

    def test_anthropic_provider_is_rejected(self) -> None:
        with pytest.raises(ValidationError, match="AI_PROVIDER"):
            Settings(**(settings.model_dump() | {"AI_PROVIDER": "anthropic"}))

    def test_legacy_anthropic_key_does_not_enable_ai(self) -> None:
        config = settings.model_dump() | {
            "AI_PROVIDER": "openai",
            "OPENAI_API_KEY": None,
            "PYDANTIC_AI_GATEWAY_API_KEY": None,
            "ANTHROPIC_API_KEY": "unused-legacy-key",
        }
        resolved = Settings(**config)
        assert resolved.ai_provider_mode == "disabled"
        assert resolved.effective_ai_mode(None) == "disabled"

    def test_direct_unknown_provider_logs_warning(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_PROVIDER", "ollama")
        with patch(f"{AI}.logger") as logger:
            _svc()._initialize_direct_provider()
        logger.warning.assert_called_once()


class TestInitializeProviderRouting:
    def test_routes_to_direct(self) -> None:
        svc = _svc()
        with patch(f"{AI}.settings") as mock_settings:
            mock_settings.ai_provider_mode = "direct"
            svc._initialize_direct_provider = MagicMock()
            svc._initialize_provider()
        svc._initialize_direct_provider.assert_called_once()

    def test_routes_to_disabled(self) -> None:
        with patch(f"{AI}.settings") as mock_settings, patch(f"{AI}.logger") as logger:
            mock_settings.ai_provider_mode = "disabled"
            _svc()._initialize_provider()
        logger.warning.assert_called_once()


class TestGenerateImage:
    async def test_generate_image_with_b64_json_return_bytes(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = _image_svc(b64_json="dGVzdA==")
        assert await svc.generate_image(prompt="test", return_bytes=True) == b"test"
        svc._client.images.generate.assert_called_once_with(
            model="gpt-image-1", prompt="test", size="1024x1024", quality="auto", n=1
        )

    async def test_generate_image_with_url_return_bytes(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = _image_svc(url="https://example.com/img.png")
        with patch(f"{AI}.image_url_to_bytes", return_value=b"fake_bytes"):
            assert await svc.generate_image(prompt="test", return_bytes=True) == b"fake_bytes"

    async def test_generate_image_url_fetch_fails(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = _image_svc(url="https://example.com/img.png")
        with (
            patch(f"{AI}.image_url_to_bytes", return_value=None),
            pytest.raises(RuntimeError, match="Failed to fetch image from URL"),
        ):
            await svc.generate_image(prompt="test", return_bytes=True)

    async def test_generate_image_no_data_return_bytes(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_IMAGE_MODEL", "gpt-image-1")
        with pytest.raises(RuntimeError, match="Failed to generate image"):
            await _image_svc().generate_image(prompt="test", return_bytes=True)

    async def test_generate_image_no_url_raises(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_IMAGE_MODEL", "gpt-image-1")
        with pytest.raises(RuntimeError, match="Image generation did not return a URL"):
            await _image_svc().generate_image(prompt="test")

    async def test_generate_image_rejects_invalid_size_for_model(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = _image_svc()
        with pytest.raises(RuntimeError, match="Invalid image size '512x512' for model gpt-image-1"):
            await svc.generate_image(prompt="test", size="512x512")
        svc._client.images.generate.assert_not_called()

    async def test_generate_image_accepts_model_specific_size(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_IMAGE_MODEL", "dall-e-3")
        svc = _image_svc(url="https://example.com/img.png")
        assert await svc.generate_image(prompt="test", size="1792x1024") == "https://example.com/img.png"
        svc._client.images.generate.assert_called_once_with(
            model="dall-e-3", prompt="test", size="1792x1024", quality="auto", n=1
        )

    async def test_generate_image_through_gateway_logs_debug(self, monkeypatch) -> None:
        monkeypatch.setattr(f"{AI}.settings.AI_IMAGE_MODEL", "gpt-image-1")
        svc = _image_svc(url="https://example.com/img.png", using_gateway=True)
        with patch(f"{AI}.logger") as logger:
            assert await svc.generate_image(prompt="test") == "https://example.com/img.png"
        logger.debug.assert_called_once()
        assert "Gateway" in logger.debug.call_args[0][0]


class TestGenerateAudio:
    async def test_generate_audio_propagates_exception(self) -> None:
        svc = _svc(_client=MagicMock())
        with (
            patch.object(svc, "_sync_generate_audio", side_effect=ValueError("TTS error")),
            pytest.raises(ValueError, match="TTS error"),
        ):
            await svc.generate_audio(text="Hello")

    async def test_generate_audio_through_gateway_logs_debug(self) -> None:
        svc = _svc(_client=MagicMock(), _using_gateway=True)
        with (
            patch.object(svc, "_sync_generate_audio", return_value=b"audio_data"),
            patch(f"{AI}.logger") as logger,
        ):
            await svc.generate_audio(text="Hello")
        logger.debug.assert_called_once()
        assert "Gateway" in logger.debug.call_args[0][0]

    def test_sync_generate_audio_calls_client(self) -> None:
        svc = _svc(_client=MagicMock())
        response = MagicMock()
        response.read.return_value = b"test_audio"
        svc._client.audio.speech.with_streaming_response.create.return_value.__enter__.return_value = response
        assert svc._sync_generate_audio("tts-1", "alloy", "Hello world") == b"test_audio"
        svc._client.audio.speech.with_streaming_response.create.assert_called_once_with(
            model="tts-1", voice="alloy", input="Hello world"
        )


class TestGenerateCompletion:
    async def test_generate_completion_success(self) -> None:
        svc = _chat_svc("Hello, world!")
        assert await svc.generate_completion(messages=MESSAGES) == "Hello, world!"
        svc._client.chat.completions.create.assert_called_once_with(model="gpt-3.5-turbo", messages=MESSAGES)

    async def test_generate_completion_empty_content_raises(self) -> None:
        with pytest.raises(RuntimeError, match="Failed to generate completion"):
            await _chat_svc(None).generate_completion(messages=MESSAGES)


class TestGenerateCompletionJson:
    async def test_generate_completion_json_success(self) -> None:
        svc = _chat_svc('{"key": "value"}')
        assert await svc.generate_completion_json(prompt="make json") == '{"key": "value"}'
        call = svc._client.chat.completions.create.call_args[1]
        assert call["model"] == "gpt-3.5-turbo"
        assert len(call["messages"]) == 2
        assert call["messages"][0]["role"] == "system"

    async def test_generate_completion_json_empty_content_raises(self) -> None:
        with pytest.raises(RuntimeError, match="Failed to generate JSON completion"):
            await _chat_svc(None).generate_completion_json(prompt="make json")


class TestGenerateSpeechFromText:
    async def test_generate_speech_from_text_success(self) -> None:
        svc = _svc(_client=MagicMock())
        response = svc._client.audio.speech.create.return_value
        result = await svc.generate_speech_from_text(text_input="Hello", speech_file_path="/tmp/speech.mp3")
        assert result == "/tmp/speech.mp3"
        svc._client.audio.speech.create.assert_called_once_with(model="tts-1", voice="echo", input="Hello")
        response.write_to_file.assert_called_once_with("/tmp/speech.mp3")


class TestTranscribeAudio:
    async def test_transcribe_audio_propagates_exception(self) -> None:
        svc = _svc(_client=MagicMock())
        svc._client.audio.transcriptions.create.side_effect = ValueError("Whisper error")
        with pytest.raises(ValueError, match="Whisper error"):
            await svc.transcribe_audio(audio_bytes=b"fake")

    async def test_transcribe_audio_raises_without_client(self) -> None:
        with pytest.raises(RuntimeError, match="OpenAI client not available"):
            await _svc(_client=None).transcribe_audio(audio_bytes=b"fake")

    async def test_transcribe_audio_through_gateway_logs_debug(self) -> None:
        svc = _svc(_client=MagicMock(), _using_gateway=True)
        svc._client.audio.transcriptions.create.return_value = "done"
        with patch(f"{AI}.logger") as logger:
            await svc.transcribe_audio(audio_bytes=b"fake")
        logger.debug.assert_called_once()
        assert "Gateway" in logger.debug.call_args[0][0]


class TestChatCompletion:
    async def test_chat_completion_delegates_to_with_usage(self) -> None:
        svc = _svc(_model=MagicMock())
        with patch("pydantic_ai.Agent") as agent_cls:
            agent_cls.return_value = _agent_run("Hello from agent", _usage(5, 7))
            assert await svc.chat_completion(messages=MESSAGES) == "Hello from agent"

    async def test_chat_completion_with_usage_uses_instructions(self) -> None:
        svc = _svc(_model=MagicMock())
        messages = [{"role": "system", "content": "You are helpful."}, *MESSAGES]
        with patch("pydantic_ai.Agent") as agent_cls:
            agent_cls.return_value = _agent_run("Response", _usage(10, 20))
            result = await svc.chat_completion_with_usage(messages=messages)
        assert (result.text, result.prompt_tokens, result.completion_tokens, result.total_tokens) == (
            "Response",
            10,
            20,
            30,
        )
        agent_cls.assert_called_once()
        assert agent_cls.call_args[1]["instructions"] == "You are helpful."

    async def test_chat_completion_with_usage_usage_extraction_fails(self) -> None:
        svc = _svc(_model=MagicMock())
        with patch("pydantic_ai.Agent") as agent_cls, patch(f"{AI}.logger") as logger:
            agent_cls.return_value = _agent_run("Response")
            result = await svc.chat_completion_with_usage(messages=MESSAGES)
        assert result.text == "Response"
        assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (None, None, None)
        logger.warning.assert_called_once()

    async def test_chat_completion_without_model_raises(self) -> None:
        with pytest.raises(RuntimeError, match="AI model not configured"):
            await _svc(_model=None).chat_completion_with_usage(messages=MESSAGES)


class TestModuleLevelFunctions:
    def test_get_ai_service_returns_singleton(self) -> None:
        AIService._instance = None
        svc = get_ai_service()
        assert isinstance(svc, AIService)
        assert svc is AIService()

    def test_is_ai_available_when_model_set(self) -> None:
        _svc(_model="fake_model")
        assert is_ai_available() is True

    def test_is_using_gateway_true(self) -> None:
        _svc(_using_gateway=True)
        assert is_using_gateway() is True


class TestChatCompletionResult:
    def test_default_values(self) -> None:
        result = ChatCompletionResult(text="test")
        assert result.text == "test"
        assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (None, None, None)

    def test_full_fields(self) -> None:
        result = ChatCompletionResult(text="hello", prompt_tokens=10, completion_tokens=20, total_tokens=30)
        assert result.text == "hello"
        assert (result.prompt_tokens, result.completion_tokens, result.total_tokens) == (10, 20, 30)
