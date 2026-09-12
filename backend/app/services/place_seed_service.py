"""Idempotent seed loader for the canonical world-place registry.

Reads ``app/data/places/seed_places.json`` (curated union of the bio place
lists and the procedural pool, plus the NPC vault roster) and ensures one
``WorldLocation`` row per entry. Existing rows win for name/coordinates;
seed-owned descriptions refresh so seed edits never need a migration.
"""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy.exc import IntegrityError

from app.core.enums import PlaceKindEnum
from app.crud.world_location import world_location as world_location_crud
from app.models.world_location import WorldLocation
from app.utils.places import collision_nudge, normalize_place_name, schematic_coords

if TYPE_CHECKING:
    from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

SEED_FILE = Path(__file__).parent.parent / "data" / "places" / "seed_places.json"


@lru_cache(maxsize=1)
def load_seed_entries() -> list[dict[str, Any]]:
    """Load and validate the seed roster (cached)."""
    with SEED_FILE.open(encoding="utf-8") as f:
        entries = json.load(f)
    seen: set[str] = set()
    for entry in entries:
        normalized = normalize_place_name(entry["name"])
        if normalized in seen:
            raise ValueError(f"Duplicate seed place {entry['name']!r}")
        seen.add(normalized)
    return entries


@lru_cache(maxsize=1)
def get_origin_places() -> list[str]:
    """Curated origin display names for bio text scanning."""
    return [entry["name"] for entry in load_seed_entries() if "origin" in entry.get("roles", [])]


@lru_cache(maxsize=1)
def get_visited_places() -> list[str]:
    """Curated visited display names for bio text scanning."""
    return [entry["name"] for entry in load_seed_entries() if "visited" in entry.get("roles", [])]


async def seed_places_from_json(db_session: AsyncSession, *, commit: bool = True) -> int:
    """Ensure one registry row per seed entry; return the inserted count."""
    entries = load_seed_entries()
    occupied = await world_location_crud.get_all_coords(db_session)
    inserted = 0
    for entry in entries:
        normalized = normalize_place_name(entry["name"])
        existing = await world_location_crud.get_registry_by_normalized(db_session, normalized)
        if existing is not None:
            if existing.source == "seed" and entry.get("description") != existing.description:
                existing.description = entry.get("description")
                db_session.add(existing)
            continue
        kind = PlaceKindEnum.VAULT if entry["kind"] == "vault" else PlaceKindEnum.PLACE
        if kind == PlaceKindEnum.VAULT:
            coord_x, coord_y = float(entry["coord_x"]), float(entry["coord_y"])
            vault_number = entry.get("vault_number")
        else:
            coord_x, coord_y = collision_nudge(schematic_coords(normalized), occupied)
            vault_number = None
        occupied.add((round(coord_x, 1), round(coord_y, 1)))
        db_session.add(
            WorldLocation(
                name=entry["name"][:64],
                normalized_name=normalized,
                kind=kind,
                vault_number=vault_number,
                coord_x=coord_x,
                coord_y=coord_y,
                description=entry.get("description"),
                source="seed",
            )
        )
        try:
            await db_session.flush()
        except IntegrityError:
            await db_session.rollback()
            reselect = await world_location_crud.get_registry_by_normalized(db_session, normalized)
            if reselect is None:
                raise
            logger.debug("Seed place %r inserted concurrently; keeping existing row", normalized)
            continue
        inserted += 1
    if commit:
        await db_session.commit()
    return inserted
