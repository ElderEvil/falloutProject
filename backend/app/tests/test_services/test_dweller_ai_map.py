from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import func, select

from app import crud
from app.core.enums import NotificationType, RarityEnum
from app.models.dweller import BIO_MAX_CHARS
from app.models.llm_interaction import LLMInteraction
from app.models.notification import Notification
from app.models.world_location import DwellerLocation, WorldLocation
from app.schemas.dweller_ai import DwellerBackstory, ExtendedBio
from app.services.dweller_ai_service import dweller_ai
from app.tests.test_services.test_dweller_ai_helpers import ai_env, fake_db, make_dweller, make_user


async def test_generate_backstory_swallows_map_failures_and_replaces_the_origin_entry() -> None:
    dweller = make_dweller("Old origin.")
    dweller.bio_entries = [
        {"source": "template", "text": "Old origin.", "ref": {}, "created_at": "2026-01-01T00:00:00"}
    ]
    output = DwellerBackstory(bio="New origin.", origin_place="Megaton", visited_places=["Rivet City"])
    with ai_env("backstory_agent", output) as d:
        d.map.register_bio_places = AsyncMock(side_effect=Exception("DB failure"))
        result = await dweller_ai.generate_backstory(user=make_user(), db_session=fake_db(), dweller_info=dweller)
    # The helper catches internally; the bio is still committed and the old origin entry replaced.
    d.crud.update.assert_called_once()
    d.llm.create.assert_called_once()
    assert result is not None
    entries = d.crud.update.call_args[0][2].bio_entries
    assert [entry["source"] for entry in entries] == ["template"]
    assert entries[0]["text"] == "New origin."


async def test_extend_bio_length_guard_truncates_at_the_bio_cap() -> None:
    dweller = make_dweller("A" * (BIO_MAX_CHARS - 100))
    output = ExtendedBio(extended_bio="B" * 300, visited_places=[])
    with ai_env("bio_extension_agent", output) as d:
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        await dweller_ai.extend_bio(db_session=fake_db(), dweller_id=dweller.id, user=make_user())
    d.crud.update.assert_called_once()
    stored_bio = d.crud.update.call_args[0][2].bio  # DwellerUpdate.bio
    assert len(stored_bio) <= BIO_MAX_CHARS
    assert stored_bio.endswith("...")
    assert not stored_bio.endswith("....")  # not double-truncated


async def test_extend_bio_rewrites_the_origin_entry() -> None:
    dweller = make_dweller("Original biography.")
    output = ExtendedBio(extended_bio="More details.", visited_places=[])
    with ai_env("bio_extension_agent", output) as d:
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        await dweller_ai.extend_bio(db_session=fake_db(), dweller_id=dweller.id, user=make_user())
    update = d.crud.update.call_args[0][2]
    assert [entry["source"] for entry in update.bio_entries] == ["template"]
    assert update.bio_entries[0]["text"] == update.bio
    assert "More details." in update.bio


async def test_extend_bio_preserves_life_entries() -> None:
    # Extending the origin story must not discard recorded life events or their metadata.
    dweller = make_dweller("Original biography.")
    dweller.bio_entries = [
        {"source": "template", "text": "Original biography.", "ref": {}, "created_at": "2026-01-01T00:00:00"},
        {"source": "dialogue", "text": "I keep a lucky wrench.", "ref": {"source": "chat"}, "created_at": "2026-01-02"},
    ]
    output = ExtendedBio(extended_bio="More details.", visited_places=[])
    with ai_env("bio_extension_agent", output) as d:
        d.crud.get_full_info = AsyncMock(return_value=dweller)
        await dweller_ai.extend_bio(db_session=fake_db(), dweller_id=dweller.id, user=make_user())
    update = d.crud.update.call_args[0][2]
    assert [entry["source"] for entry in update.bio_entries] == ["template", "dialogue"]
    assert update.bio_entries[1]["ref"] == {"source": "chat"}
    assert "lucky wrench" in update.bio
    assert "More details." in update.bio


@pytest.mark.parametrize("extend", [False, True])
async def test_failed_map_write_preserves_bio_and_usage_without_partial_places(async_session, vault, dweller, extend):
    dweller.bio = "Original biography."
    dweller.rarity = RarityEnum.LEGENDARY
    await async_session.commit()
    dweller_id = dweller.id
    user = await crud.user.get(async_session, vault.user_id)
    output = (
        ExtendedBio(extended_bio="New biography.", visited_places=["Arefu", "Megaton"])
        if extend
        else DwellerBackstory(bio="New biography.", origin_place="Arefu", visited_places=["Megaton"])
    )
    result = MagicMock(output=output)
    result.usage.return_value = MagicMock(input_tokens=3, output_tokens=2, total_tokens=5)
    agent = "bio_extension_agent" if extend else "backstory_agent"
    original = crud.world_location.link_dweller

    async def fail_after_link(*args, **kwargs):
        await original(*args, **kwargs)
        raise RuntimeError("map link failed")

    with (
        patch(f"app.services.dweller_ai_service.{agent}.run", new=AsyncMock(return_value=result)),
        patch.object(crud.world_location, "link_dweller", new=fail_after_link),
    ):
        if extend:
            await dweller_ai.extend_bio(async_session, dweller_id, user)
        else:
            await dweller_ai.generate_backstory(user, async_session, dweller_id=dweller_id)
    await async_session.rollback()
    bio = (await crud.dweller.get(async_session, dweller_id)).bio
    assert bio is not None
    assert "New biography." in bio
    interaction = (await async_session.execute(select(LLMInteraction))).scalar_one()
    assert interaction.total_tokens == 5
    notification = (await async_session.execute(select(Notification))).scalar_one()
    assert notification.notification_type == NotificationType.MAP_REGISTRATION_FAILED
    assert (await async_session.execute(select(func.count()).select_from(WorldLocation))).scalar_one() == 0
    assert (await async_session.execute(select(func.count()).select_from(DwellerLocation))).scalar_one() == 0
