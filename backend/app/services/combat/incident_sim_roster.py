"""Roster sources for the incident simulator: real vault snapshots and synthetic defenders.

``snapshot_vault_defenders`` loads a vault's healthy adults through CRUD and
turns each into a ``DefenderProfile`` using the same pure helpers the production
engine uses (``combat_power``, ``damage_reductions``). ``synthetic_defenders``
builds profiles from small local stubs — never real ``Weapon``/``Outfit``/``Junk``
models (the item-factory architecture guard bans bare constructor calls) — so the
synthetic path is formula-locked to the real game without touching the catalog.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, cast

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DamageChannel
from app.services.combat.incident_sim import DefenderProfile
from app.utils.combat import combat_power
from app.utils.damage_reductions import damage_reductions

if TYPE_CHECKING:
    from app.models.dweller import Dweller

#: Synthetic defenders fight unarmed: the same stat weights the old whole-vault
#: power model used, so ``combat_power`` on a stub reproduces it exactly.
_SYNTHETIC_WEAPON_TYPE = "unarmed"


class _SyntheticWeaponType(StrEnum):
    UNARMED = _SYNTHETIC_WEAPON_TYPE


@dataclass(frozen=True)
class _SyntheticWeapon:
    """Minimal weapon stub exposing what ``combat_power`` reads."""

    damage_min: float
    damage_max: float
    weapon_type: _SyntheticWeaponType = _SyntheticWeaponType.UNARMED


class _SyntheticDweller:
    """Minimal dweller stand-in exposing what ``combat_power``/``damage_reductions`` read.

    No real ``Weapon``/``Outfit``/``Junk`` models are constructed; the stub only
    carries the attributes those pure helpers read: SPECIAL stats, level, weapon,
    and the ``visual_attributes``/``outfit`` that identity resolution treats as
    absent (human baseline, no outfit, no faction perks).
    """

    def __init__(self, *, avg_special: float, avg_weapon_damage: float, avg_level: int) -> None:
        self.strength = avg_special
        self.perception = avg_special
        self.endurance = avg_special
        self.charisma = avg_special
        self.intelligence = avg_special
        self.agility = avg_special
        self.luck = avg_special
        self.level = avg_level
        self.weapon = _SyntheticWeapon(avg_weapon_damage, avg_weapon_damage)
        self.outfit = None
        self.visual_attributes = None


def synthetic_defenders(
    count: int, *, avg_special: float, avg_weapon_damage: float, avg_level: int
) -> list[DefenderProfile]:
    """Build ``count`` synthetic defender profiles without constructing item models.

    Power and reductions are computed by the same pure helpers the production
    engine uses (``combat_power``, ``damage_reductions``), so the synthetic path
    is formula-locked to the real game. Health follows the dweller max-health
    formula: ``50 + (level - 1) * hp_gain_per_level``.
    """
    from app.core.game_config import game_config

    max_health = 50 + (avg_level - 1) * game_config.leveling.hp_gain_per_level
    profiles: list[DefenderProfile] = []
    for index in range(count):
        stub = _SyntheticDweller(avg_special=avg_special, avg_weapon_damage=avg_weapon_damage, avg_level=avg_level)
        profiles.append(
            DefenderProfile(
                label=f"synthetic-{index}",
                power=combat_power(cast("Dweller", stub)),
                max_health=max_health,
                reductions_physical=damage_reductions(stub, DamageChannel.PHYSICAL),
                reductions_fire=damage_reductions(stub, DamageChannel.FIRE),
            )
        )
    return profiles


async def snapshot_vault_defenders(db_session: AsyncSession, vault_id: UUID4) -> list[DefenderProfile]:
    """Load a vault's healthy adults as defender profiles (weapon/outfit eager-loaded)."""
    from app.crud.dweller import dweller as crud_dweller
    from app.crud.vault import vault as vault_crud

    await vault_crud.get(db_session, vault_id)
    dwellers = await crud_dweller.get_healthy_adults_by_vault(db_session, vault_id)
    return [
        DefenderProfile(
            label=dweller.display_name,
            power=combat_power(dweller),
            max_health=dweller.effective_max_health,
            reductions_physical=damage_reductions(dweller, DamageChannel.PHYSICAL),
            reductions_fire=damage_reductions(dweller, DamageChannel.FIRE),
        )
        for dweller in dwellers
    ]
