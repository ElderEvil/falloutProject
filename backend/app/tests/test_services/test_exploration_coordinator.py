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
from app.services.exploration.event_service import event_service
from app.services.exploration.rewards_service import rewards_service
from app.services.exploration_service import exploration_service


async def _ensure_vault_storage(async_session: AsyncSession, vault_id) -> Storage:
    """Ensure storage exists for a vault, create if missing."""
    result = await async_session.execute(select(Storage).where(Storage.vault_id == vault_id))
    storage = result.scalar_one_or_none()
    if storage is None:
        storage = await vault_crud.create_storage(db_session=async_session, vault_id=vault_id)
    return storage


@pytest.mark.asyncio
async def test_transfer_skips_medical_loot_entries(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Stimpak/radaway loot entries create no junk; medical rewards flow through the counters."""
    await make_vault_storage(5)

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    exploration.add_loot(item_name="Stimpak", quantity=1, rarity="Common", item_type="stimpak")
    exploration.add_loot(item_name="RadAway", quantity=1, rarity="Common", item_type="radaway")
    exploration.add_loot(item_name="Wonderglue", quantity=1, rarity="Common", item_type="junk")
    async_session.add(exploration)
    await async_session.flush()
    await async_session.refresh(exploration)

    result = await rewards_service._transfer_loot_to_storage(async_session, exploration)

    assert [item["item_type"] for item in result["transferred"]] == ["junk"]
    junk_names = {
        junk.name
        for junk in (await async_session.execute(select(Junk).where(Junk.storage_id == result["storage_id"]))).scalars()
    }
    assert junk_names == {"Wonderglue"}


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
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

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
    result = await rewards_service._transfer_loot_to_storage(async_session, exploration)

    # Verify item was not transferred (missing data)
    assert len(result["transferred"]) == 0
    assert len(result["overflow"]) == 0  # Not in overflow, just skipped

    # Verify no Weapon record was created
    weapons = await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))
    weapon_records = weapons.scalars().all()
    assert len(weapon_records) == 0


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
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

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
    result = await rewards_service._transfer_loot_to_storage(async_session, exploration)

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
        patch("app.services.exploration.event_service.event_generator.generate_event", return_value=loot_event),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock),
    ):
        await event_service.process_event(async_session, exploration)


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

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()

    with patch(
        "app.services.exploration.rewards_service.crud_weapon.equip",
        new_callable=AsyncMock,
        side_effect=RuntimeError("equip exploded"),
    ):
        rewards = await exploration_coordinator.complete_exploration(async_session, exploration.id)

    assert rewards.caps == 5
    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == [".32 pistol"]


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

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    item = ItemSchema(name="Stimpak", rarity="Common", value=20)
    loot_event = LootEventSchema(description="Found a Stimpak", loot=LootSchema(item=item, item_type="stimpak", caps=0))
    await _process_loot_event(async_session, exploration, loot_event)

    assert exploration.stimpaks == 1
    assert len(exploration.events) == 1
    assert exploration.events[0]["type"] == "loot"
    assert exploration.loot_collected[-1]["item_type"] == "stimpak"


@pytest.mark.asyncio
async def test_auto_equip_keeps_strongest_found_outfit(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A lower-rarity later find never replaces the strongest flagged outfit."""
    await make_vault_storage()
    await _equip_outfit(
        async_session,
        dweller,
        name="Mechanic jumpsuit",
        rarity=RarityEnum.COMMON,
        value=10,
        outfit_type=OutfitTypeEnum.COMMON,
    )

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    ranger = OutfitSchema(name="NCR Ranger outfit", rarity="Rare", value=100, outfit_type="rare_outfit")
    await _process_loot_event(
        async_session,
        exploration,
        LootEventSchema(
            description="Found a NCR Ranger outfit", loot=LootSchema(item=ranger, item_type="outfit", caps=5)
        ),
    )
    rags = OutfitSchema(name="Tattered rags", rarity="Common", value=5, outfit_type="common_outfit")
    await _process_loot_event(
        async_session,
        exploration,
        LootEventSchema(description="Found some Tattered rags", loot=LootSchema(item=rags, item_type="outfit", caps=0)),
    )

    assert exploration.loot_collected[0]["auto_equip"] is True
    assert exploration.loot_collected[0]["item_name"] == "NCR Ranger outfit"
    assert exploration.loot_collected[1].get("auto_equip") is not True

    exploration.start_time = datetime.utcnow() - timedelta(hours=exploration.duration)
    async_session.add(exploration)
    await async_session.flush()
    await exploration_coordinator.complete_exploration(async_session, exploration.id)

    equipped = (await async_session.execute(select(Outfit).where(Outfit.dweller_id == dweller.id))).scalars().all()
    assert [o.name for o in equipped] == ["NCR Ranger outfit"]


@pytest.mark.asyncio
async def test_process_event_publishes_followup_events(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """Equip and auto-heal records created during an event are all streamed via SSE."""
    await make_vault_storage()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    dweller.health = 20
    dweller.max_health = 100
    dweller.radiation = 0
    dweller.stimpack = 1
    async_session.add(dweller)
    await async_session.flush()

    exploration = await exploration_service.send_dweller(
        async_session,
        vault.id,
        dweller.id,
        duration=4,
        stimpaks=1,
    )
    with (
        patch(
            "app.services.exploration.event_service.event_generator.generate_event",
            return_value=_weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500),
        ),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock) as publish_mock,
    ):
        await event_service.process_event(async_session, exploration)

    published_types = [call.args[2]["type"] for call in publish_mock.await_args_list]
    assert published_types == ["loot", "equip", "item_use"]
    assert exploration.stimpaks == 0
    assert dweller.health == 60
