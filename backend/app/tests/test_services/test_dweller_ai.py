"""Tests for DwellerAIService covering quota, edge cases, photo/audio/avatar generation, and pipeline."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dweller_ai import BIO_MAX_LENGTH, dweller_ai

pytestmark = pytest.mark.asyncio


# ── Helpers ──────────────────────────────────────────────────────────────


def _make_dweller_mock(
    *,
    bio: str | None = None,
    first_name: str = "Test",
    last_name: str = "Dweller",
    gender: str = "male",
    image_url: str | None = None,
    visual_attributes: dict | None = None,
    rarity: str = "common",
) -> MagicMock:
    """Return a MagicMock with the minimum DwellerReadFull shape needed."""
    dweller = MagicMock()
    dweller.bio = bio
    dweller.first_name = first_name
    dweller.last_name = last_name
    dweller.gender = gender
    dweller.image_url = image_url
    dweller.visual_attributes = visual_attributes
    dweller.rarity = rarity
    dweller.id = uuid.uuid4()
    dweller.vault_id = uuid.uuid4()
    # SPECIAL stats (used by format_special_stats)
    dweller.strength = 5
    dweller.perception = 5
    dweller.endurance = 5
    dweller.charisma = 5
    dweller.intelligence = 5
    dweller.agility = 5
    dweller.luck = 5
    return dweller


def _make_user_mock() -> MagicMock:
    user = MagicMock()
    user.id = uuid.uuid4()
    return user


def _make_agent_result(output, input_tokens=50, output_tokens=30, total_tokens=80) -> MagicMock:
    """Return a mock agent result with usage info."""
    result = MagicMock()
    result.output = output
    result.usage.return_value = MagicMock(
        input_tokens=input_tokens, output_tokens=output_tokens, total_tokens=total_tokens
    )
    return result


# ── Quota Exceeded Tests ────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method_name", "method_kwargs"),
    [
        ("generate_backstory", {"dweller_id": None}),
        ("extend_bio", {"dweller_id": uuid.UUID("00000000-0000-0000-0000-000000000001")}),
        ("generate_visual_attributes", {"dweller_id": None}),
    ],
)
@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.dweller_crud")
async def test_quota_exceeded_raises(
    mock_crud: MagicMock, mock_quota: MagicMock, method_name: str, method_kwargs: dict
) -> None:
    """QuotaExceededException should be raised when monthly tokens are exhausted."""
    from app.utils.exceptions import QuotaExceededException

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=False, used=500000, limit=500000))

    mock_dweller = _make_dweller_mock(bio="A story." if method_name == "extend_bio" else None)
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)
    mock_crud.update = AsyncMock()

    user = _make_user_mock()
    kwargs = {"user": user, "db_session": MagicMock(), **method_kwargs}
    if method_name in ("generate_backstory", "generate_visual_attributes"):
        kwargs["dweller_info"] = mock_dweller

    with pytest.raises(QuotaExceededException):
        await getattr(dweller_ai, method_name)(**kwargs)


# ── generate_backstory edge cases ───────────────────────────────────────


@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_backstory_already_has_bio(mock_crud: MagicMock, mock_quota: MagicMock) -> None:
    """Should raise ContentNoChangeException if dweller already has a bio."""
    from app.utils.exceptions import ContentNoChangeException

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))

    mock_dweller = _make_dweller_mock(bio="Existing biography text.")
    mock_crud.update = AsyncMock()

    with pytest.raises(ContentNoChangeException, match="already has a bio"):
        await dweller_ai.generate_backstory(user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller)


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.backstory_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_backstory_truncates_long_bio(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """Backstory exceeding BIO_MAX_LENGTH should be truncated with ellipsis."""
    from app.schemas.dweller_ai import DwellerBackstory

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()
    mock_map.register_bio_places = AsyncMock()

    mock_dweller = _make_dweller_mock(bio=None)

    # Generate a bio that's way too long (twice the max)
    long_bio = "X" * (BIO_MAX_LENGTH * 2)
    output = DwellerBackstory(bio=long_bio, origin_place="Megaton", visited_places=[])
    mock_agent.run = AsyncMock(return_value=_make_agent_result(output))

    await dweller_ai.generate_backstory(user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller)

    # Verify truncation: stored bio should be <= BIO_MAX_LENGTH and end with "..."
    mock_crud.update.assert_called_once()
    stored_bio = mock_crud.update.call_args[0][2].bio
    assert len(stored_bio) <= BIO_MAX_LENGTH
    assert stored_bio.endswith("...")


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.backstory_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_backstory_usage_extraction_fails(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """When usage() raises, bio generation should still succeed with None tokens."""
    from app.schemas.dweller_ai import DwellerBackstory

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()
    mock_map.register_bio_places = AsyncMock()

    mock_dweller = _make_dweller_mock(bio=None)

    output = DwellerBackstory(bio="A valid backstory.", origin_place="Rivet City", visited_places=[])
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage = MagicMock(side_effect=Exception("Usage extraction failure"))
    mock_agent.run = AsyncMock(return_value=mock_result)

    user = _make_user_mock()

    result = await dweller_ai.generate_backstory(user=user, db_session=MagicMock(), dweller_info=mock_dweller)

    assert result is mock_dweller
    mock_crud.update.assert_called_once()
    mock_llm.create.assert_called_once()
    llm_kwargs = mock_llm.create.call_args[1]["obj_in"]
    assert llm_kwargs.prompt_tokens is None
    assert llm_kwargs.completion_tokens is None
    assert llm_kwargs.total_tokens is None


# ── extend_bio edge cases ───────────────────────────────────────────────


@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.dweller_crud")
async def test_extend_bio_no_existing_bio(mock_crud: MagicMock, mock_quota: MagicMock) -> None:
    """Should raise ContentNoChangeException if dweller has no bio to extend."""
    from app.utils.exceptions import ContentNoChangeException

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))

    mock_dweller = _make_dweller_mock(bio=None)
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)
    mock_crud.update = AsyncMock()

    with pytest.raises(ContentNoChangeException, match="doesn't have a bio to extend"):
        await dweller_ai.extend_bio(
            db_session=MagicMock(),
            dweller_id=mock_dweller.id,
            user=_make_user_mock(),
        )


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.map_service")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.bio_extension_agent")
@patch("app.services.dweller_ai.quota_service")
async def test_extend_bio_usage_extraction_fails(
    mock_quota: MagicMock,
    mock_agent: MagicMock,
    mock_crud: MagicMock,
    mock_map: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """When usage() raises, extend_bio should still succeed with None tokens."""
    from app.schemas.dweller_ai import ExtendedBio

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()
    mock_map.register_bio_places = AsyncMock()

    mock_dweller = _make_dweller_mock(bio="Original bio.")
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)

    output = ExtendedBio(extended_bio="Extended details.", visited_places=[])
    mock_result = MagicMock()
    mock_result.output = output
    mock_result.usage = MagicMock(side_effect=Exception("Usage failure"))
    mock_agent.run = AsyncMock(return_value=mock_result)

    user = _make_user_mock()

    result = await dweller_ai.extend_bio(db_session=MagicMock(), dweller_id=mock_dweller.id, user=user)

    assert result is mock_dweller
    mock_crud.update.assert_called_once()
    mock_llm.create.assert_called_once()
    llm_kwargs = mock_llm.create.call_args[1]["obj_in"]
    assert llm_kwargs.prompt_tokens is None
    assert llm_kwargs.completion_tokens is None
    assert llm_kwargs.total_tokens is None


# ── generate_visual_attributes edge cases ────────────────────────────────


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.visual_attributes_agent")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_visual_usage_extraction_fails(
    mock_quota: MagicMock,
    mock_crud: MagicMock,
    mock_agent: MagicMock,
    mock_llm: MagicMock,
) -> None:
    """When usage() raises, visual attr generation should still succeed with None tokens."""
    import app.schemas.dweller as dweller_schemas

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(bio=None, visual_attributes={})
    mock_output = dweller_schemas.DwellerVisualAttributes(height="tall", hair_color="brown")
    mock_result = MagicMock()
    mock_result.output = mock_output
    mock_result.usage = MagicMock(side_effect=Exception("Usage failure"))
    mock_agent.run = AsyncMock(return_value=mock_result)

    user = _make_user_mock()

    result = await dweller_ai.generate_visual_attributes(user=user, db_session=MagicMock(), dweller_info=mock_dweller)

    assert result is mock_dweller
    mock_crud.update.assert_called_once()
    mock_llm.create.assert_called_once()
    llm_kwargs = mock_llm.create.call_args[1]["obj_in"]
    assert llm_kwargs.prompt_tokens is None
    assert llm_kwargs.completion_tokens is None
    assert llm_kwargs.total_tokens is None


# ── _has_substantial_visual_attributes ──────────────────────────────────


def test_has_substantial_non_dict() -> None:
    """Non-dict values should be considered substantial."""
    assert dweller_ai._has_substantial_visual_attributes(42) is True  # type: ignore[arg-type]
    assert dweller_ai._has_substantial_visual_attributes("some string") is True  # type: ignore[arg-type]
    assert dweller_ai._has_substantial_visual_attributes(["list"]) is True  # type: ignore[arg-type]


def test_has_substantial_empty_values_filtered() -> None:
    """Identity keys with empty/falsy values should not count as substantial."""
    assert (
        dweller_ai._has_substantial_visual_attributes(
            {"race": "", "faction": "vault_dweller", "age": None, "state_of_being": 0}
        )
        is False
    )


# ── generate_photo ──────────────────────────────────────────────────────


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_photo_already_has_image(mock_crud: MagicMock, mock_llm: MagicMock) -> None:
    """Should raise ContentNoChangeException if dweller already has a photo."""
    from app.utils.exceptions import ContentNoChangeException

    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(image_url="http://example.com/photo.png")

    with pytest.raises(ContentNoChangeException, match="already has a photo"):
        await dweller_ai.generate_photo(user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller)


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_photo_no_storage_service(mock_crud: MagicMock, mock_llm: MagicMock) -> None:
    """Should raise HTTPException 503 if storage service is not available."""
    from fastapi import HTTPException

    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(image_url=None)

    with patch.object(dweller_ai, "storage_service", None), pytest.raises(HTTPException) as exc_info:
        await dweller_ai.generate_photo(user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller)
    assert exc_info.value.status_code == 503
    assert "not available" in exc_info.value.detail


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_photo_success(mock_crud: MagicMock, mock_llm: MagicMock) -> None:
    """Normal photo generation: image generated, uploaded, thumbnailed, dweller updated."""
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(image_url=None)

    fake_image_bytes = b"\x89PNG\r\n\x1a\n"  # minimal PNG header

    mock_storage = MagicMock()
    mock_storage.upload_file.return_value = "http://cdn.example.com/dweller.png"
    mock_storage.upload_thumbnail.return_value = "http://cdn.example.com/dweller_thumb.png"

    mock_openai = MagicMock()
    mock_openai.generate_image = AsyncMock(return_value=fake_image_bytes)

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch.object(dweller_ai, "open_ai_service", mock_openai),
    ):
        result = await dweller_ai.generate_photo(
            user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller
        )

    assert result is mock_dweller
    mock_openai.generate_image.assert_called_once()
    mock_storage.upload_file.assert_called_once()
    mock_storage.upload_thumbnail.assert_called_once()
    mock_crud.update.assert_called_once()
    mock_llm.create.assert_called_once()


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_photo_force_overwrite(mock_crud: MagicMock, mock_llm: MagicMock) -> None:
    """force=True should regenerate photo even if dweller already has one."""
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(image_url="http://existing.com/old.png")
    fake_image_bytes = b"\x89PNG\r\n\x1a\n"

    mock_storage = MagicMock()
    mock_storage.upload_file.return_value = "http://cdn.example.com/new.png"
    mock_storage.upload_thumbnail.return_value = "http://cdn.example.com/new_thumb.png"

    mock_openai = MagicMock()
    mock_openai.generate_image = AsyncMock(return_value=fake_image_bytes)

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch.object(dweller_ai, "open_ai_service", mock_openai),
    ):
        result = await dweller_ai.generate_photo(
            user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller, force=True
        )

    assert result is mock_dweller
    mock_openai.generate_image.assert_called_once()
    mock_crud.update.assert_called_once()


# ── generate_audio ──────────────────────────────────────────────────────


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_audio_already_has_voice_line(mock_crud: MagicMock, mock_llm: MagicMock) -> None:
    """Should raise ContentNoChangeException if dweller already has voice_line_url."""
    from app.utils.exceptions import ContentNoChangeException

    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(visual_attributes={"voice_line_url": "http://cdn.example.com/audio.mp3"})

    with pytest.raises(ContentNoChangeException, match="already has an audio line"):
        await dweller_ai.generate_audio(
            text="Hello", user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller
        )


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_audio_storage_disabled(mock_crud: MagicMock, mock_llm: MagicMock) -> None:
    """Should raise HTTPException 503 if storage service is disabled."""
    from fastapi import HTTPException

    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(visual_attributes=None)

    mock_storage = MagicMock()
    mock_storage.enabled = False

    with patch.object(dweller_ai, "storage_service", mock_storage), pytest.raises(HTTPException) as exc_info:
        await dweller_ai.generate_audio(
            text="Hello", user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller
        )
    assert exc_info.value.status_code == 503
    assert "not available" in exc_info.value.detail


@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_audio_quota_exceeded(mock_crud: MagicMock, mock_llm: MagicMock, mock_quota: MagicMock) -> None:
    """Should raise QuotaExceededException if token estimate exceeds remaining quota."""
    from app.utils.exceptions import QuotaExceededException

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=False, remaining=0, used=500000, limit=500000))
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(visual_attributes=None)

    mock_storage = MagicMock()
    mock_storage.enabled = True

    with patch.object(dweller_ai, "storage_service", mock_storage), pytest.raises(QuotaExceededException):
        await dweller_ai.generate_audio(
            text="Hello world test audio", user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller
        )


@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_audio_openai_error(mock_crud: MagicMock, mock_llm: MagicMock, mock_quota: MagicMock) -> None:
    """Should raise HTTPException 500 if OpenAI TTS call fails."""
    from fastapi import HTTPException

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True, remaining=500000))
    mock_crud.update = AsyncMock()
    mock_crud.get_full_info = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(visual_attributes=None)

    mock_storage = MagicMock()
    mock_storage.enabled = True

    mock_openai = MagicMock()
    mock_openai.generate_audio = AsyncMock(side_effect=ValueError("Invalid voice"))

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch.object(dweller_ai, "open_ai_service", mock_openai),
        pytest.raises(HTTPException) as exc_info,
    ):
        await dweller_ai.generate_audio(
            text="Hello", user=_make_user_mock(), db_session=MagicMock(), dweller_info=mock_dweller
        )
    assert exc_info.value.status_code == 500
    assert "generate audio" in exc_info.value.detail


@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_audio_success(mock_crud: MagicMock, mock_llm: MagicMock, mock_quota: MagicMock) -> None:
    """Normal audio generation: TTS, upload, storage update, dweller update."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True, remaining=500000))
    mock_crud.update = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(visual_attributes={"hair_color": "brown"})
    # Need get_full_info to return an updated dweller (called at end of generate_audio)
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)

    fake_audio = b"mp3_header_fake_bytes"

    mock_storage = MagicMock()
    mock_storage.enabled = True
    mock_storage.upload_file.return_value = "http://cdn.example.com/voice.mp3"

    mock_openai = MagicMock()
    mock_openai.generate_audio = AsyncMock(return_value=fake_audio)

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch.object(dweller_ai, "open_ai_service", mock_openai),
    ):
        result = await dweller_ai.generate_audio(
            text="Welcome to the vault!",
            user=_make_user_mock(),
            db_session=MagicMock(),
            dweller_info=mock_dweller,
            voice_type="alloy",
        )

    assert result is mock_dweller
    mock_openai.generate_audio.assert_called_once_with(text="Welcome to the vault!", voice="alloy", model="tts-1")
    mock_storage.upload_file.assert_called_once()

    # Verify dweller update contained voice_line_text and preserved existing attrs
    update_call = mock_crud.update.call_args
    stored_attrs = update_call[0][2].visual_attributes
    assert stored_attrs.voice_line_text == "Welcome to the vault!"
    assert stored_attrs.hair_color == "brown"  # preserved existing attr

    mock_llm.create.assert_called_once()
    llm_kwargs = mock_llm.create.call_args[1]["obj_in"]
    assert llm_kwargs.usage == "generate_audio"


