"""Loot-table catalog for clearable place groups.

Layer-safe (no DB, no services); tables reference item type, rarity floor and optional item
categories — item catalogs live in app/data/items/ and resolve at roll time (one source of truth
per item).
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.enums import JunkTypeEnum, WeaponTypeEnum

LOOT_FILE = Path(__file__).parent.parent / "data" / "places" / "place_loot.json"

ITEM_TYPES = {"weapon", "outfit", "junk"}
RARITIES = {"common", "rare", "legendary"}
JUNK_TYPES = {member.value for member in JunkTypeEnum}
WEAPON_TYPES = {member.value for member in WeaponTypeEnum}


def _is_int(value: Any) -> bool:
    """True for a real int; bools are ints in Python, but a boolean cap is an authoring error."""
    return isinstance(value, int) and not isinstance(value, bool)


@lru_cache(maxsize=1)
def load_place_loot() -> dict[str, Any]:
    """Load and validate the loot-table catalog (cached).

    Every table needs a caps range with 0 <= min <= max and a non-empty items list
    referencing known item types and rarities.
    """
    with LOOT_FILE.open(encoding="utf-8") as f:
        data: dict[str, Any] = json.load(f)

    tables = data.get("tables")
    if not isinstance(tables, dict) or not tables:
        raise ValueError("place_loot.json needs a non-empty 'tables' object")

    for key, table in tables.items():
        if not isinstance(table, dict):
            raise ValueError(  # ruff: ignore[type-check-without-type-error] - authoring errors surface as ValueError uniformly
                f"Loot table {key!r} must be an object"
            )
        caps = table.get("caps")
        if not isinstance(caps, dict) or not _is_int(caps.get("min")) or not _is_int(caps.get("max")):
            raise ValueError(f"Loot table {key!r} needs integer caps.min and caps.max")
        if caps["min"] < 0 or caps["min"] > caps["max"]:
            raise ValueError(f"Loot table {key!r} caps must satisfy 0 <= min <= max")
        items = table.get("items")
        if not isinstance(items, list) or not items:
            raise ValueError(f"Loot table {key!r} needs a non-empty items list")
        for item in items:
            if not isinstance(item, dict) or item.get("type") not in ITEM_TYPES:
                raise ValueError(f"Loot table {key!r} has an item with unknown type")
            if item.get("rarity") not in RARITIES:
                raise ValueError(f"Loot table {key!r} has an item with unknown rarity")
            _validate_category_filter(key, item, "junk_types", "junk", JUNK_TYPES)
            _validate_category_filter(key, item, "weapon_types", "weapon", WEAPON_TYPES)
    return data


def _validate_category_filter(
    table_key: str, item: dict[str, Any], field: str, item_type: str, allowed: set[str]
) -> None:
    """Reject a filter on the wrong item type or naming a category the catalog cannot produce."""
    values = item.get(field)
    if values is None:
        return
    if item.get("type") != item_type:
        raise ValueError(f"Loot table {table_key!r} item {field} only applies to {item_type} entries")
    if not isinstance(values, list) or not values or any(not isinstance(value, str) for value in values):
        raise ValueError(f"Loot table {table_key!r} item {field} must be a non-empty list of strings")
    if unknown := {value.lower() for value in values} - allowed:
        raise ValueError(f"Loot table {table_key!r} item {field} has unknown values {sorted(unknown)}")


@lru_cache(maxsize=1)
def loot_table(key: str) -> dict[str, Any] | None:
    """One loot table by key, or None when unknown."""
    return load_place_loot()["tables"].get(key)
