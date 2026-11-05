"""OpenRouter HeyGen TTS provider — mirrors ElevenLabsTtsService shape."""

import io
import logging
import wave

import httpx

from app.core.config import settings
from app.utils.exceptions import TTSProviderException

logger = logging.getLogger(__name__)

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/audio/speech"
DEFAULT_MODEL = "heygen/heygen-voice-1-turbo:free"
DEFAULT_VOICE = "weston"


def _pcm_to_wav(pcm_data: bytes) -> bytes:
    """Wrap raw PCM (s16le, mono, 44100 Hz) into a WAV file using stdlib only."""
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # 16-bit
        wf.setframerate(44100)
        wf.writeframes(pcm_data)
    return buf.getvalue()


class OpenRouterTtsService:
    """Thin async wrapper around OpenRouter HeyGen text-to-speech REST API.

    Returns WAV bytes (wrapping the provider's PCM response) so callers
    don't need to handle PCM directly.
    """

    @property
    def is_enabled(self) -> bool:
        """True when an OpenRouter API key is configured."""
        return bool(settings.OPENROUTER_API_KEY.strip())

    async def generate_speech(self, text: str) -> bytes:
        """Generate speech audio via OpenRouter HeyGen and return WAV bytes.

        Args:
            text: The line to speak.

        Raises:
            TTSProviderException: On HTTP or transport errors from the API.
        """
        if not self.is_enabled:
            raise TTSProviderException(detail="OpenRouter TTS is not configured")

        headers = {
            "Authorization": f"Bearer {settings.OPENROUTER_API_KEY.strip()}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": DEFAULT_MODEL,
            "input": text,
            "voice": DEFAULT_VOICE,
            "response_format": "pcm",
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError as e:
            logger.warning("OpenRouter TTS transport error: %s", e)
            raise TTSProviderException(detail=f"OpenRouter unreachable: {e}") from e

        if response.status_code == 401:
            raise TTSProviderException(detail="OpenRouter API key is invalid")
        if response.status_code == 429:
            raise TTSProviderException(detail="OpenRouter rate limit exceeded")
        if response.status_code != 200:
            body = response.text[:200]
            logger.warning("OpenRouter TTS returned status %d: %s", response.status_code, body)
            raise TTSProviderException(detail=f"OpenRouter error: HTTP {response.status_code}")

        # Wrap PCM → WAV
        return _pcm_to_wav(response.content)


# Module-level singleton for direct injection
def get_openrouter_tts_service() -> OpenRouterTtsService:
    """Return the shared OpenRouterTtsService instance."""
    return _OPENROUTER_TTS_INSTANCE


_OPENROUTER_TTS_INSTANCE = OpenRouterTtsService()
