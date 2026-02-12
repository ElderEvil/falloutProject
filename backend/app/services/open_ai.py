"""AI service module that handles AI provider configuration lazily.

This module can be imported without API keys set - AI features will simply
not be available until a provider is configured.

Migration Guide:
    - New projects: Use PYDANTIC_AI_GATEWAY_API_KEY (recommended)
    - Existing projects: Direct provider keys still work but emit deprecation warnings
    - Set AI_PROVIDER to choose the upstream provider when using Gateway
"""

import asyncio
import logging
import warnings
from typing import Any, Optional, Self

import openai
from pydantic_ai.models.openai import OpenAIChatModel
from pydantic_ai.providers.gateway import gateway_provider

from app.core.config import settings
from app.utils.image_processing import image_url_to_bytes

logger = logging.getLogger(__name__)


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

        self._model: Optional[Any] = None
        self._client: Optional[openai.Client] = None
        self._using_gateway: bool = False

        self._initialize_provider()
        self._initialized = True

    def _initialize_provider(self) -> None:
        """Initialize AI provider based on configuration priority.

        Priority: 1. Gateway (recommended), 2. Direct (deprecated), 3. Ollama, 4. Disabled
        """
        mode = settings.ai_provider_mode

        match mode:
            case "gateway":
                self._initialize_gateway()
            case "direct":
                self._initialize_direct_provider()
            case "ollama":
                self._initialize_ollama()
            case "disabled":
                logger.warning("No AI provider configured. AI features disabled.")

    def _initialize_gateway(self) -> None:
        """Initialize using Pydantic AI Gateway (recommended approach)."""
        if not settings.PYDANTIC_AI_GATEWAY_API_KEY:
            return
        try:
            provider = gateway_provider(
                settings.AI_PROVIDER,
                api_key=settings.PYDANTIC_AI_GATEWAY_API_KEY,
            )
            self._model = OpenAIChatModel(
                model_name=settings.AI_MODEL,
                provider=provider,
            )
            self._using_gateway = True
            logger.info(f"AI initialized via Gateway ({settings.AI_PROVIDER}/{settings.AI_MODEL})")
            # For OpenAI-specific features, still need direct client
            if settings.OPENAI_API_KEY:
                self._client = openai.Client(api_key=settings.OPENAI_API_KEY)
        except Exception:
            logger.exception("Failed to initialize Gateway")
            self._model = None
            self._using_gateway = False

    def _initialize_direct_provider(self) -> None:
        """Initialize using direct provider API keys (deprecated)."""
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

                    provider = OpenAIProvider(api_key=settings.OPENAI_API_KEY)
                    self._model = OpenAIChatModel(model_name=settings.AI_MODEL, provider=provider)
                    logger.warning("AI initialized with direct OpenAI API (deprecated)")
            case "anthropic":
                if settings.ANTHROPIC_API_KEY:
                    # Anthropic direct access - use Gateway instead for better compatibility
                    logger.error(
                        "Direct Anthropic API access requires Pydantic AI Gateway. "
                        "Set PYDANTIC_AI_GATEWAY_API_KEY to use Anthropic models."
                    )
            case _:
                logger.warning(f"Direct provider mode does not support: {settings.AI_PROVIDER}")

    def _initialize_ollama(self) -> None:
        """Initialize using local Ollama instance."""
        if settings.OLLAMA_BASE_URL:
            self._model = OpenAIChatModel(model_name=settings.AI_MODEL, provider="ollama")
            logger.info(f"AI initialized with Ollama ({settings.AI_MODEL})")

    @property
    def model(self) -> Optional[Any]:
        """Get the AI model, or None if not configured."""
        return self._model

    @classmethod
    def get_model(cls) -> Optional[Any]:
        """Get the AI model class method (for backward compatibility)."""
        return cls().model

    @property
    def client(self) -> Optional[openai.Client]:
        """Get the OpenAI client, or None if not configured."""
        return self._client

    @property
    def using_gateway(self) -> bool:
        """Check if using Pydantic AI Gateway."""
        return self._using_gateway

    def is_available(self) -> bool:
        """Check if AI features are available."""
        return self._model is not None

    def _ensure_model_available(self) -> None:
        """Raise if model is not available."""
        if self._model is None:
            raise RuntimeError("AI model not configured. Set AI_PROVIDER and required API keys.")

    def _ensure_client_available(self) -> None:
        """Raise if client is not available (required for image/audio operations)."""
        if self._client is None:
            raise RuntimeError("OpenAI client not available. Use AI_PROVIDER=openai for image/audio features.")

    async def generate_image(self, *, prompt: str, return_bytes: bool = False) -> str | bytes:
        """Generate an image using DALL-E."""
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
        response = await asyncio.to_thread(
            self._client.images.generate, model="dall-e-3", prompt=prompt, size="1024x1024", quality="standard", n=1
        )
        url = response.data[0].url
        if url is None:
            raise RuntimeError("Failed to generate image: no URL returned")
        return await image_url_to_bytes(url) if return_bytes else url

    async def generate_audio(self, text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
        """Generate audio from text using OpenAI's TTS API."""
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
        try:
            with self._client.audio.speech.with_streaming_response.create(
                model=model,
                voice=voice,
                input=text,
            ) as response:
                return response.read()
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
        response.stream_to_file(speech_file_path)
        return speech_file_path

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Transcribe audio to text using Whisper."""
        self._ensure_client_available()
        if self._client is None:
            raise RuntimeError("OpenAI client not available")
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
        """Generate chat completion using the configured AI provider and model."""
        self._ensure_model_available()
        if self._model is None:
            raise RuntimeError("AI model not configured")
        from pydantic_ai import Agent

        system_prompt = None
        user_messages = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "user":
                user_messages.append(msg["content"])

        user_input = "\n".join(user_messages) if user_messages else ""

        agent = Agent(model=self._model, system_prompt=system_prompt) if system_prompt else Agent(model=self._model)
        result = await agent.run(user_input)
        return result.output


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
