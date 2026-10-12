"""Roster sources for the incident simulator: real vault snapshots and synthetic defenders.

``snapshot_vault_defenders`` loads a vault's healthy adults through CRUD and
turns each into a ``DefenderProfile`` using the same pure helpers the production
engine uses (``combat_power``, ``damage_reductions``), including the active
hazard-team places the dweller already holds. ``synthetic_defenders`` builds
profiles from small local stubs — never real ``Weapon``/``Outfit``/``Junk``
models (the item-factory architecture guard bans bare constructor calls) — so the
synthetic path is formula-locked to the real game without touching the catalog.
Synthetic outfits are read from the item catalog (resists + SPECIAL) but are
stubs, not ORM rows.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, cast

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DamageChannel, HazardTeam, OutfitTypeEnum
from app.services.combat.incident_sim import DefenderProfile
from app.services.hazard_team_service import TEAM_OUTFIT_NAMES
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


@dataclass(frozen=True)
class _SyntheticOutfit:
    """Catalog-shaped outfit stub exposing what ``combat_power``/``damage_reductions`` read."""

    name: str
    outfit_type: OutfitTypeEnum
    fire_resist: float = 0.0
    radiation_resist: float | None = None
    strength: int = 0
    perception: int = 0
    endurance: int = 0
    charisma: int = 0
    intelligence: int = 0
    agility: int = 0
    luck: int = 0


def _catalog_outfit(name: str) -> _SyntheticOutfit:
    """Build an outfit stub from the real item catalog, so resists never drift from the game."""
    from app.utils.static_data import game_data_store

    data = next((outfit for outfit in game_data_store.outfits if str(outfit.name).lower() == name.lower()), None)
    if data is None:
        raise ValueError(f"Outfit catalog has no {name!r} row")
    declared_radiation = data.radiation_resist
    return _SyntheticOutfit(
        name=str(data.name),
        outfit_type=OutfitTypeEnum(str(data.outfit_type).lower()),
        fire_resist=float(data.fire_resist or 0.0),
        radiation_resist=float(declared_radiation) if declared_radiation is not None else None,
        strength=int(data.strength or 0),
        perception=int(data.perception or 0),
        endurance=int(data.endurance or 0),
        charisma=int(data.charisma or 0),
        intelligence=int(data.intelligence or 0),
        agility=int(data.agility or 0),
        luck=int(data.luck or 0),
    )


class _SyntheticDweller:
    """Minimal dweller stand-in exposing what ``combat_power``/``damage_reductions`` read.

    No real ``Weapon``/``Outfit``/``Junk`` models are constructed; the stub only
    carries the attributes those pure helpers read: SPECIAL stats, level, weapon,
    an optional catalog-shaped outfit stub, and the ``visual_attributes`` that
    identity resolution treats as absent (human baseline, no faction perks).
    """

    def __init__(
        self,
        *,
        avg_special: float,
        avg_weapon_damage: float,
        avg_level: int,
        outfit: _SyntheticOutfit | None = None,
    ) -> None:
        self.strength = avg_special
        self.perception = avg_special
        self.endurance = avg_special
        self.charisma = avg_special
        self.intelligence = avg_special
        self.agility = avg_special
        self.luck = avg_special
        self.level = avg_level
        self.weapon = _SyntheticWeapon(avg_weapon_damage, avg_weapon_damage)
        self.outfit = outfit
        self.visual_attributes = None


def synthetic_defenders(
    count: int,
    *,
    avg_special: float,
    avg_weapon_damage: float,
    avg_level: int,
    hazard_team: HazardTeam | None = None,
    team_size: int = 0,
    outfit_count: int | None = None,
) -> list[DefenderProfile]:
    """Build ``count`` synthetic defender profiles without constructing item models.

    The first ``team_size`` defenders hold an active place on ``hazard_team`` and
    the first ``outfit_count`` (defaulting to ``team_size``) wear the team's
    catalog outfit, mirroring production's ``equip_hazard_outfits``. Splitting the
    two lets the balance playtest isolate the team place from the matching gear:
    gear without a place (``team_size=0``, ``outfit_count>0``) and a place without
    gear (``outfit_count=0``). Power and reductions are computed by the same pure
    helpers the production engine uses (``combat_power``, ``damage_reductions``),
    so the synthetic path is formula-locked to the real game. Health follows the
    dweller max-health formula: ``50 + (level - 1) * hp_gain_per_level``.
    """
    from app.core.game_config import game_config

    max_health = 50 + (avg_level - 1) * game_config.leveling.hp_gain_per_level
    wearing = team_size if outfit_count is None else outfit_count
    team_outfit_data = (
        _catalog_outfit(TEAM_OUTFIT_NAMES[hazard_team]) if hazard_team is not None and wearing > 0 else None
    )
    profiles: list[DefenderProfile] = []
    for index in range(count):
        on_team = hazard_team is not None and index < team_size
        stub = _SyntheticDweller(
            avg_special=avg_special,
            avg_weapon_damage=avg_weapon_damage,
            avg_level=avg_level,
            outfit=team_outfit_data if index < wearing else None,
        )
        profiles.append(
            DefenderProfile(
                label=f"synthetic-{index}",
                power=combat_power(cast("Dweller", stub)),
                max_health=max_health,
                reductions_physical=damage_reductions(stub, DamageChannel.PHYSICAL),
                reductions_fire=damage_reductions(stub, DamageChannel.FIRE),
                reductions_radiation=damage_reductions(stub, DamageChannel.RADIATION),
                teams=frozenset({hazard_team}) if on_team else frozenset(),
            )
        )
    return profiles


async def snapshot_vault_defenders(db_session: AsyncSession, vault_id: UUID4) -> list[DefenderProfile]:
    """Load a vault's healthy adults as defender profiles (weapon/outfit/pet eager-loaded)."""
    from app.crud.dweller import dweller as crud_dweller
    from app.crud.team import team_crud
    from app.crud.vault import vault as vault_crud

    await vault_crud.get(db_session, vault_id)
    dwellers = await crud_dweller.get_healthy_adults_by_vault(db_session, vault_id)
    dweller_ids = [dweller.id for dweller in dwellers]
    active_teams: dict[UUID4, set[HazardTeam]] = {dweller_id: set() for dweller_id in dweller_ids}
    for team in HazardTeam:
        for dweller_id in await team_crud.get_active_hazard_member_ids(db_session, vault_id, team, dweller_ids):
            active_teams[dweller_id].add(team)
    return [
        DefenderProfile(
            label=dweller.display_name,
            power=combat_power(dweller),
            max_health=dweller.effective_max_health,
            reductions_physical=damage_reductions(dweller, DamageChannel.PHYSICAL),
            reductions_fire=damage_reductions(dweller, DamageChannel.FIRE),
            reductions_radiation=damage_reductions(dweller, DamageChannel.RADIATION),
            teams=frozenset(active_teams[dweller.id]),
        )
        for dweller in dwellers
    ]
