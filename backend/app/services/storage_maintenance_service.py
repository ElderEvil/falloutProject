"""Catalog ladders and vault-wide storage protection; no database queries."""

from collections import defaultdict
from functools import lru_cache

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.weapon import Weapon
from app.options.identity_modifiers import effective_stat, identity_modifiers_for
from app.schemas.storage import StorageMaintenanceRead
from app.schemas.weapon import LadderEntry
from app.services.catalog_service import load_weapons
from app.utils.item_factory import build_weapon
from app.utils.weapon_naming import family_key


@lru_cache(maxsize=1)
def _ladders() -> dict[str, tuple[LadderEntry, ...]]:
    families: dict[str, list[LadderEntry]] = defaultdict(list)
    for raw in load_weapons():
        weapon = build_weapon(raw, raw["rarity"])
        entry = LadderEntry(
            name=weapon.name,
            rarity=weapon.rarity,
            value=weapon.value,
            weapon_type=weapon.weapon_type,
            weapon_subtype=weapon.weapon_subtype,
            stat=weapon.stat,
            damage_min=weapon.damage_min,
            damage_max=weapon.damage_max,
        )
        families[family_key(entry.name)].append(entry)
    return {
        key: tuple(sorted(entries, key=lambda e: (e.damage_min + e.damage_max, e.value or 0, e.name)))
        for key, entries in families.items()
    }


@lru_cache(maxsize=1)
def eligible_weapon_names() -> tuple[str, ...]:
    return tuple(
        sorted(entry.name.strip().casefold() for ladder in _ladders().values() if len(ladder) > 1 for entry in ladder)
    )


def ladder_for(name: str) -> tuple[LadderEntry, ...] | None:
    if name.strip().casefold() not in eligible_weapon_names():
        return None
    return _ladders()[family_key(name)]


def adjacent(name: str, direction: int) -> LadderEntry | None:
    ladder = ladder_for(name)
    if ladder is None or direction == 0:
        return None
    index = next(i for i, entry in enumerate(ladder) if entry.name.casefold() == name.strip().casefold()) + direction
    return ladder[index] if 0 <= index < len(ladder) else None


def worker_endurance(workers: list[Dweller]) -> float:
    return sum(effective_stat(d, "endurance") * (1 + identity_modifiers_for(d).production_pct) for d in workers)


def trial_odds(total_end: float) -> tuple[int, float]:
    config = game_config.storage
    delta = total_end / config.end_for_full_protection - 1
    # Keep exact decimal boundaries (e.g. 19.6 END) inside the deadband after float rounding.
    if abs(delta) <= config.deadband + 1e-12:
        return 0, 0.0
    return (1 if delta > 0 else -1), min(abs(delta), 1.0) * config.chance_at_extreme


def roll_allowed(weapon: Weapon, target: LadderEntry, direction: int) -> bool:
    config = game_config.storage
    return direction < 0 or (config.allow_upgrade and (config.allow_rarity_upgrade or target.rarity == weapon.rarity))


async def summary(db: AsyncSession, vault_id: UUID4) -> StorageMaintenanceRead:
    workers = await crud.dweller.list_storage_workers(db, vault_id)
    total = worker_endurance(workers)
    direction, chance = trial_odds(total)
    config = game_config.storage
    if direction > 0 and not config.allow_upgrade:
        direction, chance = 0, 0.0
    return StorageMaintenanceRead(
        enabled=config.maintenance_enabled,
        worker_count=len(workers),
        total_endurance=total,
        protection_pct=min(total / config.end_for_full_protection, 1.0) * 100,
        mode="disabled" if not config.maintenance_enabled else {-1: "rusting", 0: "stable", 1: "improving"}[direction],
        hourly_chance=chance if config.maintenance_enabled and (direction < 0 or config.allow_upgrade) else 0,
        trial_interval_seconds=config.trial_interval_seconds,
    )
