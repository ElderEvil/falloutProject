"""Outfit SPECIAL bonuses must apply in combat and production, effective-only.

The agreed contract (docs/ROADMAP.md "Outfit SPECIAL Bonuses Are Inert"): a 10 S
dweller wearing a +5 S outfit counts as 15 S in combat AND production. The bonus
is derived on read by ``effective_stat`` and never written into the stored
dweller stat, so unequipping reverts cleanly.
"""

import pytest

from app import crud
from app.core.game_config import game_config
from app.models.room import Room
from app.models.vault import Vault
from app.options.identity_modifiers import effective_stat
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.services.resource_manager import ResourceManager
from app.utils.combat import combat_power


async def _create_dweller(async_session, vault: Vault, *, strength: int = 10) -> object:
    dweller = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(
            first_name="Strong",
            last_name="Dweller",
            gender="male",
            rarity="common",
            vault_id=vault.id,
            strength=strength,
            perception=1,
            endurance=1,
            charisma=1,
            intelligence=1,
            agility=1,
            luck=1,
        ),
    )
    # Reload with weapon/outfit eager-loaded so combat_power never lazy-loads.
    return await crud.dweller.get(async_session, dweller.id)


async def _equip_strength_outfit(async_session, dweller_id, *, strength: int = 5) -> None:
    outfit = await crud.outfit.create(
        async_session,
        obj_in={
            "name": "Strength Suit",
            "rarity": "Rare",
            "value": 100,
            "outfit_type": "rare_outfit",
            "strength": strength,
        },
    )
    await crud.outfit.equip(db_session=async_session, item_id=outfit.id, dweller_id=dweller_id)


@pytest.mark.asyncio
async def test_equipped_outfit_raises_combat_power(async_session, vault) -> None:
    """A +5 S outfit raises combat_power by 5 x the unarmed strength weight."""
    dweller = await _create_dweller(async_session, vault)
    base_power = combat_power(dweller)

    await _equip_strength_outfit(async_session, dweller.id)
    dweller = await crud.dweller.get(async_session, dweller.id)

    strength_weight = game_config.combat.weapon_stat_weights["unarmed"]["strength"]
    assert combat_power(dweller) == pytest.approx(base_power + 5 * strength_weight)


@pytest.mark.asyncio
async def test_outfit_bonus_reaches_production_rate(async_session, vault) -> None:
    """Production (the real effective_stat consumer) scales with the outfit bonus."""
    dweller = await _create_dweller(async_session, vault)
    room = Room(
        name="Power Generator",
        category=RoomTypeEnum.PRODUCTION,
        ability=SPECIALEnum.STRENGTH,
        output=10,
        tier=1,
    )
    manager = ResourceManager()
    base = manager._calculate_room_production(room, [dweller], 60)

    await _equip_strength_outfit(async_session, dweller.id)
    dweller = await crud.dweller.get(async_session, dweller.id)
    boosted = manager._calculate_room_production(room, [dweller], 60)

    assert boosted == pytest.approx(base * 1.5)  # 15 effective vs 10 stored


@pytest.mark.asyncio
async def test_equipping_never_writes_the_stored_stat(async_session, vault) -> None:
    """The bonus is effective-only: the stored SPECIAL stays the trained value."""
    dweller = await _create_dweller(async_session, vault)
    assert dweller.strength == 10

    await _equip_strength_outfit(async_session, dweller.id)
    dweller = await crud.dweller.get(async_session, dweller.id)

    assert dweller.strength == 10
    assert effective_stat(dweller, "strength") == 15


@pytest.mark.asyncio
async def test_effective_stat_is_not_capped_at_ten(async_session, vault) -> None:
    """10 + 5 must equal 15 — pin this so it is not 'corrected' to a cap later."""
    dweller = await _create_dweller(async_session, vault, strength=10)
    await _equip_strength_outfit(async_session, dweller.id, strength=5)
    dweller = await crud.dweller.get(async_session, dweller.id)

    assert effective_stat(dweller, "strength") == 15