@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_audio_empty_bytes_warning(
    mock_crud: MagicMock, mock_llm: MagicMock, mock_quota: MagicMock
) -> None:
    """Empty audio bytes from OpenAI should still proceed (logger.warning, no exception)."""
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True, remaining=500000))
    mock_crud.update = AsyncMock()
    mock_crud.get_full_info = AsyncMock()
    mock_llm.create = AsyncMock()

    mock_dweller = _make_dweller_mock(visual_attributes=None)
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)

    mock_storage = MagicMock()
    mock_storage.enabled = True
    mock_storage.upload_file.return_value = "http://cdn.example.com/silent.mp3"

    mock_openai = MagicMock()
    mock_openai.generate_audio = AsyncMock(return_value=b"")  # empty bytes

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch.object(dweller_ai, "open_ai_service", mock_openai),
    ):
        result = await dweller_ai.generate_audio(
            text="",
            user=_make_user_mock(),
            db_session=MagicMock(),
            dweller_info=mock_dweller,
        )

    assert result is mock_dweller
    # Should still upload and store even with empty bytes
    mock_storage.upload_file.assert_called_once()
    mock_crud.update.assert_called_once()


# ── generate_dweller_avatar ─────────────────────────────────────────────


@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_avatar_updates_and_generates_photo(
    mock_crud: MagicMock,
) -> None:
    """generate_dweller_avatar should update attributes then generate photo (no audio)."""
    import app.schemas.dweller as dweller_schemas

    mock_dweller = _make_dweller_mock()
    # Return a fresh mock after update (simulating the cascading update)
    mock_crud.update = AsyncMock(return_value=mock_dweller)
    mock_crud.get_full_info = AsyncMock()

    fake_image_bytes = b"\x89PNG\r\n\x1a\n"

    mock_storage = MagicMock()
    mock_storage.upload_file.return_value = "http://cdn.example.com/photo.png"
    mock_storage.upload_thumbnail.return_value = "http://cdn.example.com/thumb.png"

    mock_openai = MagicMock()
    mock_openai.generate_image = AsyncMock(return_value=fake_image_bytes)

    mock_llm = MagicMock()
    mock_llm.create = AsyncMock()

    vis_attrs = dweller_schemas.DwellerVisualAttributes(height="tall", hair_color="black")

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch.object(dweller_ai, "open_ai_service", mock_openai),
        patch("app.services.dweller_ai.llm_interaction_crud", mock_llm),
    ):
        result = await dweller_ai.generate_dweller_avatar(
            dweller_id=mock_dweller.id,
            dweller_first_name="Jane",
            dweller_last_name="Doe",
            visual_attributes_input=vis_attrs,
            db_session=MagicMock(),
            user=_make_user_mock(),
        )

    assert result is mock_dweller
    # First update: name + visual attributes
    mock_crud.update.assert_called()
    first_update_call = mock_crud.update.call_args_list[0]
    assert first_update_call[0][2].first_name == "Jane"
    assert first_update_call[0][2].last_name == "Doe"

    # Photo generated
    mock_openai.generate_image.assert_called_once()

    # LLM interaction logged for photo (not for avatar separately)
    assert mock_llm.create.call_count >= 1


