"""Loot-table catalog for clearable place groups.

Layer-safe home (no DB, no services) for the per-risk loot pools a cleared map
point draws from. Tables reference item type + rarity floor only — the actual
item catalogs live in ``app/data/items/`` and are resolved by the loot
calculator at roll time, keeping one source of truth per item.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

LOOT_FILE = Path(__file__).parent.parent / "data" / "places" / "place_loot.json"

ITEM_TYPES = {"weapon", "outfit", "junk"}
RARITIES = {"common", "rare", "legendary"}


@lru_cache(maxsize=1)
def load_place_loot() -> dict[str, Any]:
    """Load and validate the loot-table catalog (cached).

    Every table needs a caps range with ``0 <= min <= max`` and a non-empty
    items list whose entries reference a known item type and rarity.
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
        if not isinstance(caps, dict) or not isinstance(caps.get("min"), int) or not isinstance(caps.get("max"), int):
            raise ValueError(  # ruff: ignore[type-check-without-type-error] - authoring errors surface as ValueError uniformly
                f"Loot table {key!r} needs integer caps.min and caps.max"
            )
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
    return data


@lru_cache(maxsize=1)
def loot_table(key: str) -> dict[str, Any] | None:
    """One loot table by key, or None when unknown."""
    return load_place_loot()["tables"].get(key)
