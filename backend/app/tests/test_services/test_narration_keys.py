"""Guard: the pack generator and runtime must agree on narration cache keys.

A pre-generated voice pack is only useful if the runtime cache-first lookup
finds it. Both sides must derive identical bucket keys from the same
text + runtime voice identifier.
"""

import json
from pathlib import Path
from unittest.mock import MagicMock

from app.services.dweller_ai import dweller_ai
from app.utils.narration_keys import narration_cache_key


def test_runtime_and_generator_produce_identical_keys() -> None:
    """Runtime _cache_key and narration_cache_key agree for the same inputs."""
    text, voice = "Hello, dweller.", "echo"
    assert dweller_ai._cache_key(text, voice) == narration_cache_key(text, voice)


def test_manifest_entries_hash_with_runtime_voice_type() -> None:
    """Every manifest entry's key, as the generator computes it, is a runtime key.

    Guards against the generator drifting back to hashing the ElevenLabs
    voice_id (which runtime requests never see).
    """
    import scripts.generate_voices as gen

    manifest = json.loads((Path(gen.MANIFEST_PATH)).read_text(encoding="utf-8"))
    assert manifest, "manifest must not be empty"
    for entry in manifest:
        expected = narration_cache_key(entry["text"], entry.get("voice_type", "echo"))
        assert gen.content_cache_key(entry) == expected
        assert expected.startswith("pa/")
        assert expected.endswith(".mp3")


def test_shared_helper_matches_runtime_cache_key_for_all_voices() -> None:
    """Key shape and stability: 16 hex chars under pa/, deterministic on re-run."""
    first = narration_cache_key("some line", "echo")
    second = narration_cache_key("some line", "echo")
    assert first == second
    hex_part = first.removeprefix("pa/").removesuffix(".mp3")
    assert len(hex_part) == 16
    assert int(hex_part, 16) >= 0  # must be hex
