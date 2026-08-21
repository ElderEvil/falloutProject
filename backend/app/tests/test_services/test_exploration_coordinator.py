"""Tests for exploration coordinator storage validation logic."""

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.junk import Junk
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.common import JunkTypeEnum, OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.schemas.exploration_event import (
    CombatEventSchema,
    ExplorationEventType,
    ItemSchema,
    LootEventSchema,
    LootSchema,
    OutfitSchema,
    WeaponSchema,
)
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
    make_vault_storage,
):
    """Test that loot transfer respects storage capacity limits."""
    storage = await make_vault_storage(3)

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
    make_vault_storage,
):
    """Test that rarer items are transferred first when storage is limited."""
    storage = await make_vault_storage(2)

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
    exploration.add_loot(item_name="Another Common Item", quantity=1, rarity="Common", item_type="junk")
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

    # Overflow should be the less rare items (both common)
    overflow_names = [item["item_name"] for item in result["overflow"]]
    assert "Common Junk" in overflow_names
    assert "Another Common Item" in overflow_names


@pytest.mark.asyncio
async def test_transfer_logs_overflow_warning(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
    caplog,
):
    """Test that overflow is logged as a warning."""
    import logging

    storage = await make_vault_storage(1)

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
    make_vault_storage,
):
    """Test that empty loot returns empty result."""
    await make_vault_storage()

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
    make_vault_storage,
):
    """Test that transfer updates storage used_space counter."""
    storage = await make_vault_storage()

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
    make_vault_storage,
):
    """Test that transfer handles already full storage."""
    storage = await make_vault_storage(2)

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
    make_vault_storage,
):
    """Test that complete_exploration returns overflow items in rewards."""
    storage = await make_vault_storage(1)

    # Create exploration
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Complete only after the configured duration has elapsed.
    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
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


