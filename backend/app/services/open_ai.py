"""AI service module that handles AI provider configuration lazily.

This module can be imported without API keys set - AI features will simply
not be available until a provider is configured.
"""

import logging
from typing import Any, Optional

import openai
from pydantic_ai.models.openai import OpenAIChatModel

from app.core.config import settings
from app.utils.image_processing import image_url_to_bytes

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI operations. Lazily initialized with provider config.

    All methods check if AI is available and raise RuntimeError if not.
    """

    _instance: Optional["AIService"] = None

    def __new__(cls) -> "AIService":
        """Singleton pattern to ensure single model/client instance."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize if not already done."""
        if getattr(self, "_initialized", False):
            return

        self._model: Optional[OpenAIChatModel] = None
        self._client: Optional[openai.Client] = None

        # Try to initialize based on provider
        match settings.AI_PROVIDER:
            case "openai":
                if settings.OPENAI_API_KEY:
                    self._client = openai.Client(api_key=settings.OPENAI_API_KEY)
                    self._model = OpenAIChatModel(
                        model_name=settings.AI_MODEL,
                        provider=openai.OpenAIProvider(api_key=settings.OPENAI_API_KEY),  # type: ignore
                    )
                else:
                    logger.warning("OPENAI_API_KEY not set, AI features will be disabled")
            case "anthropic":
                if settings.ANTHROPIC_API_KEY:
                    self._model = OpenAIChatModel(
                        model_name=settings.AI_MODEL,
                        provider=openai.AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY),  # type: ignore
                    )
                else:
                    logger.warning("ANTHROPIC_API_KEY not set, AI features will be disabled")
            case "ollama":
                if settings.OLLAMA_BASE_URL:
                    self._model = OpenAIChatModel(
                        model_name=settings.AI_MODEL,
                        provider=openai.LitellmProvider(base_url=settings.OLLAMA_BASE_URL),  # type: ignore
                    )
                else:
                    logger.warning("OLLAMA_BASE_URL not set, AI features will be disabled")
            case _:
                logger.warning(f"Unsupported AI provider: {settings.AI_PROVIDER}, AI features will be disabled")

        self._initialized = True

    @property
    def model(self) -> Optional[OpenAIChatModel]:
        """Get the AI model, or None if not configured."""
        return self._model

    @property
    def client(self) -> Optional[openai.Client]:
        """Get the OpenAI client, or None if not configured."""
        return self._client

    def is_available(self) -> bool:
        """Check if AI features are available."""
        return self._model is not None and self._client is not None

    def _ensure_available(self) -> None:
        """Raise if AI is not available."""
        if not self.is_available():
            raise RuntimeError("AI not configured. Set OPENAI_API_KEY or another provider.")

    async def generate_image(self, *, prompt: str, return_bytes: bool = False) -> str | bytes:
        """Generate an image using DALL-E."""
        self._ensure_available()
        assert self._client is not None
        response = self._client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1024",
            quality="standard",
            n=1,
        )
        url = response.data[0].url
        assert url is not None
        result = await image_url_to_bytes(url) if return_bytes else url
        assert result is not None
        return result

    async def generate_audio(self, text: str, voice: str = "alloy", model: str = "tts-1") -> bytes:
        """Generate audio from text using OpenAI's TTS API."""
        self._ensure_available()
        assert self._client is not None
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
        self._ensure_available()
        assert self._client is not None
        response = self._client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[cast(Any, m) for m in messages],
        )
        content = response.choices[0].message.content
        assert content is not None
        return content

    async def generate_completion_json(self, prompt: str) -> str:
        """Generate a JSON-formatted completion."""
        self._ensure_available()
        assert self._client is not None
        response = self._client.chat.completions.create(
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
        assert content is not None
        return content

    async def generate_speech_from_text(self, text_input: str, speech_file_path: str) -> str:
        """Generate speech from text and save to file."""
        self._ensure_available()
        assert self._client is not None
        response = self._client.audio.speech.create(
            model="tts-1",
            voice="echo",
            input=text_input,
        )
        response.stream_to_file(speech_file_path)
        return speech_file_path

    async def transcribe_audio(self, audio_bytes: bytes, filename: str = "audio.webm") -> str:
        """Transcribe audio to text using Whisper."""
        self._ensure_available()
        assert self._client is not None
        try:
            from io import BytesIO

            audio_file = BytesIO(audio_bytes)
            audio_file.name = filename

            response = self._client.audio.transcriptions.create(
                model="whisper-1", file=audio_file, response_format="text"
            )
            return response.strip() if isinstance(response, str) else response.text.strip()
        except Exception as e:
            err_msg = f"Error transcribing audio: {e}"
            logger.exception(err_msg)
            raise

    async def chat_completion(self, messages: list[dict[str, str]]) -> str:
        """Generate chat completion using the configured AI provider and model."""
        self._ensure_available()
        assert self._model is not None
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


def get_model() -> OpenAIChatModel | None:
    """Get the AI model, or None if not configured."""
    return AIService().model


def cast(_type: Any, value: Any) -> Any:
    """Type cast helper."""
    return value