@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_avatar_with_voice_line(mock_crud: MagicMock) -> None:
    """generate_dweller_avatar with voice_line_text should also generate audio."""
    import app.schemas.dweller as dweller_schemas

    mock_dweller = _make_dweller_mock()
    mock_crud.update = AsyncMock(return_value=mock_dweller)
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)

    fake_image_bytes = b"\x89PNG\r\n\x1a\n"
    fake_audio_bytes = b"mp3_bytes"

    mock_storage = MagicMock()
    mock_storage.enabled = True
    mock_storage.upload_file.side_effect = [
        "http://cdn.example.com/photo.png",  # image upload
        "http://cdn.example.com/voice.mp3",  # audio upload
    ]
    mock_storage.upload_thumbnail.return_value = "http://cdn.example.com/thumb.png"

    mock_openai = MagicMock()
    mock_openai.generate_image = AsyncMock(return_value=fake_image_bytes)
    mock_openai.generate_audio = AsyncMock(return_value=fake_audio_bytes)

    mock_quota = MagicMock()
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True, remaining=500000))

    mock_llm = MagicMock()
    mock_llm.create = AsyncMock()

    vis_attrs = dweller_schemas.DwellerVisualAttributes(
        height="average", hair_color="blonde", voice_line_text="I'm ready for duty!"
    )

    with (
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch.object(dweller_ai, "open_ai_service", mock_openai),
        patch("app.services.dweller_ai.llm_interaction_crud", mock_llm),
        patch("app.services.dweller_ai.quota_service", mock_quota),
    ):
        result = await dweller_ai.generate_dweller_avatar(
            dweller_id=mock_dweller.id,
            dweller_first_name="Jane",
            dweller_last_name="Doe",
            visual_attributes_input=vis_attrs,
            db_session=MagicMock(),
            user=_make_user_mock(),
        )

    assert result is mock_dweller
    # Both image and audio generated
    mock_openai.generate_image.assert_called_once()
    mock_openai.generate_audio.assert_called_once()
    assert mock_storage.upload_file.call_count == 2  # image + audio


