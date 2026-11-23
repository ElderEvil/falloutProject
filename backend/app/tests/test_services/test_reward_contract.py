from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.core.event_bus import GameEvent
from app.models.item import Item
from app.models.junk import Junk
from app.models.storage import Storage
from app.schemas.quest import QuestCompleteResponse
from app.schemas.rewards import format_reward_summary, granted_reward_adapter
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.reward_service import reward_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException
from app.utils.reward_delivery import defer_reward_delivery

_contract = granted_reward_adapter


async def _vault_with_storage(async_session: AsyncSession, max_space: int = 100):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(async_session, obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id))
    async_session.add(Storage(vault_id=vault.id, max_space=max_space))
    await async_session.commit()
    return vault


async def test_caps_grant_matches_contract(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    granted = _contract.validate_python(await reward_service.grant_caps(async_session, vault.id, 50))
    assert (granted.reward_type, granted.amount) == ("caps", 50)


async def test_generic_lunchbox_item_grant_matches_contract(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    granted = _contract.validate_python(
        await reward_service.grant_item(async_session, vault.id, {"item_type": "lunchbox", "name": "Lunchbox"})
    )
    assert granted.reward_type == "item"
    assert granted.item_id is not None
    item = await async_session.get(Item, UUID(granted.item_id))
    assert item is not None
    assert item.item_type == "lunchbox"


async def test_lunchbox_reward_mints_unopened_item(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    result = await reward_service.grant_lunchbox(async_session, vault.id)
    assert _contract.validate_python(result).reward_type == "item"
    rows = (await async_session.execute(select(Item))).scalars().all()
    assert [item.item_type for item in rows] == ["lunchbox"]
    assert "dweller" not in result


async def test_complete_response_rejects_unshaped_grant() -> None:
    with pytest.raises(ValidationError):
        QuestCompleteResponse(
            quest_id=uuid4(),
            quest_title="Shapeless",
            is_completed=True,
            granted_rewards=[{"reward_type": "caps"}],
        )


async def test_format_reward_summary_covers_variants(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    caps = _contract.validate_python(await reward_service.grant_caps(async_session, vault.id, 25))
    food = _contract.validate_python(await reward_service.grant_resource(async_session, vault.id, "food", 10))
    box = _contract.validate_python(
        await reward_service.grant_item(async_session, vault.id, {"item_type": "lunchbox", "name": "Lunchbox"})
    )
    assert format_reward_summary(caps) == "25 caps"
    assert format_reward_summary(food) == "10 food"
    assert format_reward_summary(box) == "Lunchbox"
    assert format_reward_summary([caps, food, box]) == "25 caps, 10 food, Lunchbox"


async def test_open_lunchbox_rejects_unknown_foreign_and_non_lunchbox_items(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    other = await _vault_with_storage(async_session)
    minted = await reward_service.grant_lunchbox(async_session, vault.id)
    nuka = await reward_service.grant_item(async_session, vault.id, {"item_type": "consumable", "name": "Nuka-Cola"})
    with pytest.raises(ResourceNotFoundException):
        await reward_service.open_lunchbox(async_session, vault.id, uuid4())
    with pytest.raises(ResourceNotFoundException):
        await reward_service.open_lunchbox(async_session, other.id, UUID(minted["item_id"]))
    with pytest.raises(ResourceNotFoundException):
        await reward_service.open_lunchbox(async_session, vault.id, UUID(nuka["item_id"]))


async def test_open_lunchbox_full_storage_409(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session, max_space=1)
    minted = await reward_service.grant_lunchbox(async_session, vault.id)
    with pytest.raises(ResourceConflictException):
        await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))
    remaining = (await async_session.execute(select(Item))).scalars().all()
    assert [item.item_type for item in remaining] == ["lunchbox"]


async def test_open_lunchbox_twice_second_404(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    minted = await reward_service.grant_lunchbox(async_session, vault.id)
    opened = await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))
    assert len(opened["items"]) == 3
    with pytest.raises(ResourceNotFoundException):
        await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))


async def test_open_lunchbox_needs_only_net_two_slots(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session, max_space=3)
    minted = await reward_service.grant_lunchbox(async_session, vault.id)
    opened = await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))
    assert len(opened["items"]) == 3


async def test_rarity_junk_placeholders_settle_into_catalog_valuables(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    for name, rarity, canonical in (("Rare junk", "rare", "Globe"), ("Legendary junk", "legendary", "Gold watch")):
        granted = await reward_service.grant_item(
            async_session, vault.id, {"item_type": "junk", "name": name, "rarity": rarity}
        )
        junk = await async_session.get(Junk, UUID(granted["item_id"]))
        assert junk is not None
        assert junk.name == canonical
        assert junk.junk_type.value == "valuables"
        assert junk.value is not None
        assert junk.image_url is not None
        assert granted["name"] == name  # The claim response keeps the authored reward text.
    desk_fan = await reward_service.grant_item(
        async_session, vault.id, {"item_type": "junk", "name": "Desk fan", "rarity": "common"}
    )
    fan = await async_session.get(Junk, UUID(desk_fan["item_id"]))
    assert fan is not None
    assert (fan.junk_type.value, fan.value) == ("steel", 2)


async def test_deferred_junk_grant_emits_no_collection_event(async_session: AsyncSession) -> None:
    # Junk granted by an objective or quest reward must never credit a collection objective.
    vault = await _vault_with_storage(async_session)
    junk = {"item_type": "junk", "name": "Duct tape", "rarity": "common", "quantity": 2}
    with patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit:
        async with defer_reward_delivery(async_session):
            await reward_service.grant_item(async_session, vault.id, junk)
        assert [call for call in emit.await_args_list if call.args and call.args[0] == GameEvent.ITEM_COLLECTED] == []
    with patch("app.core.event_bus.event_bus.emit", new_callable=AsyncMock) as emit:
        await reward_service.grant_item(async_session, vault.id, junk)
    collected = [
        call.args[2] for call in emit.await_args_list if call.args and call.args[0] == GameEvent.ITEM_COLLECTED
    ]
    assert collected == [{"item_type": "junk", "amount": 2}]
