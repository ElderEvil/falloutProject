"""Immediate mid-expedition equip of found weapons/outfits (issue #765 workstream 2).

An exploring dweller equips a found weapon/outfit the moment it beats the equipped one,
holds the displaced item on the exploration, and exploration combat reads the live
equipped weapon instead of the departure snapshot.
"""

from unittest.mock import AsyncMock, patch

import pytest_asyncio
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import OutfitTypeEnum, RarityEnum
from app.crud.dweller import dweller as dweller_crud
from app.models.dweller import Dweller
from app.models.outfit import Outfit
from app.models.vault import Vault
from app.models.weapon import Weapon
from app.schemas.exploration_event import CombatEventSchema, EnemySchema
from app.services.exploration.combat_calculator import combat_calculator
from app.services.exploration.event_service import event_service
from app.services.exploration_service import exploration_service
from app.tests.factory.exploration_loot import (
    equip_outfit as _equip_outfit,
)
from app.tests.factory.exploration_loot import (
    equip_weapon as _equip_weapon,
)
from app.tests.factory.exploration_loot import (
    equipped_weapon_names as _equipped_weapons,
)
from app.tests.factory.exploration_loot import (
    held_weapons as _held_weapons,
)
from app.tests.factory.exploration_loot import (
    outfit_loot_event as _outfit_loot_event,
)
from app.tests.factory.exploration_loot import (
    process_loot_event as _process_loot_event,
)
from app.tests.factory.exploration_loot import (
    vault_storage_factory,
)
from app.tests.factory.exploration_loot import (
    weapon_loot_event as _weapon_loot_event,
)
from app.utils.combat import ExpeditionCombatProfile, expedition_combat_profile


@pytest_asyncio.fixture
async def make_vault_storage(async_session: AsyncSession, vault: Vault):
    return await vault_storage_factory(async_session, vault)


async def test_better_weapon_equips_holds_displaced_and_drives_combat(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
    storage = await make_vault_storage()
    dweller.strength = 5
    dweller.agility = 5
    dweller.endurance = 5
    dweller.health = 10
    dweller.max_health = 100
    dweller.radiation = 0
    async_session.add(dweller)
    await async_session.flush()
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    notify = await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )
    # The mid-run equip rings the progression bell.
    assert notify.await_count == 1
    kwargs = notify.await_args.kwargs
    assert kwargs["user_id"] == vault.user_id
    assert kwargs["vault_id"] == vault.id
    assert "Fire hydrant bat" in kwargs["event_description"]
    assert kwargs["meta_data"]["item_type"] == "weapon"
    assert await _equipped_weapons(async_session, dweller) == ["Fire hydrant bat"]
    held = await _held_weapons(async_session, exploration)
    assert [w.name for w in held] == [".32 pistol"]
    assert all(w.dweller_id is None and w.storage_id is None for w in held)
    stored = (await async_session.execute(select(Weapon).where(Weapon.storage_id == storage.id))).scalars().all()
    assert stored == []
    # The displaced item is not duplicated in the journey log.
    assert len(exploration.loot_collected) == 1
    entry = exploration.loot_collected[0]
    assert entry["item_name"] == "Fire hydrant bat"
    assert entry["equipped"] is True
    assert "equipped_item_id" in entry
    # Combat reads the live weapon, not the departure snapshot.
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
    # Death drops the held row instead of stranding it.
    combat_event = CombatEventSchema(description="Deathclaw attack", health_loss=10, enemy="Deathclaw", victory=False)
    with (
        patch("app.services.exploration.event_service.event_generator.generate_event", return_value=combat_event),
        patch("app.services.exploration.event_service.sse_manager.publish", new_callable=AsyncMock),
    ):
        await event_service.process_event(async_session, exploration)
    assert await _held_weapons(async_session, exploration) == []
    assert await _equipped_weapons(async_session, dweller) == ["Fire hydrant bat"]
    assert dweller.is_dead is True


async def test_worse_or_tied_weapon_does_not_equip(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> None:
    await _equip_weapon(
        async_session, dweller, name="Fire hydrant bat", rarity=RarityEnum.LEGENDARY, damage_min=19, damage_max=31
    )
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(async_session, exploration, _weapon_loot_event(".32 pistol", "Common", 1, 2, 10))
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Relentless raider sword", "Legendary", 19, 31, 500)
    )
    assert await _equipped_weapons(async_session, dweller) == ["Fire hydrant bat"]
    assert await _held_weapons(async_session, exploration) == []
    assert all(entry.get("equipped") is not True for entry in exploration.loot_collected)


async def test_better_outfit_equips_immediately(
    async_session: AsyncSession, vault: Vault, dweller: Dweller, make_vault_storage
) -> None:
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


async def test_two_successive_upgrades_hold_both_displaced(
    async_session: AsyncSession, vault: Vault, dweller: Dweller
) -> None:
    await _equip_weapon(async_session, dweller, name=".32 pistol", rarity=RarityEnum.COMMON, damage_min=1, damage_max=2)
    exploration = await exploration_service.send_dweller(async_session, vault.id, dweller.id, duration=4)
    await _process_loot_event(async_session, exploration, _weapon_loot_event("Baseball bat", "Rare", 5, 15, 100))
    await _process_loot_event(
        async_session, exploration, _weapon_loot_event("Fire hydrant bat", "Legendary", 19, 31, 500)
    )
    assert await _equipped_weapons(async_session, dweller) == ["Fire hydrant bat"]
    held = await _held_weapons(async_session, exploration)
    assert sorted(w.name for w in held) == [".32 pistol", "Baseball bat"]
    assert all(w.dweller_id is None and w.storage_id is None for w in held)