# ── dweller_generate_pipeline ────────────────────────────────────────────


@patch("app.services.dweller_ai.dweller_crud")
async def test_pipeline_dweller_already_complete(mock_crud: MagicMock) -> None:
    """Pipeline should raise ContentNoChangeException if dweller has bio, VA, and image."""
    from app.utils.exceptions import ContentNoChangeException

    mock_dweller = _make_dweller_mock(
        bio="Full bio.",
        image_url="http://example.com/photo.png",
        visual_attributes={"race": "human", "height": "tall", "hair_color": "brown"},
    )
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)

    with pytest.raises(ContentNoChangeException, match="already has"):
        await dweller_ai.dweller_generate_pipeline(
            db_session=MagicMock(), dweller_id=mock_dweller.id, user=_make_user_mock()
        )


@patch("app.services.dweller_ai.dweller_crud")
async def test_pipeline_generates_bio_only(mock_crud: MagicMock) -> None:
    """Pipeline should generate only what's missing (bio, not VA/photo if already present)."""
    mock_dweller = _make_dweller_mock(
        bio=None,
        image_url="http://example.com/photo.png",
        visual_attributes={"race": "human", "height": "tall", "hair_color": "brown"},
    )
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)
    mock_crud.update = AsyncMock()

    from app.schemas.dweller_ai import DwellerBackstory

    mock_quota = MagicMock()
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))

    mock_agent = MagicMock()
    output = DwellerBackstory(bio="Generated bio.", origin_place="Megaton", visited_places=[])
    mock_agent.run = AsyncMock(return_value=_make_agent_result(output))

    mock_map = MagicMock()
    mock_map.register_bio_places = AsyncMock()

    mock_llm = MagicMock()
    mock_llm.create = AsyncMock()

    with (
        patch("app.services.dweller_ai.quota_service", mock_quota),
        patch("app.services.dweller_ai.backstory_agent", mock_agent),
        patch("app.services.dweller_ai.map_service", mock_map),
        patch("app.services.dweller_ai.llm_interaction_crud", mock_llm),
    ):
        result = await dweller_ai.dweller_generate_pipeline(
            db_session=MagicMock(), dweller_id=mock_dweller.id, user=_make_user_mock()
        )

    assert result is mock_dweller
    # Bio was generated (VA and photo skipped — already present)
    mock_agent.run.assert_called_once()
    mock_crud.update.assert_called_once()


