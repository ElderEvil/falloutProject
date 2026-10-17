"""Shared synthesis voices and content-cache keys for runtime and voice packs."""

from __future__ import annotations

import hashlib

ELEVENLABS_VOICES = {
    "echo": "JBFqnCBsd6RMkjVDRZzb",  # George
    "alloy": "pNInz6obpgDQGcFmaJgB",
    "fable": "21m00Tcm4TlvDq8ikWAM",
}


def elevenlabs_voice_id(voice_type: str) -> str:
    """Unmapped game voices retain the default announcer voice."""
    return ELEVENLABS_VOICES.get(voice_type, ELEVENLABS_VOICES["echo"])


def narration_cache_key(text: str, voice: str) -> str:
    """Changing text, game voice, or resolved synthesis voice invalidates audio."""
    raw = f"{text}:{voice}:{elevenlabs_voice_id(voice)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"pa/{digest[:16]}.mp3"
