"""dweller_ai.generate_audio cache-first routing: only ElevenLabs/OpenAI HTTP and the storage bucket are faked."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dweller_ai_service import dweller_ai
from app.tests.test_services.test_dweller_ai_helpers import ai_env, fake_db, make_dweller, make_user
from app.utils.exceptions import ContentNoChangeException, ElevenLabsProviderException

ELEVEN = "app.services.dweller_ai_service.get_elevenlabs_tts_service"
CACHED = "https://cdn.example.com/pa/cached.mp3"


def _storage(*, hit: bool, url: str = "http://cdn.example.com/audio.mp3") -> MagicMock:
    storage = MagicMock(enabled=True)
    storage.file_exists.return_value = hit
    storage.upload_file.return_value = url
    storage.public_url.return_value = url
    return storage


async def test_cache_hit_skips_all_tts_calls() -> None:
    storage = _storage(hit=True, url="http://cdn.example.com/pa/abc123.mp3")
    with ai_env(storage=storage) as d:
        d.crud.get_full_info = AsyncMock(side_effect=lambda *a, **kw: make_dweller())
        await dweller_ai.generate_audio(
            text="Hello vault dweller",
            user=make_user(),
            db_session=fake_db(),
            dweller_info=make_dweller(),
            voice_type="echo",
        )
    storage.file_exists.assert_called_once()
    # The cache path still logs the interaction, tagged with provider="cache".
    d.llm.create.assert_called_once()
    assert d.llm.create.call_args.kwargs["obj_in"].provider == "cache"


async def test_elevenlabs_enabled_skips_openai_and_quota() -> None:
    dweller = make_dweller()
    storage = _storage(hit=False)
    eleven = MagicMock(is_enabled=True, generate_speech=AsyncMock(return_value=b"mp3-data"))
    with ai_env(storage=storage) as d, patch(ELEVEN, return_value=eleven):
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        await dweller_ai.generate_audio(
            text="Hello vault dweller",
            user=make_user(),
            db_session=fake_db(),
            dweller_info=dweller,
            voice_type="JBFqnCBsd6RMkjVDRZzb",
        )
    d.quota.check_quota.assert_not_called()
    eleven.generate_speech.assert_called_once()
    d.llm.create.assert_called_once()
    log_entry = d.llm.create.call_args.kwargs["obj_in"]
    assert log_entry.provider == "elevenlabs"
    assert log_entry.model == "eleven_multilingual_v2"


async def test_elevenlabs_failure_falls_through_to_openai() -> None:
    dweller = make_dweller()
    storage = _storage(hit=False)
    eleven = MagicMock(is_enabled=True, generate_speech=AsyncMock(side_effect=ElevenLabsProviderException()))
    ai = MagicMock(generate_audio=AsyncMock(return_value=b"openai-audio"))
    with ai_env(storage=storage, ai=ai) as d, patch(ELEVEN, return_value=eleven):
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        await dweller_ai.generate_audio(text="Hello", user=make_user(), db_session=fake_db(), dweller_info=dweller)
    d.quota.check_quota.assert_called_once()
    ai.generate_audio.assert_called_once()
    d.llm.create.assert_called_once()
    log_entry = d.llm.create.call_args.kwargs["obj_in"]
    assert log_entry.provider == "openai"
    assert log_entry.model == "tts-1"


async def test_cache_hit_attaches_voice_line_to_dweller(async_session, user_with_vault, dweller_in_vault) -> None:
    # A dweller reusing a cached line must end up with a playable voice_line_url.
    user, _vault = user_with_vault
    storage = _storage(hit=True, url=CACHED)
    eleven = MagicMock(generate_speech=AsyncMock())
    ai = MagicMock(generate_audio=AsyncMock())
    with (
        patch.object(dweller_ai, "storage_service", storage),
        patch.object(dweller_ai, "ai_service", ai),
        patch(ELEVEN) as eleven_factory,
        patch("app.services.dweller_ai_service.quota_service") as quota,
    ):
        eleven_factory.return_value = eleven
        result = await dweller_ai.generate_audio("Cached line", user, async_session, dweller_id=dweller_in_vault.id)
    assert result.visual_attributes["voice_line_url"] == CACHED
    assert result.visual_attributes["voice_line_text"] == "Cached line"
    # No generation, no upload, no quota.
    eleven.generate_speech.assert_not_called()
    ai.generate_audio.assert_not_called()
    quota.check_quota.assert_not_called()


@pytest.mark.parametrize("voice_type", ["echo", "alloy", "fable"])
async def test_runtime_synthesizes_the_same_voice_as_pack(
    async_session, user_with_vault, dweller_in_vault, voice_type
) -> None:
    import scripts.generate_voices as gen

    entry = {"text": "Hello", "voice_type": voice_type}
    user, _ = user_with_vault
    storage = _storage(hit=False, url="https://cdn.example.com/line.mp3")
    provider = MagicMock(is_enabled=True, generate_speech=AsyncMock(return_value=b"audio"))
    with patch.object(dweller_ai, "storage_service", storage), patch(ELEVEN, return_value=provider):
        await dweller_ai.generate_audio(
            "Hello", user, async_session, dweller_id=dweller_in_vault.id, voice_type=voice_type
        )
    provider.generate_speech.assert_awaited_once_with(text="Hello", voice_id=gen.resolve_voice(entry))
    assert storage.upload_file.call_args.kwargs["file_name"] == gen.content_cache_key(entry)
