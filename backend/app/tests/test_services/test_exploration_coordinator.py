"""Tests for exploration coordinator storage validation logic."""

from datetime import datetime, timedelta

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.storage import Storage
from app.models.vault import Vault
from app.schemas.common import JunkTypeEnum, RarityEnum
from app.services.exploration.coordinator import exploration_coordinator


async def _ensure_vault_storage(async_session: AsyncSession, vault_id) -> Storage:
    """Ensure storage exists for a vault, create if missing."""
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    storage = result.scalar_one_or_none()
    if storage is None:
        storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault_id)
    return storage


@pytest.mark.asyncio
async def test_transfer_respects_storage_limits(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that loot transfer respects storage capacity limits."""
    # Ensure storage exists and set up limited space
    storage = await _ensure_vault_storage(async_session, vault.id)
    storage.max_space = 3
    storage.used_space = 0
    async_session.add(storage)
    await async_session.flush()

    # Create exploration with 5 items
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add 5 loot items
    for i in range(5):
        exploration.add_loot(
            item_name=f"Test Item {i}",
            quantity=1,
            rarity="Common",
            item_type="junk",
        )
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Should have transferred 3 items (storage limit) and overflowed 2
    assert len(result["transferred"]) == 3
    assert len(result["overflow"]) == 2


@pytest.mark.asyncio
async def test_transfer_prioritizes_rare_items(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that rarer items are transferred first when storage is limited."""
    # Ensure storage exists and set up limited space for only 2 items
    storage = await _ensure_vault_storage(async_session, vault.id)
    storage.max_space = 2
    storage.used_space = 0
    async_session.add(storage)
    await async_session.flush()

    # Create exploration
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add items with different rarities (in non-priority order)
    exploration.add_loot(item_name="Common Junk", quantity=1, rarity="Common", item_type="junk")
    exploration.add_loot(item_name="Legendary Blade", quantity=1, rarity="Legendary", item_type="junk")
    exploration.add_loot(item_name="Uncommon Stuff", quantity=1, rarity="Uncommon", item_type="junk")
    exploration.add_loot(item_name="Rare Gem", quantity=1, rarity="Rare", item_type="junk")

    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Should have transferred 2 items (capacity limit)
    assert len(result["transferred"]) == 2
    assert len(result["overflow"]) == 2

    # Transferred items should be the rarest ones
    transferred_names = [item["item_name"] for item in result["transferred"]]
    assert "Legendary Blade" in transferred_names
    assert "Rare Gem" in transferred_names

    # Overflow should be the less rare items
    overflow_names = [item["item_name"] for item in result["overflow"]]
    assert "Common Junk" in overflow_names
    assert "Uncommon Stuff" in overflow_names


@pytest.mark.asyncio
async def test_transfer_logs_overflow_warning(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    caplog,
):
    """Test that overflow is logged as a warning."""
    import logging

    # Ensure storage exists and set up limited space
    storage = await _ensure_vault_storage(async_session, vault.id)
    storage.max_space = 1
    storage.used_space = 0
    async_session.add(storage)
    await async_session.flush()

    # Create exploration with 2 items
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    exploration.add_loot(item_name="Item A", quantity=1, rarity="Common", item_type="junk")
    exploration.add_loot(item_name="Item B", quantity=1, rarity="Common", item_type="junk")

    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot with logging
    with caplog.at_level(logging.WARNING):
        result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Verify overflow occurred
    assert len(result["overflow"]) == 1

    # Verify warning was logged
    overflow_logs = [r for r in caplog.records if "overflow" in r.message.lower() or "Storage full" in r.message]
    assert len(overflow_logs) >= 1


@pytest.mark.asyncio
async def test_transfer_empty_loot_returns_empty(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that empty loot returns empty result."""
    # Ensure storage exists
    await _ensure_vault_storage(async_session, vault.id)

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await async_session.refresh(exploration)

    # No loot added
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    assert result["transferred"] == []
    assert result["overflow"] == []


@pytest.mark.asyncio
async def test_transfer_updates_storage_used_space(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that transfer updates storage used_space counter."""
    # Ensure storage exists and set it up
    storage = await _ensure_vault_storage(async_session, vault.id)
    storage.max_space = 10
    storage.used_space = 0
    async_session.add(storage)
    await async_session.flush()

    # Create exploration with 3 items
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    for i in range(3):
        exploration.add_loot(
            item_name=f"Item {i}",
            quantity=1,
            rarity="Common",
            item_type="junk",
        )
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Verify storage used_space was updated (re-query to get fresh object)
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault.id))
    updated_storage = result.scalar_one()
    assert updated_storage.used_space == 3


@pytest.mark.asyncio
async def test_transfer_with_full_storage(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that transfer handles already full storage."""
    # Ensure storage exists and fill it
    storage = await _ensure_vault_storage(async_session, vault.id)
    storage.max_space = 2
    storage.used_space = 0
    async_session.add(storage)
    await async_session.flush()

    # Add existing items to fill storage
    for i in range(2):
        junk = Junk(
            name=f"Existing Junk {i}",
            junk_type=JunkTypeEnum.VALUABLES,
            rarity=RarityEnum.COMMON,
            description="Test",
            storage_id=storage.id,
        )
        async_session.add(junk)

    await async_session.flush()

    # Create exploration with loot
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    exploration.add_loot(item_name="New Item", quantity=1, rarity="Common", item_type="junk")
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # All items should overflow since storage is full
    assert len(result["transferred"]) == 0
    assert len(result["overflow"]) == 1


@pytest.mark.asyncio
async def test_complete_exploration_includes_overflow_items(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Test that complete_exploration returns overflow items in rewards."""
    # Ensure storage exists and set up limited space
    storage = await _ensure_vault_storage(async_session, vault.id)
    storage.max_space = 1
    storage.used_space = 0
    async_session.add(storage)
    await async_session.flush()

    # Create exploration
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Make exploration active and add loot
    exploration.start_time = datetime.utcnow() - timedelta(hours=1)
    exploration.add_loot(item_name="Kept Item", quantity=1, rarity="Legendary", item_type="junk")
    exploration.add_loot(item_name="Dropped Item", quantity=1, rarity="Common", item_type="junk")
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Complete exploration
    rewards = await exploration_coordinator.complete_exploration(async_session, exploration.id)

    # Verify overflow items are reported
    assert len(rewards.items) == 1
    assert rewards.items[0]["item_name"] == "Kept Item"
    assert len(rewards.overflow_items) == 1
    assert rewards.overflow_items[0]["item_name"] == "Dropped Item"
