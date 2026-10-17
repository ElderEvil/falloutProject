"""ElevenLabs text-to-speech service — cache-first, quota-exempt TTS path."""

import logging

import httpx

from app.core.config import settings
from app.utils.exceptions import ElevenLabsProviderException

logger = logging.getLogger(__name__)

ELEVENLABS_API_URL = "https://api.elevenlabs.io/v1/text-to-speech"
DEFAULT_VOICE_ID = "JBFqnCBsd6RMkjVDRZzb"  # George
DEFAULT_MODEL_ID = "eleven_multilingual_v2"
DEFAULT_STABILITY = 0.5
DEFAULT_SIMILARITY_BOOST = 0.75


class ElevenLabsTtsService:
    """Thin async wrapper around ElevenLabs text-to-speech REST API.

    The free tier has no quota, so callers may use this path without
    checking token quotas.
    """

    @property
    def is_enabled(self) -> bool:
        """True when an API key is configured."""
        return bool(settings.ELEVENLABS_API_KEY.strip())

    async def generate_speech(
        self,
        text: str,
        voice_id: str | None = None,
        model_id: str | None = None,
    ) -> bytes:
        """Generate speech audio via ElevenLabs and return raw bytes.

        Args:
            text: The line to speak.
            voice_id: ElevenLabs voice; defaults to DEFAULT_VOICE_ID.
            model_id: ElevenLabs model; defaults to DEFAULT_MODEL_ID.

        Raises:
            ElevenLabsProviderException: On HTTP or transport errors from the API.
        """
        if not self.is_enabled:
            raise ElevenLabsProviderException(detail="ElevenLabs is not configured")

        headers = {
            "xi-api-key": settings.ELEVENLABS_API_KEY.strip(),
            "Content-Type": "application/json",
        }
        payload = {
            "model_id": model_id or DEFAULT_MODEL_ID,
            "text": text,
            "voice_settings": {
                "stability": DEFAULT_STABILITY,
                "similarity_boost": DEFAULT_SIMILARITY_BOOST,
            },
        }

        url = f"{ELEVENLABS_API_URL}/{voice_id or DEFAULT_VOICE_ID}"

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json=payload,
                )
        except httpx.RequestError as e:
            # Transport-level failures (timeout, DNS, connect) must also hit the
            # caller's degradation path, not leak out as unhandled errors.
            logger.warning("ElevenLabs TTS transport error: %s", e)
            raise ElevenLabsProviderException(detail=f"ElevenLabs unreachable: {e}") from e

        if response.status_code == 401:
            raise ElevenLabsProviderException(detail="ElevenLabs API key is invalid")
        if response.status_code == 429:
            raise ElevenLabsProviderException(detail="ElevenLabs rate limit exceeded")
        if response.status_code != 200:
            body = response.text[:200]
            logger.warning("ElevenLabs TTS returned status %d: %s", response.status_code, body)
            raise ElevenLabsProviderException(detail=f"ElevenLabs error: HTTP {response.status_code}")

        return response.content


# Module-level singleton for direct injection
def get_elevenlabs_tts_service() -> ElevenLabsTtsService:
    """Return the shared ElevenLabsTtsService instance."""
    return _ELEVENLABS_TTS_INSTANCE


_ELEVENLABS_TTS_INSTANCE = ElevenLabsTtsService()