@patch("app.services.dweller_ai.dweller_crud")
async def test_pipeline_generates_all_from_scratch(mock_crud: MagicMock) -> None:
    """Pipeline should generate bio, VA, and photo when all are missing."""
    import app.schemas.dweller as dweller_schemas

    mock_dweller = _make_dweller_mock(
        bio=None,
        image_url=None,
        visual_attributes=None,
    )
    mock_crud.get_full_info = AsyncMock(return_value=mock_dweller)
    mock_crud.update = AsyncMock()

    # Mock backstory agent
    from app.schemas.dweller_ai import DwellerBackstory

    mock_quota = MagicMock()
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))

    mock_bio_agent = MagicMock()
    bio_output = DwellerBackstory(bio="Generated bio.", origin_place="Megaton", visited_places=[])
    mock_bio_agent.run = AsyncMock(return_value=_make_agent_result(bio_output))

    # Mock visual attributes agent
    mock_va_agent = MagicMock()
    va_output = dweller_schemas.DwellerVisualAttributes(height="tall", hair_color="brown")
    mock_va_agent.run = AsyncMock(return_value=_make_agent_result(va_output))

    # Mock storage / OpenAI for photo
    mock_storage = MagicMock()
    mock_storage.upload_file.return_value = "http://cdn.example.com/photo.png"
    mock_storage.upload_thumbnail.return_value = "http://cdn.example.com/thumb.png"

    mock_openai = MagicMock()
    mock_openai.generate_image = AsyncMock(return_value=b"\x89PNG\r\n\x1a\n")

    mock_map = MagicMock()
    mock_map.register_bio_places = AsyncMock()

    mock_llm = MagicMock()
    mock_llm.create = AsyncMock()

    with (
        patch("app.services.dweller_ai.quota_service", mock_quota),
        patch("app.services.dweller_ai.backstory_agent", mock_bio_agent),
        patch("app.services.dweller_ai.visual_attributes_agent", mock_va_agent),
        patch("app.services.dweller_ai.map_service", mock_map),
        patch("app.services.dweller_ai.llm_interaction_crud", mock_llm),
        patch.object(dweller_ai, "storage_service", mock_storage),
        patch.object(dweller_ai, "open_ai_service", mock_openai),
    ):
        result = await dweller_ai.dweller_generate_pipeline(
            db_session=MagicMock(),
            dweller_id=mock_dweller.id,
            user=_make_user_mock(),
            origin="Vault 111",
        )

    assert result is mock_dweller
    # All three agents called
    mock_bio_agent.run.assert_called_once()
    mock_va_agent.run.assert_called_once()
    mock_openai.generate_image.assert_called_once()
    assert mock_llm.create.call_count == 3
