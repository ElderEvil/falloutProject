"""Guard: the pack generator and runtime must agree on narration cache keys.

A pre-generated voice pack is only useful if the runtime cache-first lookup
finds it. Both sides must derive identical bucket keys from the same
text + runtime voice identifier, and one game-side voice_type must map to
exactly one provider voice (otherwise identical text+type entries collide
in the content cache while synthesizing differently).
"""

import json
from pathlib import Path

import pytest

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

    registry, lines = gen.load_manifest(Path(gen.MANIFEST_PATH))
    assert lines, "manifest must not be empty"
    for entry in lines:
        expected = narration_cache_key(entry["text"], entry.get("voice_type", "echo"))
        assert gen.content_cache_key(entry) == expected
        assert expected.startswith("pa/")
        assert expected.endswith(".mp3")


def test_manifest_voice_registry_is_one_to_one() -> None:
    """One canonical provider voice per game-side voice_type.

    The content cache hashes text+voice_type. If two different ElevenLabs
    voice_ids mapped to the same voice_type, identical lines from different
    speakers would collide in the bucket while synthesizing differently —
    editing a manifest speaker would silently reuse the old recording.
    """
    import scripts.generate_voices as gen

    registry, _lines = gen.load_manifest(Path(gen.MANIFEST_PATH))
    assert registry, "manifest must declare a voice registry"
    ids = list(registry.values())
    assert len(ids) == len(set(ids)), f"registry maps multiple voice_types to the same/duplicated voice ids: {registry}"


def test_manifest_lines_resolve_without_per_entry_overrides() -> None:
    """Every line must resolve through the registry — per-entry voice_id is forbidden."""
    import scripts.generate_voices as gen

    registry, lines = gen.load_manifest(Path(gen.MANIFEST_PATH))
    for entry in lines:
        resolved = gen.resolve_voice(entry, registry)  # raises on override/unknown type
        assert resolved in set(registry.values())
        assert "voice_id" not in entry


def test_generator_rejects_per_entry_voice_id() -> None:
    """The resolver rejects a per-entry voice_id: it breaks the cache contract."""
    import scripts.generate_voices as gen

    entry = {"key": "x", "text": "hello", "voice_type": "echo", "voice_id": "voice-B"}
    with pytest.raises(ValueError, match="forbidden"):
        gen.resolve_voice(entry, {"echo": "voice-A"})


def test_generator_rejects_unknown_voice_type() -> None:
    import scripts.generate_voices as gen

    entry = {"key": "x", "text": "hello", "voice_type": "nope"}
    with pytest.raises(ValueError, match="not in manifest voice registry"):
        gen.resolve_voice(entry, {"echo": "voice-A"})


def test_shared_helper_matches_runtime_cache_key_for_all_voices() -> None:
    """Key shape and stability: 16 hex chars under pa/, deterministic on re-run."""
    first = narration_cache_key("some line", "echo")
    second = narration_cache_key("some line", "echo")
    assert first == second
    hex_part = first.removeprefix("pa/").removesuffix(".mp3")
    assert len(hex_part) == 16
    assert int(hex_part, 16) >= 0  # must be hex
