"""Shared content-cache keys for narration audio.

Single source of truth for the deterministic bucket key used by BOTH the
runtime cache-first lookup (DwellerAIService) and the offline pack
generator (scripts/generate_voices.py). If you change this function,
previously cached audio is orphaned — that is a migration, not a refactor.
"""

from __future__ import annotations

import hashlib


def narration_cache_key(text: str, voice: str) -> str:
    """Deterministic bucket key from a sha256 of text + voice identifier.

    The voice argument is whatever identifier the caller uses to pick the
    voice: the runtime passes the dweller's voice_type (e.g. "echo"), the
    pack generator passes the ElevenLabs voice_id. Callers on the same line
    must therefore use the same identifier to share cache entries.
    """
    raw = f"{text}:{voice}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return f"pa/{digest[:16]}.mp3"
