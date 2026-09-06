"""Tests for overflow take/sell/abandon resolution."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.storage import Storage
from app.models.vault import Vault
from app.services.exploration.coordinator import exploration_coordinator
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException, ValidationException


async def _ensure_vault_storage(async_session: AsyncSession, vault_id) -> Storage:
    """Ensure storage exists for a vault, create if missing."""
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    storage = result.scalar_one_or_none()
    if storage is None:
        storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault_id)
    return storage


@pytest_asyncio.fixture
async def make_vault_storage(async_session: AsyncSession, vault: Vault) -> Callable[[int], Awaitable[Storage]]:
    """Factory for the test vault's storage, emptied and sized via max_space."""

    async def _make(max_space: int = 10) -> Storage:
        storage = await _ensure_vault_storage(async_session, vault.id)
        storage.max_space = max_space
        storage.used_space = 0
        async_session.add(storage)
        await async_session.flush()
        return storage

    return _make


async def _completed_with_overflow(async_session, vault, dweller, loots=None):
    """Complete an exploration that overflows; returns (exploration, rewards)."""
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    for loot in loots or []:
        exploration.add_loot(**loot)
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)
    rewards = await exploration_coordinator.complete_exploration(async_session, exploration.id)
    await async_session.refresh(exploration)
    return exploration, rewards


@pytest.mark.asyncio
async def test_complete_persists_unclaimed_loot(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Overflow reported in rewards is also persisted for later resolution."""
    await make_vault_storage(1)
    exploration, rewards = await _completed_with_overflow(
        async_session,
        vault,
        dweller,
        loots=[
            {"item_name": "Kept Item", "quantity": 1, "rarity": "Legendary", "item_type": "junk"},
            {"item_name": "Dropped Item", "quantity": 1, "rarity": "Common", "item_type": "junk"},
        ],
    )

    assert [i["item_name"] for i in rewards.overflow_items] == ["Dropped Item"]
    assert [i["item_name"] for i in (exploration.unclaimed_loot or [])] == ["Dropped Item"]


@pytest.mark.asyncio
async def test_take_unclaimed_item_stores_it(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Taking an overflow item stores it and clears it from the list."""
    storage = await make_vault_storage(2)
    exploration, _ = await _completed_with_overflow(
        async_session,
        vault,
        dweller,
        loots=[
            {"item_name": "Item A", "quantity": 1, "rarity": "Common", "item_type": "junk"},
            {"item_name": "Item B", "quantity": 1, "rarity": "Common", "item_type": "junk"},
            {"item_name": "Item C", "quantity": 1, "rarity": "Common", "item_type": "junk"},
        ],
    )
    stored = (await async_session.execute(select(Junk).where(Junk.storage_id == storage.id))).scalars().all()
    await crud.junk.sell(db_session=async_session, item_id=stored[0].id)

    remaining = await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)

    assert remaining == []
    names = {
        junk.name for junk in (await async_session.execute(select(Junk).where(Junk.storage_id == storage.id))).scalars()
    }
    assert "Item C" in names


@pytest.mark.asyncio
async def test_take_unclaimed_item_conflicts_when_full(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Taking with no space raises 409 and keeps the list intact."""
    await make_vault_storage(1)
    exploration, _ = await _completed_with_overflow(
        async_session,
        vault,
        dweller,
        loots=[
            {"item_name": "Item A", "quantity": 1, "rarity": "Common", "item_type": "junk"},
            {"item_name": "Item B", "quantity": 1, "rarity": "Common", "item_type": "junk"},
        ],
    )

    with pytest.raises(ResourceConflictException):
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 0)

    await async_session.refresh(exploration)
    assert len(exploration.unclaimed_loot or []) == 1


@pytest.mark.asyncio
async def test_sell_unclaimed_item_grants_caps_without_space(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Selling overflow junk grants quantity-aware caps even when storage is full."""
    await make_vault_storage(1)
    await async_session.refresh(vault)
    caps_before = vault.bottle_caps
    exploration, _ = await _completed_with_overflow(
        async_session,
        vault,
        dweller,
        loots=[
            {"item_name": "Item A", "quantity": 1, "rarity": "Common", "item_type": "junk"},
            {"item_name": "Item B", "quantity": 2, "rarity": "Common", "item_type": "junk"},
        ],
    )

    caps, remaining = await rewards_service.sell_unclaimed_item(async_session, exploration.id, 0)

    assert caps == game_config.exploration.junk_value_common * 2
    assert remaining == []
    await async_session.refresh(vault)
    assert vault.bottle_caps > caps_before


@pytest.mark.asyncio
async def test_unclaimed_rejects_bad_index_and_active_exploration(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Out-of-range index 404s; active explorations cannot be resolved."""
    await make_vault_storage(1)
    exploration, _ = await _completed_with_overflow(
        async_session,
        vault,
        dweller,
        loots=[
            {"item_name": "Item A", "quantity": 1, "rarity": "Common", "item_type": "junk"},
            {"item_name": "Item B", "quantity": 1, "rarity": "Common", "item_type": "junk"},
        ],
    )

    with pytest.raises(ResourceNotFoundException):
        await rewards_service.take_unclaimed_item(async_session, exploration.id, 5)

    active = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    with pytest.raises(ValidationException):
        await rewards_service.sell_unclaimed_item(async_session, active.id, 0)
