"""AI service module that handles AI provider configuration lazily.

This module can be imported without API keys set - AI features will simply
not be available until a provider is configured.

Migration Guide:
    - New projects: Use PYDANTIC_AI_GATEWAY_API_KEY (recommended)
    - Existing projects: Direct provider keys still work but emit deprecation warnings
    - Set AI_PROVIDER to choose the upstream provider when using Gateway

Architecture Notes:
    - Chat/Text: Uses PydanticAI Gateway when PYDANTIC_AI_GATEWAY_API_KEY is set
    - Image (DALL-E): Uses direct OpenAI client (Gateway ImageGenerationTool requires Agent pattern)
    - Audio (TTS/Whisper): Uses direct OpenAI client (Gateway does not support OpenAI native audio APIs)
    - For image/audio: Set both PYDANTIC_AI_GATEWAY_API_KEY AND OPENAI_API_KEY for full functionality
"""

import asyncio
import base64
import logging
import warnings
from dataclasses import dataclass
from typing import Any, Optional, Self

import openai
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.gateway import gateway_provider

from app.core.config import settings
from app.utils.image_processing import image_url_to_bytes

logger = logging.getLogger(__name__)


@dataclass
class ChatCompletionResult:
    text: str
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class AIService:
    """Service for AI operations. Lazily initialized with provider config.

    Supports Pydantic AI Gateway (recommended) and legacy direct provider access.
    All methods check if AI is available and raise RuntimeError if not.
    """

    _instance: Optional["AIService"] = None

    def __new__(cls) -> Self:
        """Singleton pattern to ensure single model/client instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize if not already done."""
        if getattr(self, "_initialized", False):
            return

        self._model: Any | None = None
        self._client: openai.Client | None = None
        self._using_gateway: bool = False

        self._initialize_provider()
        self._initialized = True

    def _initialize_provider(
        self, mode: str | None = None, base_url: str | None = None
    ) -> None:
        """Initialize AI provider based on configuration priority.

        Priority: 1. Gateway (recommended), 2. Direct (deprecated), 3. Ollama, 4. LM Studio, 5. Disabled

        Args:
            mode: Optional forced mode (used by ``reconfigure`` when the DB
                profile forces a local provider). Defaults to ``settings.ai_provider_mode``.
            base_url: Optional base URL override forwarded to the gateway and
                direct provider initializers.
        """
        mode = mode or settings.ai_provider_mode

        match mode:
            case "gateway":
                self._initialize_gateway(base_url=base_url)
            case "direct":
                self._initialize_direct_provider(base_url=base_url)
            case "ollama":
                self._initialize_ollama()
            case "lmstudio":
                self._initialize_lmstudio()
            case "disabled":
                logger.warning("No AI provider configured. AI features disabled.")

    def _initialize_gateway(self, base_url: str | None = None) -> None:
        """Initialize using Pydantic AI Gateway (recommended approach).

        Args:
            base_url: Optional Gateway proxy URL override (defaults to
                ``PYDANTIC_AI_GATEWAY_BASE_URL``).
        """
        if not settings.PYDANTIC_AI_GATEWAY_API_KEY:
            return
        try:
            gateway_options = {"api_key": settings.PYDANTIC_AI_GATEWAY_API_KEY}
            if settings.PYDANTIC_AI_GATEWAY_ROUTE:
                gateway_options["route"] = settings.PYDANTIC_AI_GATEWAY_ROUTE
            gateway_base_url = base_url or settings.PYDANTIC_AI_GATEWAY_BASE_URL
            if gateway_base_url:
                gateway_options["base_url"] = gateway_base_url
            provider = gateway_provider(settings.AI_PROVIDER, **gateway_options)
            self._model = OpenAIChatModel(
                model_name=settings.AI_MODEL,
                provider=provider,
            )
            self._using_gateway = True
            route_suffix = f" via {settings.PYDANTIC_AI_GATEWAY_ROUTE}" if settings.PYDANTIC_AI_GATEWAY_ROUTE else ""
            logger.info(f"AI initialized via Gateway ({settings.AI_PROVIDER}/{settings.AI_MODEL}){route_suffix}")
            # For OpenAI-specific features, still need direct client
            if settings.OPENAI_API_KEY:
                self._client = openai.Client(api_key=settings.OPENAI_API_KEY)
        except Exception:
            logger.exception("Failed to initialize Gateway")
            self._model = None
            self._using_gateway = False

    def _initialize_direct_provider(self, base_url: str | None = None) -> None:
        """Initialize using direct provider API keys (deprecated).

        Args:
            base_url: Optional OpenAI-compatible base URL override.
        """
        warnings.warn(
            "Direct provider API keys are deprecated. Use PYDANTIC_AI_GATEWAY_API_KEY.",
            DeprecationWarning,
            stacklevel=3,
        )
        match settings.AI_PROVIDER:
            case "openai":
                if settings.OPENAI_API_KEY:
                    self._client = openai.Client(api_key=settings.OPENAI_API_KEY)
                    from pydantic_ai.providers.openai import OpenAIProvider

                    provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY, base_url=base_url)
                    self._model = OpenAIChatModel(model_name=settings.AI_MODEL, provider=provider)
                    logger.warning("AI initialized with direct OpenAI API (deprecated)")
            case "anthropic":
                if settings.ANTHROPIC_API_KEY:
                    # Anthropic direct access - use Gateway instead for better compatibility
                    raise RuntimeError(
                        f"Direct Anthropic API access is not supported. "
                        f"AI_PROVIDER={settings.AI_PROVIDER} requires Pydantic AI Gateway. "
                        f"Set PYDANTIC_AI_GATEWAY_API_KEY to use Anthropic models, "
                        f"or switch to a supported provider (AI_PROVIDER=openai, ollama)."
                    )
                logger.warning(
                    "Direct provider mode does not support: %s. AI features will be disabled.",
                    settings.AI_PROVIDER,
                )
            case _:
                logger.warning(
                    "Direct provider mode does not support: %s. AI features will be disabled.",
                    settings.AI_PROVIDER,
                )

    def _initialize_ollama(self) -> None:
        """Initialize using local Ollama instance."""
        if settings.OLLAMA_BASE_URL:
            from pydantic_ai.providers.ollama import OllamaProvider

            provider = OllamaProvider(base_url=settings.OLLAMA_BASE_URL)
            self._model = OpenAIChatModel(model_name=settings.AI_MODEL, provider=provider)
            logger.info(f"AI initialized with Ollama ({settings.AI_MODEL}) at {settings.OLLAMA_BASE_URL}")

    def _initialize_lmstudio(self) -> None:
        """Initialize using local LM Studio instance (OpenAI-compatible)."""
        if settings.LMSTUDIO_BASE_URL:
            from pydantic_ai.providers.openai import OpenAIProvider

            provider = OpenAIProvider(base_url=settings.LMSTUDIO_BASE_URL, api_key="lm-studio")
            self._model = OpenAIChatModel(model_name=settings.AI_MODEL, provider=provider)
            logger.info(f"AI initialized with LM Studio ({settings.AI_MODEL}) at {settings.LMSTUDIO_BASE_URL}")

    @property
    def model(self) -> Any | None:
        """Get the AI model, or None if not configured."""
        return self._model

    @classmethod
    def get_model(cls) -> Any | None:
        """Get the AI model class method (for backward compatibility)."""
        return cls().model

    @property
    def client(self) -> openai.Client | None:
        """Get the OpenAI client, or None if not configured."""
        return self._client

    @property
    def using_gateway(self) -> bool:
        """Check if using Pydantic AI Gateway."""
        return self._using_gateway

    def is_available(self) -> bool:
        """Check if AI features are available."""
        return self._model is not None

    def reconfigure(
        self,
        *,
        provider: str | None = None,
        model: str | None = None,
        base_url: str | None = None,
        gateway_route: str | None = None,
    ) -> bool:
        """Re-initialize from effective values (profile overrides env).

        Temporarily patches the settings attributes that ``_initialize_provider``
        and its sub-initializers read, then restores them. Returns True if the
        model is available after reconfiguration.
        """
        overrides: dict[str, Any] = {}
        if provider is not None:
            overrides["AI_PROVIDER"] = provider
        if model is not None:
            overrides["AI_MODEL"] = model
        if base_url is not None:
            eff_provider = provider if provider is not None else settings.AI_PROVIDER
            if eff_provider == "ollama":
                overrides["OLLAMA_BASE_URL"] = base_url
            elif eff_provider == "lmstudio":
                overrides["LMSTUDIO_BASE_URL"] = base_url
            else:
                # Gateway (and direct OpenAI) honor a custom base URL.
                overrides["PYDANTIC_AI_GATEWAY_BASE_URL"] = base_url
        if gateway_route is not None:
            overrides["PYDANTIC_AI_GATEWAY_ROUTE"] = gateway_route

        self._model = None
        self._client = None
        self._using_gateway = False

        saved = {key: getattr(settings, key) for key in overrides}
        for key, val in overrides.items():
            setattr(settings, key, val)
        try:
            forced_mode: str | None = None
            if provider == "lmstudio" and (base_url or settings.LMSTUDIO_BASE_URL):
                forced_mode = "lmstudio"
            elif provider == "ollama" and (base_url or settings.OLLAMA_BASE_URL):
                forced_mode = "ollama"
            self._initialize_provider(mode=forced_mode, base_url=base_url)
        except Exception:
            logger.exception("Failed to reconfigure AI service")
            self._model = None
        finally:
            for key, val in saved.items():
                setattr(settings, key, val)

        return self._model is not None

    def _ensure_model_available(self) -> None:
        """Raise if model is not available."""
        if self._model is None:
            raise RuntimeError("AI model not configured. Set AI_PROVIDER and required API keys.")

    def _ensure_client_available(self) -> None:
        """Raise if client is not available (required for image/audio operations)."""
        if self._client is None:
            raise RuntimeError("OpenAI client not available. Use AI_PROVIDER=openai for image/audio features.")

    async def generate_image(self, *, prompt: str, return_bytes: bool = False, size: str = "1024x1024") -> str | bytes:
        """Generate an image using OpenAI's image model.

        Uses the configured AI_IMAGE_MODEL (default: gpt-image-1) and the
        requested ``size`` (defaults to square; e.g. "1536x1024" for landscape).
        Falls back to URL-based fetching for legacy model responses, but the new
        gpt-image-* models return b64_json directly.

        Note: Image generation uses direct OpenAI client, not Gateway.
        Gateway's ImageGenerationTool requires Agent pattern which is incompatible
        with the current service architecture. Set OPENAI_API_KEY for image features.
        """
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
        if self._using_gateway:
            logger.debug("Image generation via direct OpenAI client (Gateway doesn't support image API)")

        self._validate_image_size(size)

        response = await asyncio.to_thread(
            self._client.images.generate,
            model=settings.AI_IMAGE_MODEL,
            prompt=prompt,
            size=size,
            quality="auto",
            n=1,
        )
        data = response.data[0]

        if return_bytes:
            if data.b64_json:
                return base64.b64decode(data.b64_json)
            if data.url:
                result = await image_url_to_bytes(data.url)
                if result is None:
                    raise RuntimeError("Failed to fetch image from URL")
                return result
            raise RuntimeError("Failed to generate image: no image data returned")

        if data.url:
            return data.url
        msg = "Image generation did not return a URL. Use return_bytes=True to receive image data as bytes."
        raise RuntimeError(msg)

    @staticmethod
    def _validate_image_size(size: str) -> None:
        """Reject sizes the configured model does not accept before calling OpenAI.

        gpt-image-* supports the square/landscape/portrait set (plus "auto");
        DALL-E 3 uses the 1792 variants; DALL-E 2 uses small squares.
        """
        model = settings.AI_IMAGE_MODEL.lower()
        if model.startswith("gpt-image"):
            valid = {"1024x1024", "1536x1024", "1024x1536", "auto"}
        elif model == "dall-e-3":
            valid = {"1024x1024", "1792x1024", "1024x1792"}
        elif model == "dall-e-2":
            valid = {"256x256", "512x512", "1024x1024"}
        else:
            valid = {"1024x1024"}
        if size not in valid:
            raise RuntimeError(
                f"Invalid image size {size!r} for model {settings.AI_IMAGE_MODEL}; supported sizes: {', '.join(sorted(valid))}"
            )

    def _sync_generate_audio(self, model: str, voice: str, text: str) -> bytes:
        with self._client.audio.speech.with_streaming_response.create(
            model=model,
            voice=voice,
            input=text,
        ) as response:
            return response.read()

    async def generate_audio(self, text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
        """Generate audio from text using OpenAI's TTS API via direct client.

        Note: Audio generation uses direct OpenAI client, not Gateway.
        Gateway does not support OpenAI's native TTS API. Set OPENAI_API_KEY for audio features.
        """
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
        if self._using_gateway:
            logger.debug("Audio generation via direct OpenAI client (Gateway doesn't support TTS API)")
        try:
            return await asyncio.to_thread(self._sync_generate_audio, model, voice, text)
        except Exception as e:
            err_msg = f"Error generating audio from text: {e}"
            logger.exception(err_msg)
            raise

    async def generate_completion(self, messages: list[dict[str, str]]) -> str:
        """Generate a chat completion."""
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model="gpt-3.5-turbo",
            messages=messages,
        )
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Failed to generate completion: no content returned")
        return content

    async def generate_completion_json(self, prompt: str) -> str:
        """Generate a JSON-formatted completion."""
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
        response = await asyncio.to_thread(
            self._client.chat.completions.create,
            model="gpt-3.5-turbo",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are a helpful assistant. "
                        "You must assist the user in generating a response to the following prompt in JSON format."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
        )
        content = response.choices[0].message.content
        if content is None:
            raise RuntimeError("Failed to generate JSON completion: no content returned")
        return content

    async def generate_speech_from_text(self, text_input: str, speech_file_path: str) -> str:
        """Generate speech from text and save to file."""
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
        response = await asyncio.to_thread(
            self._client.audio.speech.create,
            model="tts-1",
            voice="echo",
            input=text_input,
        )
        await asyncio.to_thread(response.stream_to_file, speech_file_path)
        return speech_file_path

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Transcribe audio to text using Whisper via direct OpenAI client.

        Note: Audio transcription uses direct OpenAI client, not Gateway.
        Gateway does not support OpenAI's native Whisper API. Set OPENAI_API_KEY for transcription.
        """
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
        if self._using_gateway:
            logger.debug("Audio transcription via direct OpenAI client (Gateway doesn't support Whisper API)")
        try:
            from io import BytesIO

            audio_file = BytesIO(audio_bytes)
            audio_file.name = filename

            response = await asyncio.to_thread(
                self._client.audio.transcriptions.create,
                model="whisper-1",
                file=audio_file,
                response_format="text",
            )
            return response.strip() if isinstance(response, str) else response.text.strip()
        except Exception as e:
            err_msg = f"Error transcribing audio: {e}"
            logger.exception(err_msg)
            raise

    async def chat_completion(self, messages: list[dict[str, str]]) -> str:
        result = await self.chat_completion_with_usage(messages)
        return result.text

    async def chat_completion_with_usage(self, messages: list[dict[str, str]]) -> ChatCompletionResult:
        self._ensure_model_available()
        if self._model is None:
            raise RuntimeError("AI model not configured")
        from pydantic_ai import Agent

        instructions = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                instructions = msg["content"]
            elif msg["role"] == "user":
                user_messages.append(msg["content"])

        user_input = "\n".join(user_messages) if user_messages else ""

        agent = Agent(model=self._model, instructions=instructions) if instructions else Agent(model=self._model)
        result = await agent.run(user_input)

        try:
            usage = result.usage()
            prompt_tokens = usage.input_tokens
            completion_tokens = usage.output_tokens
            total_tokens = usage.total_tokens
        except Exception:
            logger.warning("Failed to extract usage info from AI service result")
            prompt_tokens = None
            completion_tokens = None
            total_tokens = None

        return ChatCompletionResult(
            text=result.output,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )


def get_ai_service() -> AIService:
    """Get the AI service singleton instance."""
    return AIService()


def is_ai_available() -> bool:
    """Check if AI features are available."""
    return AIService().is_available()


def get_model() -> Any | None:
    """Get the AI model, or None if not configured."""
    return AIService().model


def is_using_gateway() -> bool:
    """Check if Pydantic AI Gateway is being used."""
    return AIService().using_gateway


def build_test_model(
    provider: str,
    model: str,
    base_url: str | None,
    gateway_route: str | None,
    mode: str,
) -> Any | None:
    try:
        match mode:
            case "gateway":
                if not settings.PYDANTIC_AI_GATEWAY_API_KEY:
                    return None
                gateway_options = {"api_key": settings.PYDANTIC_AI_GATEWAY_API_KEY}
                if gateway_route:
                    gateway_options["route"] = gateway_route
                gateway_base_url = base_url or settings.PYDANTIC_AI_GATEWAY_BASE_URL
                if gateway_base_url:
                    gateway_options["base_url"] = gateway_base_url
                provider_obj = gateway_provider(provider, **gateway_options)
                return OpenAIChatModel(model_name=model, provider=provider_obj)
            case "direct":
                if provider == "openai" and settings.OPENAI_API_KEY:
                    from pydantic_ai.providers.openai import OpenAIProvider

                    provider_obj = OpenAIProvider(api_key=settings.OPENAI_API_KEY, base_url=base_url)
                    return OpenAIChatModel(model_name=model, provider=provider_obj)
                return None
            case "ollama":
                if base_url:
                    from pydantic_ai.providers.ollama import OllamaProvider

                    provider_obj = OllamaProvider(base_url=base_url)
                    return OpenAIChatModel(model_name=model, provider=provider_obj)
                return None
            case "lmstudio":
                if base_url:
                    from pydantic_ai.providers.openai import OpenAIProvider

                    provider_obj = OpenAIProvider(base_url=base_url, api_key="lm-studio")
                    return OpenAIChatModel(model_name=model, provider=provider_obj)
                return None
    except Exception:
        logger.exception("Failed to build one-off AI model")
    return None
