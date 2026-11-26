"""DwellerAIService: quota, edge cases, photo/audio/avatar generation and the pipeline."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.schemas.dweller import DwellerVisualAttributes
from app.schemas.dweller_ai import DwellerBackstory
from app.services.dweller_ai_service import BIO_MAX_LENGTH, dweller_ai
from app.services.quota_service import QuotaCheckResult
from app.tests.test_services.test_dweller_ai_helpers import SVC, ai_env, fake_db, make_dweller, make_user
from app.utils.exceptions import (
    AIAudioException,
    AIProviderException,
    AIStorageException,
    ContentNoChangeException,
    QuotaExceededException,
)

DEFAULT_PORTRAIT = "/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp"


@pytest.mark.parametrize(
    ("method_name", "method_kwargs"),
    [
        ("generate_backstory", {"dweller_id": None}),
        ("extend_bio", {"dweller_id": uuid.UUID("00000000-0000-0000-0000-000000000001")}),
        ("generate_visual_attributes", {"dweller_id": None}),
    ],
)
async def test_quota_exceeded_raises(method_name, method_kwargs) -> None:
    with ai_env() as d:
        d.quota.check_quota = AsyncMock(
            return_value=QuotaCheckResult(
                allowed=False, remaining=0, limit=500_000, percentage=100.0, warning=True, used=500_000
            )
        )
        dweller = make_dweller("A story." if method_name == "extend_bio" else None)
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        kwargs = {"user": make_user(), "db_session": MagicMock(), **method_kwargs}
        if method_name in ("generate_backstory", "generate_visual_attributes"):
            kwargs["dweller_info"] = dweller
        with pytest.raises(QuotaExceededException):
            await getattr(dweller_ai, method_name)(**kwargs)


async def test_generate_backstory_truncates_long_bio() -> None:
    output = DwellerBackstory(bio="X" * (BIO_MAX_LENGTH * 2), origin_place="Megaton", visited_places=[])
    with ai_env("backstory_agent", output) as d:
        await dweller_ai.generate_backstory(user=make_user(), db_session=fake_db(), dweller_info=make_dweller())
    d.llm.create.call_args.args[0].commit.assert_awaited_once()
    # Rendered bios must stay within the prompt's 900-character upper bound.
    d.crud.update.assert_called_once()
    stored_bio = d.crud.update.call_args[0][2].bio
    assert len(stored_bio) <= 900
    assert stored_bio.endswith("...")


async def test_extend_bio_no_existing_bio() -> None:
    dweller = make_dweller()
    with ai_env() as d:
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        with pytest.raises(ContentNoChangeException, match="doesn't have a bio to extend"):
            await dweller_ai.extend_bio(db_session=fake_db(), dweller_id=dweller.id, user=make_user())


async def test_generate_visual_usage_extraction_fails() -> None:
    output = DwellerVisualAttributes(height="tall", hair_color="brown")
    with ai_env("visual_attributes_agent", output) as d:
        d.agent.run.return_value.usage = MagicMock(side_effect=Exception("Usage failure"))
        dweller = make_dweller(visual_attributes={})
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        result = await dweller_ai.generate_visual_attributes(
            user=make_user(), db_session=fake_db(), dweller_info=dweller
        )
    assert result is dweller
    d.crud.update.assert_called_once()
    d.llm.create.assert_called_once()
    llm_kwargs = d.llm.create.call_args[1]["obj_in"]
    assert llm_kwargs.prompt_tokens is None
    assert llm_kwargs.completion_tokens is None
    assert llm_kwargs.total_tokens is None


def test_has_substantial_non_dict() -> None:
    assert dweller_ai._has_substantial_visual_attributes(42) is True  # type: ignore[arg-type]
    assert dweller_ai._has_substantial_visual_attributes("some string") is True  # type: ignore[arg-type]
    assert dweller_ai._has_substantial_visual_attributes(["list"]) is True  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("method", "kwargs", "match"),
    [
        ("generate_photo", {}, "already has a photo"),
        ("generate_audio", {"text": "Hello"}, "already has an audio line"),
    ],
)
async def test_generation_guard_rejects_completed_assets(method, kwargs, match) -> None:
    dweller = make_dweller(
        image_url="http://example.com/photo.png",
        visual_attributes={"voice_line_url": "http://cdn.example.com/audio.mp3"},
    )
    with ai_env(), pytest.raises(ContentNoChangeException, match=match):
        await getattr(dweller_ai, method)(user=make_user(), db_session=fake_db(), dweller_info=dweller, **kwargs)


@pytest.mark.parametrize(
    ("method", "kwargs", "disabled"),
    [
        ("generate_photo", {"image_url": None}, False),
        ("generate_photo", {"image_url": DEFAULT_PORTRAIT}, False),
        ("generate_audio", {"text": "Hello"}, True),
    ],
    ids=["photo", "photo-default-portrait-regenerable", "audio"],
)
async def test_storage_unavailable_maps_to_a_503(method, kwargs, disabled) -> None:
    call_kwargs = dict(kwargs)
    storage = MagicMock(enabled=False) if disabled else None
    dweller = make_dweller(image_url=call_kwargs.pop("image_url", None), visual_attributes=None)
    with ai_env() as d, patch.object(dweller_ai, "storage_service", storage):
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        with pytest.raises(AIStorageException) as exc:
            await getattr(dweller_ai, method)(
                user=make_user(), db_session=fake_db(), dweller_info=dweller, **call_kwargs
            )
    assert exc.value.status_code == 503
    assert "not available" in exc.value.detail


async def test_generate_photo_maps_provider_failures_to_a_safe_error() -> None:
    # Portrait provider failures must not reach the client as an unstructured 500.
    storage = MagicMock()
    ai = MagicMock(generate_image=AsyncMock(side_effect=RuntimeError("OpenAI client not available")))
    dweller = make_dweller(image_url=None)
    with ai_env(storage=storage, ai=ai), pytest.raises(AIProviderException) as exc_info:
        await dweller_ai.generate_photo(user=make_user(), db_session=fake_db(), dweller_info=dweller)
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "Portrait generation failed. Please try again."


async def test_generate_audio_quota_exceeded() -> None:
    storage = MagicMock(enabled=True)
    storage.file_exists.return_value = False  # no cache hit
    dweller = make_dweller(visual_attributes=None)
    with ai_env(storage=storage) as d:
        d.quota.check_quota = AsyncMock(
            return_value=QuotaCheckResult(
                allowed=False, remaining=0, limit=500_000, percentage=100.0, warning=True, used=500_000
            )
        )
        with pytest.raises(QuotaExceededException):
            await dweller_ai.generate_audio(
                text="Hello world test audio", user=make_user(), db_session=fake_db(), dweller_info=dweller
            )
    assert storage.file_exists.call_count == 1


async def test_generate_audio_openai_error() -> None:
    storage = MagicMock(enabled=True)
    storage.file_exists.return_value = False  # no cache hit
    ai = MagicMock(generate_audio=AsyncMock(side_effect=ValueError("Invalid voice")))
    dweller = make_dweller(visual_attributes=None)
    with ai_env(storage=storage, ai=ai), pytest.raises(AIAudioException) as exc_info:
        await dweller_ai.generate_audio(text="Hello", user=make_user(), db_session=fake_db(), dweller_info=dweller)
    assert exc_info.value.status_code == 500
    assert "generate audio" in exc_info.value.detail


async def test_generate_audio_empty_bytes_warning() -> None:
    storage = MagicMock(enabled=True)
    storage.file_exists.return_value = False  # no cache hit
    storage.upload_file.return_value = "http://cdn.example.com/silent.mp3"
    ai = MagicMock(generate_audio=AsyncMock(return_value=b""))  # empty bytes
    dweller = make_dweller(visual_attributes=None)
    with ai_env(storage=storage, ai=ai) as d:
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        result = await dweller_ai.generate_audio(text="", user=make_user(), db_session=fake_db(), dweller_info=dweller)
    assert result is dweller
    # Empty bytes still get uploaded and stored.
    storage.upload_file.assert_called_once()
    d.crud.update.assert_called_once()


async def test_generate_avatar_updates_and_generates_photo() -> None:
    dweller = make_dweller()
    storage = MagicMock()
    storage.upload_file.return_value = "http://cdn.example.com/photo.png"
    storage.upload_thumbnail.return_value = "http://cdn.example.com/thumb.png"
    ai = MagicMock(generate_image=AsyncMock(return_value=b"\x89PNG\r\n\x1a\n"))
    attrs = DwellerVisualAttributes(height="tall", hair_color="black")
    user = make_user()
    with (
        ai_env(storage=storage, ai=ai) as d,
        patch(f"{SVC}.dweller_service.update_player_dweller", new_callable=AsyncMock) as update,
    ):
        update.return_value = dweller
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        result = await dweller_ai.generate_dweller_avatar(
            dweller_id=dweller.id,
            dweller_first_name="Jane",
            dweller_last_name="Doe",
            visual_attributes_input=attrs,
            db_session=fake_db(),
            user=user,
        )
    assert result is dweller
    # First update: name + visual attributes, screened as player text.
    update.assert_called_once()
    assert update.call_args.kwargs["user_id"] == user.id
    assert update.call_args[0][2].first_name == "Jane"
    assert update.call_args[0][2].last_name == "Doe"
    # Photo generated; LLM interaction logged for the photo (not for the avatar separately).
    ai.generate_image.assert_called_once()
    assert d.llm.create.call_count >= 1


async def test_generate_avatar_with_voice_line() -> None:
    dweller = make_dweller()
    storage = MagicMock(enabled=True)
    storage.file_exists.return_value = False  # no cache hit
    storage.upload_file.side_effect = [
        "http://cdn.example.com/photo.png",  # image upload
        "http://cdn.example.com/voice.mp3",  # audio upload
    ]
    storage.upload_thumbnail.return_value = "http://cdn.example.com/thumb.png"
    ai = MagicMock(
        generate_image=AsyncMock(return_value=b"\x89PNG\r\n\x1a\n"), generate_audio=AsyncMock(return_value=b"mp3_bytes")
    )
    attrs = DwellerVisualAttributes(height="average", hair_color="blonde", voice_line_text="I'm ready for duty!")
    with (
        ai_env(storage=storage, ai=ai) as d,
        patch(f"{SVC}.dweller_service.update_player_dweller", new_callable=AsyncMock) as update,
    ):
        update.return_value = dweller
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        result = await dweller_ai.generate_dweller_avatar(
            dweller_id=dweller.id,
            dweller_first_name="Jane",
            dweller_last_name="Doe",
            visual_attributes_input=attrs,
            db_session=fake_db(),
            user=make_user(),
        )
    assert result is dweller
    # Both image and audio generated.
    ai.generate_image.assert_called_once()
    ai.generate_audio.assert_called_once()
    assert storage.upload_file.call_count == 2  # image + audio


async def test_pipeline_completeness_and_default_portrait() -> None:
    dossier = {"race": "human", "height": "tall", "hair_color": "brown"}
    complete = make_dweller("Full bio.", image_url="http://example.com/photo.png", visual_attributes=dossier)
    with ai_env() as d:
        d.crud.get_full_info = AsyncMock(return_value=complete)
        with pytest.raises(ContentNoChangeException, match="already has"):
            await dweller_ai.dweller_generate_pipeline(db_session=fake_db(), dweller_id=complete.id, user=make_user())
    # A curated default must not make the dossier complete; the pipeline still generates a custom photo.
    defaulted = make_dweller("Full bio.", image_url=DEFAULT_PORTRAIT, visual_attributes=dossier)
    with ai_env() as d:
        d.crud.get_full_info = AsyncMock(return_value=defaulted)
        with patch.object(dweller_ai, "generate_photo", new=AsyncMock(return_value=defaulted)) as generate:
            result = await dweller_ai.dweller_generate_pipeline(
                db_session=fake_db(), dweller_id=defaulted.id, user=make_user()
            )
    generate.assert_awaited_once()
    assert result is defaulted


async def test_pipeline_generates_all_from_scratch() -> None:
    dweller = make_dweller(bio=None, image_url=None, visual_attributes=None)
    storage = MagicMock()
    storage.upload_file.return_value = "http://cdn.example.com/photo.png"
    storage.upload_thumbnail.return_value = "http://cdn.example.com/thumb.png"
    ai = MagicMock(generate_image=AsyncMock(return_value=b"\x89PNG\r\n\x1a\n"))
    bio_output = DwellerBackstory(bio="Generated bio.", origin_place="Megaton", visited_places=[])
    va_output = DwellerVisualAttributes(height="tall", hair_color="brown")
    with ai_env(
        agents={"backstory_agent": bio_output, "visual_attributes_agent": va_output}, storage=storage, ai=ai
    ) as d:
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        result = await dweller_ai.dweller_generate_pipeline(
            db_session=fake_db(), dweller_id=dweller.id, user=make_user(), origin="Vault 111"
        )
    assert result is dweller
    # All three generation steps ran.
    d.backstory_agent.run.assert_called_once()
    d.visual_attributes_agent.run.assert_called_once()
    ai.generate_image.assert_called_once()
    assert d.llm.create.call_count == 3
