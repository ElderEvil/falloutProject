"""Tests for immediate mid-expedition equip of found weapons/outfits (issue #765 workstream 2).

An exploring dweller equips a found weapon/outfit the moment it beats the equipped one,
holds the displaced item on the exploration, and exploration combat reads the live
equipped weapon instead of the departure snapshot.
"""

from collections.abc import Awaitable, Callable
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import OutfitTypeEnum, RarityEnum, WeaponSubtypeEnum, WeaponTypeEnum
from app.crud.dweller import dweller as dweller_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.storage import Storage
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.exploration_event import (
    CombatEventSchema,
    EnemySchema,
    LootEventSchema,
    LootSchema,
    OutfitSchema,
    WeaponSchema,
)
from app.services.exploration.combat_calculator import combat_calculator
from app.services.exploration.event_service import event_service
from app.services.exploration_service import exploration_service
from app.utils.combat import ExpeditionCombatProfile, expedition_combat_profile


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


def _outfit_loot_event(name: str, rarity: str, value: int, outfit_type: str) -> LootEventSchema:
    item = OutfitSchema(name=name, rarity=rarity, value=value, outfit_type=outfit_type)
    return LootEventSchema(description=f"Found a {name}", loot=LootSchema(item=item, item_type="outfit", caps=5))


async def _process_loot_event(async_session: AsyncSession, exploration, loot_event: LootEventSchema) -> None:
    with (
        patch("app.services.exploration.event_service.event_generator.generate_event", return_value=loot_event),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock),
    ):
        await event_service.process_event(async_session, exploration)


@pytest.mark.asyncio
async def test_finding_better_weapon_equips_immediately(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A better found weapon is equipped at once; the displaced one is held, not stored."""
    storage = await make_vault_storage()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == ["Fire hydrant bat"]

    held = (await async_session.execute(select(Weapon).where(Weapon.exploration_id == exploration.id))).scalars().all()
    assert [w.name for w in held] == [".32 pistol"]
    assert all(w.dweller_id is None and w.storage_id is None for w in held)

    stored = (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all()
    assert stored == []


@pytest.mark.asyncio
async def test_worse_or_tied_weapon_does_not_equip(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """A worse or tied found weapon stays ordinary loot: no equip, no held row, no marker."""
    await _equip_weapon(
        async_session, dweller, name="Fire hydrant bat", rarity=RarityEnum.LEGENDARY, damage_min=19, damage_max=31
    )

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(async_session, exploration, _weapon_loot_event(".32 pistol", "Common", 1, 2, 10))
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Relentless raider sword", "Legendary", 19, 31, 500)
    )

    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == ["Fire hydrant bat"]

    held = (await async_session.execute(select(Weapon).where(Weapon.exploration_id == exploration.id))).scalars().all()
    assert held == []

    assert all(entry.get("equipped") is not True for entry in exploration.loot_collected)


@pytest.mark.asyncio
async def test_better_outfit_equips_immediately(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
    make_vault_storage,
):
    """A better found outfit is equipped at once and the displaced outfit is held."""
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
    await _process_loot_event(
        async_session, exploration, _outfit_loot_event("NCR Ranger outfit", "Rare", 100, "rare_outfit")
    )

    equipped = (await async_session.execute(select(Outfit).where(Outfit.dweller_id == dweller.id))).scalars().all()
    assert [o.name for o in equipped] == ["NCR Ranger outfit"]

    held = (await async_session.execute(select(Outfit).where(Outfit.exploration_id == exploration.id))).scalars().all()
    assert [o.name for o in held] == ["Mechanic jumpsuit"]
    assert all(o.dweller_id is None and o.storage_id is None for o in held)


@pytest.mark.asyncio
async def test_two_successive_upgrades_hold_both_displaced(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Two upgrades in a row: the strongest stays equipped and both displaced weapons are held."""
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(async_session, exploration, _weapon_loot_event("Baseball bat", "Rare", 5, 15, 100))
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == ["Fire hydrant bat"]

    held = (await async_session.execute(select(Weapon).where(Weapon.exploration_id == exploration.id))).scalars().all()
    assert sorted(w.name for w in held) == [".32 pistol", "Baseball bat"]
    assert all(w.dweller_id is None and w.storage_id is None for w in held)


@pytest.mark.asyncio
async def test_loot_entry_marked_equipped_and_displaced_not_added(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """The equipped find's loot entry carries the equipped marker; the displaced item is not logged."""
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    assert len(exploration.loot_collected) == 1
    entry = exploration.loot_collected[0]
    assert entry["item_name"] == "Fire hydrant bat"
    assert entry["equipped"] is True
    assert "equipped_item_id" in entry


@pytest.mark.asyncio
async def test_combat_uses_live_equipped_weapon(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """Combat reads the live equipped weapon: the profile reflects it and changes the outcome."""
    dweller.strength = 5
    dweller.agility = 5
    dweller.endurance = 5
    async_session.add(dweller)
    await async_session.flush()

    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    dweller_with_equipment = await dweller_crud.get_with_equipment(async_session, dweller.id)
    profile = expedition_combat_profile(dweller_with_equipment)
    assert profile.weapon_damage == 25.0

    enemy = EnemySchema(name="Radroach swarm", difficulty=1, min_damage=5, max_damage=15)
    new_profile = ExpeditionCombatProfile(strength=5, agility=5, endurance=5, weapon_damage=25.0)

    with (
        patch("app.services.exploration.combat_calculator.random.random", return_value=0.8),
        patch("app.services.exploration.combat_calculator.random.randint", return_value=10),
    ):
        snapshot_outcome = combat_calculator.calculate_combat_outcome(exploration, enemy)
        live_outcome = combat_calculator.calculate_combat_outcome(exploration, enemy, new_profile)

    assert snapshot_outcome.victory is False
    assert live_outcome.victory is True
    assert live_outcome.health_loss != snapshot_outcome.health_loss


@pytest.mark.asyncio
async def test_death_deletes_held_items(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """A fatal combat deletes the run's held items and leaves the equipped item on the corpse."""
    dweller.health = 10
    dweller.max_health = 100
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.flush()

    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )

    combat_event = CombatEventSchema(description="Deathclaw attack", health_loss=10, enemy="Deathclaw", victory=False)
    with (
        patch("app.services.exploration.event_service.event_generator.generate_event", return_value=combat_event),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock),
    ):
        await event_service.process_event(async_session, exploration)

    held = (await async_session.execute(select(Weapon).where(Weapon.exploration_id == exploration.id))).scalars().all()
    assert held == []

    equipped = (await async_session.execute(select(Weapon).where(Weapon.dweller_id == dweller.id))).scalars().all()
    assert [w.name for w in equipped] == ["Fire hydrant bat"]

    assert dweller.is_dead is True


@pytest.mark.asyncio
async def test_mid_run_equip_fires_progression_bell_notification(
    async_session: AsyncSession,
    vault: Vault,
    dweller: Dweller,
):
    """An immediate equip creates a bell entry (progression-visibility red line), not just an SSE line."""
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)

    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)

    notify = AsyncMock()
    with (
        patch("app.services.exploration.event_service.notification_service.notify_exploration_update", notify),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock),
    ):
        await _process_loot_event(
            async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
        )

    assert notify.await_count == 1
    kwargs = notify.await_args.kwargs
    assert kwargs["user_id"] == vault.user_id
    assert kwargs["vault_id"] == vault.id
    assert "Fire hydrant bat" in kwargs["event_description"]
    assert kwargs["meta_data"]["item_type"] == "weapon"