@pytest.mark.asyncio
async def test_transfer_weapon_loot_creates_weapon_record(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Test that weapon loot transfer creates Weapon records in storage."""
    storage = await make_vault_storage()

    # Create exploration
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add weapon loot (using a real weapon name from the data)
    exploration.add_loot(
        item_name="Baseball bat",
        quantity=1,
        rarity="Rare",
        item_type="weapon",
    )
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Verify weapon was transferred
    assert len(result["transferred"]) == 1
    assert result["transferred"][0]["item_type"] == "weapon"
    assert result["transferred"][0]["item_name"] == "Baseball bat"

    # Verify Weapon record was created in storage
    weapons = await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))
    weapon_records = weapons.scalars().all()
    assert len(weapon_records) == 1
    assert weapon_records[0].name == "Baseball bat"
    assert weapon_records[0].rarity == RarityEnum.RARE


@pytest.mark.asyncio
async def test_transfer_outfit_loot_creates_outfit_record(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Test that outfit loot transfer creates Outfit records in storage."""
    storage = await make_vault_storage()

    # Create exploration
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add outfit loot (using a real outfit name from the data)
    exploration.add_loot(
        item_name="Mechanic jumpsuit",
        quantity=1,
        rarity="Common",
        item_type="outfit",
    )
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Verify outfit was transferred
    assert len(result["transferred"]) == 1
    assert result["transferred"][0]["item_type"] == "outfit"
    assert result["transferred"][0]["item_name"] == "Mechanic jumpsuit"

    # Verify Outfit record was created in storage
    outfits = await async_session.execute(select(Outfit).where(Outfit.storage_id == storage.id))
    outfit_records = outfits.scalars().all()
    assert len(outfit_records) == 1
    assert outfit_records[0].name == "Mechanic jumpsuit"
    assert outfit_records[0].rarity == RarityEnum.COMMON


@pytest.mark.asyncio
async def test_transfer_missing_weapon_data_skips_item(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Test that weapon loot with missing data is skipped gracefully."""
    storage = await make_vault_storage()

    # Create exploration
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add weapon loot with non-existent weapon name
    exploration.add_loot(
        item_name="NonExistentWeapon12345",
        quantity=1,
        rarity="Legendary",
        item_type="weapon",
    )
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Verify item was not transferred (missing data)
    assert len(result["transferred"]) == 0
    assert len(result["overflow"]) == 0  # Not in overflow, just skipped

    # Verify no Weapon record was created
    weapons = await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))
    weapon_records = weapons.scalars().all()
    assert len(weapon_records) == 0


@pytest.mark.asyncio
async def test_transfer_missing_outfit_data_skips_item(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Test that outfit loot with missing data is skipped gracefully."""
    storage = await make_vault_storage()

    # Create exploration
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add outfit loot with non-existent outfit name
    exploration.add_loot(
        item_name="NonExistentOutfit12345",
        quantity=1,
        rarity="Legendary",
        item_type="outfit",
    )
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Verify item was not transferred (missing data)
    assert len(result["transferred"]) == 0
    assert len(result["overflow"]) == 0  # Not in overflow, just skipped

    # Verify no Outfit record was created
    outfits = await async_session.execute(select(Outfit).where(Outfit.storage_id == storage.id))
    outfit_records = outfits.scalars().all()
    assert len(outfit_records) == 0


@pytest.mark.asyncio
async def test_transfer_invalid_rarity_defaults_to_common(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Test that invalid rarity strings default to COMMON."""
    storage = await make_vault_storage()
    await async_session.flush()

    # Create exploration
    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )

    # Add junk loot with invalid rarity
    exploration.add_loot(
        item_name="Test Item",
        quantity=1,
        rarity="InvalidRarity",
        item_type="junk",
    )
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    # Transfer loot
    result = await exploration_coordinator._transfer_loot_to_storage(async_session, exploration)

    # Verify item was transferred
    assert len(result["transferred"]) == 1
    assert result["transferred"][0]["item_name"] == "Test Item"

    # Verify Junk record was created with COMMON rarity
    junks = await async_session.execute(select(Junk).where(Junk.storage_id == storage.id))
    junk_records = junks.scalars().all()
    assert len(junk_records) == 1
    assert junk_records[0].rarity == RarityEnum.COMMON


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


async def _equip_weapon(
    async_session: AsyncSession,
    dweller: Dweller,
    *,
    name: str,
    rarity: RarityEnum,
    damage_min: int,
    damage_max: int,
    value: int = 10,
) -> Weapon:
    weapon = Weapon(
        name=name,
        rarity=rarity,
        value=value,
        weapon_type=WeaponTypeEnum.GUN,
        weapon_subtype=WeaponSubtypeEnum.PISTOL,
        stat="agility",
        damage_min=damage_min,
        damage_max=damage_max,
        dweller_id=dweller.id,
    )
    async_session.add(weapon)
    await async_session.flush()
    return weapon


async def _equip_outfit(
    async_session: AsyncSession,
    dweller: Dweller,
    *,
    name: str,
    rarity: RarityEnum,
    value: int,
    outfit_type: OutfitTypeEnum,
) -> Outfit:
    outfit = Outfit(name=name, rarity=rarity, value=value, outfit_type=outfit_type, dweller_id=dweller.id)
    async_session.add(outfit)
    await async_session.flush()
    return outfit


def _weapon_loot_event(name: str, rarity: str, damage_min: int, damage_max: int, value: int) -> LootEventSchema:
    item = WeaponSchema(
        name=name,
        rarity=rarity,
        value=value,
        weapon_type="MELEE",
        weapon_subtype="BLUNT",
        stat="strength",
        damage_min=damage_min,
        damage_max=damage_max,
    )
    return LootEventSchema(description=f"Found a {name}", loot=LootSchema(item=item, item_type="weapon", caps=5))


async def _process_loot_event(async_session: AsyncSession, exploration, loot_event: LootEventSchema) -> None:
    with (
        patch("app.services.exploration.coordinator.event_generator.generate_event", return_value=loot_event),
        patch("app.services.exploration.coordinator.sse_manager.publish", new_callable=AsyncMock),
    ):
        await exploration_coordinator.process_event(async_session, exploration)


@pytest.mark.asyncio
async def test_auto_equip_equips_better_found_weapon_on_completion(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Better weapon found during exploration is equipped on completion; old weapon returns to storage."""
    storage = await make_vault_storage()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    valid_types = {e.value for e in ExplorationEventType}
    assert all(e["type"] in valid_types for e in exploration.events)
    assert exploration.loot_collected[-1]["auto_equip"] is True

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()
    await exploration_coordinator.complete_exploration(async_session, exploration.id)

    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == ["Fire hydrant bat"]
    stored = (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all()
    assert [w.name for w in stored] == [".32 pistol"]


@pytest.mark.asyncio
async def test_auto_equip_does_not_equip_worse_weapon(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A weaker found weapon is not equipped; the dweller keeps the current weapon."""
    storage = await make_vault_storage()
    await _equip_weapon(
        async_session,
        dweller,
        name="Fire hydrant bat",
        rarity=RarityEnum.LEGENDARY,
        damage_min=19,
        damage_max=31,
        value=500,
    )

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await _process_loot_event(async_session, exploration, _weapon_loot_event(".32 pistol", "Common", 1, 2, 10))

    assert exploration.loot_collected[-1].get("auto_equip") is not True

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()
    await exploration_coordinator.complete_exploration(async_session, exploration.id)

    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == ["Fire hydrant bat"]
    stored = (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all()
    assert [w.name for w in stored] == [".32 pistol"]


@pytest.mark.asyncio
async def test_auto_equip_equips_better_found_outfit_by_rarity(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A higher-rarity found outfit (rarity then value) is equipped on completion."""
    storage = await make_vault_storage()
    await _equip_outfit(
        async_session,
        dweller,
        name="Mechanic jumpsuit",
        rarity=RarityEnum.COMMON,
        value=10,
        outfit_type=OutfitTypeEnum.COMMON,
    )

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    item = OutfitSchema(name="NCR Ranger outfit", rarity="Rare", value=100, outfit_type="rare_outfit")
    loot_event = LootEventSchema(
        description="Found a NCR Ranger outfit",
        loot=LootSchema(item=item, item_type="outfit", caps=5),
    )
    await _process_loot_event(async_session, exploration, loot_event)

    assert exploration.loot_collected[-1]["auto_equip"] is True

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()
    await exploration_coordinator.complete_exploration(async_session, exploration.id)

    equipped = (await async_session.execute(select(Outfit).where(Outfit.dweller_id == dweller.id))).scalars().all()
    assert [o.name for o in equipped] == ["NCR Ranger outfit"]
    stored = (await async_session.execute(select(Outfit).where(Outfit.storage_id == storage.id))).scalars().all()
    assert [o.name for o in stored] == ["Mechanic jumpsuit"]


@pytest.mark.asyncio
async def test_auto_equip_skipped_when_storage_full(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """When storage is full the better item is dropped to overflow and never equipped."""
    storage = await make_vault_storage(1)
    async_session.add(
        Junk(
            name="Trash",
            junk_type=JunkTypeEnum.VALUABLES,
            rarity=RarityEnum.COMMON,
            value=1,
            description="Fill slot",
            storage_id=storage.id,
        )
    )
    await async_session.flush()

    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()
    rewards = await exploration_coordinator.complete_exploration(async_session, exploration.id)

    assert len(rewards.overflow_items) == 1
    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == [".32 pistol"]
    bats = (await async_session.execute(select(Weapon).where(Weapon.name == "Fire hydrant bat"))).scalars().all()
    assert bats == []


@pytest.mark.asyncio
async def test_auto_equip_applies_on_recall(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Recall also equips the marked better weapon."""
    storage = await make_vault_storage()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    await exploration_coordinator.recall_exploration(async_session, exploration.id)

    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == ["Fire hydrant bat"]
    stored = (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all()
    assert [w.name for w in stored] == [".32 pistol"]


@pytest.mark.asyncio
async def test_auto_equip_failure_does_not_break_completion(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A failing auto-equip is best-effort and never fails the completion."""
    storage = await make_vault_storage()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()

    with patch(
        "app.services.exploration.coordinator.crud_weapon.equip",
        new_callable=AsyncMock,
        side_effect=RuntimeError("equip exploded"),
    ):
        rewards = await exploration_coordinator.complete_exploration(async_session, exploration.id)

    assert rewards.caps == 5
    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == [".32 pistol"]


@pytest.mark.asyncio
async def test_auto_equip_notifies_vault_owner(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Auto-equipping a better found weapon notifies the vault owner."""
    await make_vault_storage()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()

    with patch(
        "app.services.exploration.coordinator.notification_service.notify_exploration_update",
        new_callable=AsyncMock,
    ) as notify_mock:
        await exploration_coordinator.complete_exploration(async_session, exploration.id)

    notify_mock.assert_awaited_once()
    call_kwargs = notify_mock.await_args.kwargs
    assert call_kwargs["user_id"] == vault.user_id
    assert call_kwargs["vault_id"] == vault.id
    assert call_kwargs["dweller_id"] == dweller.id
    assert "Fire hydrant bat" in call_kwargs["event_description"]


@pytest.mark.asyncio
async def test_auto_equip_no_notification_when_weaker_item(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A weaker found weapon is not equipped, so no notification is sent."""
    await make_vault_storage()
    await _equip_weapon(
        async_session,
        dweller,
        name="Fire hydrant bat",
        rarity=RarityEnum.LEGENDARY,
        damage_min=19,
        damage_max=31,
        value=500,
    )

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    await _process_loot_event(async_session, exploration, _weapon_loot_event(".32 pistol", "Common", 1, 2, 10))

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()

    with patch(
        "app.services.exploration.coordinator.notification_service.notify_exploration_update",
        new_callable=AsyncMock,
    ) as notify_mock:
        await exploration_coordinator.complete_exploration(async_session, exploration.id)

    notify_mock.assert_not_awaited()


@pytest.mark.asyncio
async def test_medicine_loot_adds_single_log_entry(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """A stimpak find logs exactly one event; the count lives in the stimpaks counter."""
    dweller.health = 100
    dweller.max_health = 100
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.flush()

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    item = ItemSchema(name="Stimpak", rarity="Common", value=20)
    loot_event = LootEventSchema(description="Found a Stimpak", loot=LootSchema(item=item, item_type="stimpak", caps=0))
    await _process_loot_event(async_session, exploration, loot_event)

    assert exploration.stimpaks == 1
    assert len(exploration.events) == 1
    assert exploration.events[0]["type"] == "loot"
    assert exploration.loot_collected[-1]["item_type"] == "stimpak"


@pytest.mark.asyncio
async def test_process_event_sse_payload_includes_event_and_health(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Per-event SSE carries the structured event dict plus live health/radiation."""
    dweller.health = 100
    dweller.max_health = 100
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.flush()

    exploration = await crud.exploration.create_with_dweller_stats(
        async_session,
        vault_id=vault.id,
        dweller_id=dweller.id,
        duration=4,
    )
    combat_event = CombatEventSchema(description="Raider attacked", health_loss=5, enemy="Raider", victory=True)

    with (
        patch("app.services.exploration.coordinator.event_generator.generate_event", return_value=combat_event),
        patch("app.services.exploration.coordinator.sse_manager.publish", new_callable=AsyncMock) as publish_mock,
    ):
        await exploration_coordinator.process_event(async_session, exploration)

    publish_mock.assert_awaited_once()
    payload = publish_mock.await_args.args[2]
    assert payload["type"] == "combat"
    assert payload["event"]["type"] == "combat"
    assert payload["event"]["description"] == "Raider attacked"
    assert "time_elapsed_hours" in payload["event"]
    assert payload["health"] == 95
    assert payload["radiation"] == 0
    assert payload["enemies_encountered"] == 1
