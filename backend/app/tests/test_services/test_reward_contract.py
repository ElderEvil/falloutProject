"""Reward contract tests — one wire shape shared by settlement, API, and presentation.

Red-phase targets (all fail before the contract lands):
- granted payloads validate against the GrantedReward union;
- a LUNCHBOX quest reward mints one unopened Item row instead of auto-rolling;
- QuestCompleteResponse rejects unshaped grant dicts;
- a single format_reward_summary() helper renders every variant.
"""

from uuid import UUID, uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from app import crud
from app.models.item import Item
from app.models.storage import Storage
from app.schemas.quest import QuestCompleteResponse
from app.schemas.rewards import format_reward_summary, granted_reward_adapter
from app.schemas.user import UserCreate
from app.schemas.vault import VaultCreateWithUserID
from app.services.reward_service import reward_service
from app.tests.factory.users import create_fake_user
from app.tests.factory.vaults import create_fake_vault
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException

_contract = granted_reward_adapter


async def _vault_with_storage(async_session: AsyncSession):
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    async_session.add(Storage(vault_id=vault.id, max_space=100))
    await async_session.commit()
    return vault


@pytest.mark.asyncio
async def test_caps_grant_matches_contract(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)

    granted = _contract.validate_python(await reward_service.grant_caps(async_session, vault.id, 50))

    assert granted.reward_type == "caps"
    assert granted.amount == 50


@pytest.mark.asyncio
async def test_generic_lunchbox_item_grant_matches_contract(async_session: AsyncSession) -> None:
    """The unopened-lunchbox mint path (grant_item) already yields a contract-shaped payload."""
    vault = await _vault_with_storage(async_session)

    granted = _contract.validate_python(
        await reward_service.grant_item(async_session, vault.id, {"item_type": "lunchbox", "name": "Lunchbox"})
    )

    assert granted.reward_type == "item"
    assert granted.item_id is not None
    item = await async_session.get(Item, UUID(granted.item_id))
    assert item is not None
    assert item.item_type == "lunchbox"


@pytest.mark.asyncio
async def test_lunchbox_reward_mints_unopened_item(async_session: AsyncSession) -> None:
    """LUNCHBOX settlement must mint one unopened Item, not auto-roll contents."""
    vault = await _vault_with_storage(async_session)

    result = await reward_service.grant_lunchbox(async_session, vault.id)

    granted = _contract.validate_python(result)
    assert granted.reward_type == "item"
    rows = (await async_session.execute(select(Item))).scalars().all()
    assert [item.item_type for item in rows] == ["lunchbox"]
    assert "dweller" not in result


@pytest.mark.asyncio
async def test_complete_response_rejects_unshaped_grant(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)

    with pytest.raises(ValidationError):
        QuestCompleteResponse(
            quest_id=vault.id,
            quest_title="Shapeless",
            is_completed=True,
            granted_rewards=[{"reward_type": "caps"}],
        )


@pytest.mark.asyncio
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


@pytest.mark.asyncio
async def test_open_lunchbox_unknown_item_404(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)

    with pytest.raises(ResourceNotFoundException):
        await reward_service.open_lunchbox(async_session, vault.id, uuid4())


@pytest.mark.asyncio
async def test_open_lunchbox_foreign_vault_404(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    other = await _vault_with_storage(async_session)
    minted = await reward_service.grant_lunchbox(async_session, vault.id)

    with pytest.raises(ResourceNotFoundException):
        await reward_service.open_lunchbox(async_session, other.id, UUID(minted["item_id"]))


@pytest.mark.asyncio
async def test_open_non_lunchbox_item_404(async_session: AsyncSession) -> None:
    vault = await _vault_with_storage(async_session)
    minted = await reward_service.grant_item(async_session, vault.id, {"item_type": "consumable", "name": "Nuka-Cola"})

    with pytest.raises(ResourceNotFoundException):
        await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))


@pytest.mark.asyncio
async def test_open_lunchbox_full_storage_409(async_session: AsyncSession) -> None:
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    async_session.add(Storage(vault_id=vault.id, max_space=1))
    await async_session.commit()
    minted = await reward_service.grant_lunchbox(async_session, vault.id)

    with pytest.raises(ResourceConflictException):
        await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))

    remaining = (await async_session.execute(select(Item))).scalars().all()
    assert [item.item_type for item in remaining] == ["lunchbox"]


@pytest.mark.asyncio
async def test_open_lunchbox_twice_second_404(async_session: AsyncSession) -> None:
    """A consumed box cannot be opened again — sequential double-open is single-winner."""
    vault = await _vault_with_storage(async_session)
    minted = await reward_service.grant_lunchbox(async_session, vault.id)

    opened = await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))
    assert len(opened["items"]) == 3

    with pytest.raises(ResourceNotFoundException):
        await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))


@pytest.mark.asyncio
async def test_open_lunchbox_needs_only_net_two_slots(async_session: AsyncSession) -> None:
    """The consumed box frees its slot, so two free slots fit the three rolled items."""
    user = await crud.user.create(async_session, obj_in=UserCreate(**create_fake_user()))
    vault = await crud.vault.create(
        async_session,
        obj_in=VaultCreateWithUserID(**create_fake_vault(), user_id=user.id),
    )
    async_session.add(Storage(vault_id=vault.id, max_space=3))
    await async_session.commit()
    minted = await reward_service.grant_lunchbox(async_session, vault.id)

    opened = await reward_service.open_lunchbox(async_session, vault.id, UUID(minted["item_id"]))

    assert len(opened["items"]) == 3
