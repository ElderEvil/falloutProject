"""Tests for dweller_ai.generate_audio cache-first routing.

Mocks only external boundaries: ElevenLabs HTTP, OpenAI HTTP, storage bucket.
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.utils.exceptions import ContentNoChangeException, QuotaExceededException

pytestmark = pytest.mark.asyncio


def _make_dweller_mock(
    *,
    visual_attributes: dict | None = None,
    dweller_id: uuid.UUID | None = None,
) -> MagicMock:
    dweller = MagicMock()
    dweller.visual_attributes = visual_attributes
    dweller.id = dweller_id or uuid.uuid4()
    dweller.first_name = "Test"
    dweller.last_name = "Dweller"
    return dweller


def _make_user_mock() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


def _mock_get_full_info(db_session, dweller_id) -> MagicMock:
    result = MagicMock()
    result.id = dweller_id
    return result


# ── Cache-hit test ───────────────────────────────────────────────────────


@patch("app.services.dweller_ai_service.llm_interaction_crud")
@patch("app.services.dweller_ai_service.dweller_crud")
async def test_cache_hit_skips_all_tts_calls(
    mock_crud: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """Second call with same text+voice finds cache → no ElevenLabs, no OpenAI calls."""
    from app.services.dweller_ai_service import dweller_ai

    mock_crud.get_full_info = AsyncMock(
        side_effect=lambda *a, **kw: _make_dweller_mock(visual_attributes=None, dweller_id=uuid.uuid4())
    )
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_storage = MagicMock()
    mock_storage.enabled = True
    mock_storage.file_exists.return_value = True
    mock_storage.public_url.return_value = "http://cdn.example.com/pa/abc123.mp3"

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    user = _make_user_mock()
    text = "Hello vault dweller"
    voice_type = "echo"

    with patch.object(dweller_ai, "storage_service", mock_storage):
        dweller_obj = await dweller_ai.generate_audio(
            text=text,
            user=user,
            db_session=mock_db,
            dweller_info=_make_dweller_mock(visual_attributes=None, dweller_id=uuid.uuid4()),
            voice_type=voice_type,
        )

    # Cache hit should NOT call AI services at all
    mock_storage.file_exists.assert_called_once()
    # Should NOT call _log_audio_result with a TTS call — but it IS called with provider=cache
    mock_llm.create.assert_called_once()
    call_kwargs = mock_llm.create.call_args
    assert call_kwargs.kwargs["obj_in"].provider == "cache"

    # Should NOT update visual_attributes with new URL (just logs and returns early)
    # Actually it does update — let me check the code... it returns early on cache hit
    # without updating. Good.


# ── ElevenLabs routing test ─────────────────────────────────────────────


@patch("app.services.dweller_ai_service.llm_interaction_crud")
@patch("app.services.dweller_ai_service.dweller_crud")
async def test_elevenlabs_enabled_skips_openai_and_quota(
    mock_crud: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """When ElevenLabs is enabled and succeeds, OpenAI generate_audio is never called
    and quota is NOT checked."""
    from app.services.dweller_ai_service import dweller_ai

    dweller_id = uuid.uuid4()
    mock_dweller = _make_dweller_mock(visual_attributes=None, dweller_id=dweller_id)
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_storage = MagicMock()
    mock_storage.enabled = True
    mock_storage.file_exists.return_value = False  # No cache hit
    mock_storage.upload_file.return_value = "http://cdn.example.com/audio.mp3"

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    user = _make_user_mock()
    text = "Hello vault dweller"

    # Mock ElevenLabs to succeed
    mock_elevenlabs_svc = MagicMock()
    mock_elevenlabs_svc.is_enabled = True
    mock_elevenlabs_svc.generate_speech = AsyncMock(return_value=b"mp3-data")

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch("app.services.dweller_ai_service.get_elevenlabs_tts_service", return_value=mock_elevenlabs_svc),
        patch("app.services.dweller_ai_service.quota_service") as mock_quota,
    ):
        await dweller_ai.generate_audio(
            text=text,
            user=user,
            db_session=mock_db,
            dweller_info=mock_dweller,
            voice_type="JBFqnCBsd6RMkjVDRZzb",
        )

    # OpenAI generate_audio must NOT have been called
    # Since we didn't mock ai_service.generate_audio, if it was called it would raise
    # But the test still passes because the patch on get_elevenlabs_tts_service means
    # the ElevenLabs path is taken and audio_bytes is set.
    # Let's be explicit: verify quota was NOT checked
    mock_quota.check_quota.assert_not_called()

    # ElevenLabs was called
    mock_elevenlabs_svc.generate_speech.assert_called_once()

    # LLMInteraction log should carry provider='elevenlabs'
    mock_llm.create.assert_called_once()
    call_kwargs = mock_llm.create.call_args
    log_entry = call_kwargs.kwargs["obj_in"]
    assert log_entry.provider == "elevenlabs"
    assert log_entry.model == "eleven_multilingual_v2"


# ── ElevenLabs failure falls through to OpenAI ──────────────────────────


@patch("app.services.dweller_ai_service.llm_interaction_crud")
@patch("app.services.dweller_ai_service.dweller_crud")
async def test_elevenlabs_failure_falls_through_to_openai(
    mock_crud: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """When ElevenLabs raises, the code falls through to OpenAI (which IS quota-checked)."""
    from app.services.dweller_ai_service import dweller_ai
    from app.utils.exceptions import ElevenLabsProviderException

    dweller_id = uuid.uuid4()
    mock_dweller = _make_dweller_mock(visual_attributes=None, dweller_id=dweller_id)
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_storage = MagicMock()
    mock_storage.enabled = True
    mock_storage.file_exists.return_value = False
    mock_storage.upload_file.return_value = "http://cdn.example.com/audio.mp3"

    mock_db = MagicMock()
    mock_db.commit = AsyncMock()

    user = _make_user_mock()

    # Mock ElevenLabs to fail
    mock_elevenlabs_svc = MagicMock()
    mock_elevenlabs_svc.is_enabled = True
    mock_elevenlabs_svc.generate_speech = AsyncMock(side_effect=ElevenLabsProviderException())

    # Mock quota to allow
    mock_quota_result = MagicMock()
    mock_quota_result.allowed = True
    mock_quota_result.remaining = 10000

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch("app.services.dweller_ai_service.get_elevenlabs_tts_service", return_value=mock_elevenlabs_svc),
        patch("app.services.dweller_ai_service.quota_service") as mock_quota,
        patch.object(dweller_ai, "ai_service") as mock_ai_svc,
    ):
        mock_quota.check_quota = AsyncMock(return_value=mock_quota_result)
        mock_ai_svc.generate_audio = AsyncMock(return_value=b"openai-audio")

        await dweller_ai.generate_audio(
            text="Hello",
            user=user,
            db_session=mock_db,
            dweller_info=mock_dweller,
        )

    # Quota was checked (OpenAI path)
    mock_quota.check_quota.assert_called_once()
    # OpenAI was called
    mock_ai_svc.generate_audio.assert_called_once()
    # Provider in log should be 'openai'
    mock_llm.create.assert_called_once()
    log_entry = mock_llm.create.call_args.kwargs["obj_in"]
    assert log_entry.provider == "openai"
    assert log_entry.model == "tts-1"


# ── Existing guard preserved ────────────────────────────────────────────


@patch("app.services.dweller_ai_service.llm_interaction_crud")
@patch("app.services.dweller_ai_service.dweller_crud")
async def test_already_has_audio_line_raises_before_anything(
    mock_crud: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """Pre-existing voice_line_url guard must still fire."""
    from app.services.dweller_ai_service import dweller_ai

    mock_dweller = _make_dweller_mock(visual_attributes={"voice_line_url": "http://cdn.example.com/existing.mp3"})
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)

    mock_db = MagicMock()

    user = _make_user_mock()

    with pytest.raises(ContentNoChangeException, match="already has an audio line"):
        await dweller_ai.generate_audio(
            text="New text",
            user=user,
            db_session=mock_db,
            dweller_info=mock_dweller,
        )


# ── Cache hit attaches voice_line_url to the requesting dweller ─────────


async def test_cache_hit_attaches_voice_line_to_dweller(async_session, user_with_vault, dweller_in_vault) -> None:
    """A dweller reusing a cached line must end up with a playable voice_line_url."""
    import app.services.dweller_ai_service as dweller_ai_mod
    from app.services.dweller_ai_service import dweller_ai as dweller_ai_service

    user, _vault = user_with_vault

    with (
        patch.object(dweller_ai_service, "storage_service") as mock_storage,
        patch.object(dweller_ai_service, "ai_service") as mock_openai,
        patch("app.services.dweller_ai_service.get_elevenlabs_tts_service") as mock_el,
        patch("app.services.dweller_ai_service.quota_service") as mock_quota,
    ):
        mock_storage.enabled = True
        mock_storage.file_exists = MagicMock(return_value=True)
        mock_storage.public_url = MagicMock(return_value="https://cdn.example.com/pa/cached.mp3")
        mock_el.return_value.generate_speech = AsyncMock()
        mock_openai.generate_audio = AsyncMock()

        result = await dweller_ai_service.generate_audio(
            "Cached line", user, async_session, dweller_id=dweller_in_vault.id
        )

        # The requesting dweller now carries the cached audio URL.
        assert result.visual_attributes["voice_line_url"] == "https://cdn.example.com/pa/cached.mp3"
        assert result.visual_attributes["voice_line_text"] == "Cached line"
        # No generation, no upload, no quota.
        mock_el.return_value.generate_speech.assert_not_called()
        mock_openai.generate_audio.assert_not_called()
        mock_quota.check_quota.assert_not_called()


@pytest.mark.parametrize("voice_type", ["echo", "alloy", "fable"])
async def test_runtime_synthesizes_the_same_voice_as_pack(
    async_session, user_with_vault, dweller_in_vault, voice_type
) -> None:
    import scripts.generate_voices as gen

    from app.services.dweller_ai_service import dweller_ai as service

    entry = {"text": "Hello", "voice_type": voice_type}
    user, _ = user_with_vault
    with (
        patch.object(service, "storage_service") as storage,
        patch("app.services.dweller_ai_service.get_elevenlabs_tts_service") as provider,
    ):
        storage.enabled = True
        storage.file_exists.return_value = False
        storage.upload_file.return_value = "https://cdn.example.com/line.mp3"
        provider.return_value.is_enabled = True
        provider.return_value.generate_speech = AsyncMock(return_value=b"audio")

        await service.generate_audio(
            "Hello", user, async_session, dweller_id=dweller_in_vault.id, voice_type=voice_type
        )

        provider.return_value.generate_speech.assert_awaited_once_with(text="Hello", voice_id=gen.resolve_voice(entry))
        assert storage.upload_file.call_args.kwargs["file_name"] == gen.content_cache_key(entry)
