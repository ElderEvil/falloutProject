"""Bobblehead catalog: SPECIAL collectibles and the places that hold them.

Layer-safe (no DB, no services): adding a collectible is a data edit, not a migration.
The catalog is validated at load so a bad placement fails loud instead of shipping inert.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.enums import SPECIAL_STATS
from app.utils.place_groups import get_place_group, group_for_place_name
from app.utils.places import normalize_place_name

CATALOG_FILE = Path(__file__).parent.parent / "data" / "collectibles" / "bobbleheads.json"
STATIC_ROOT = Path(__file__).parent.parent / "static"
ACTIONS = frozenset({"clear", "salvage"})


def validate_bobbleheads(
    entries: list[dict[str, Any]], *, static_root: Path = STATIC_ROOT
) -> tuple[dict[str, Any], ...]:
    """Validate catalog rows and return them as a tuple; raise ValueError on any authoring error."""
    seen: set[str] = set()
    for entry in entries:
        key = entry.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError("Bobblehead entries need a string 'key'")
        if key in seen:
            raise ValueError(f"Duplicate bobblehead key {key!r}")
        seen.add(key)
        if entry.get("stat") not in SPECIAL_STATS:
            raise ValueError(f"Bobblehead {key!r} has unknown stat {entry.get('stat')!r}")
        amount = entry.get("amount")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
            raise ValueError(f"Bobblehead {key!r} needs a positive integer amount")
        action = entry.get("action")
        if action not in ACTIONS:
            raise ValueError(f"Bobblehead {key!r} has unknown action {action!r}")
        if not str(entry.get("description") or "").strip():
            raise ValueError(f"Bobblehead {key!r} needs a description")
        group = get_place_group(group_for_place_name(str(entry.get("location") or "")))
        if group is None:
            raise ValueError(f"Bobblehead {key!r} references unknown seeded place {entry.get('location')!r}")
        if bool(group.get("clearable")) != (action == "clear"):
            raise ValueError(f"Bobblehead {key!r} action {action!r} does not match its place archetype")
        image = entry.get("image")
        if not image or not (static_root / image).is_file():
            raise ValueError(f"Bobblehead {key!r} references missing image {image!r}")
    return tuple(entries)


@lru_cache(maxsize=1)
def load_bobbleheads() -> tuple[dict[str, Any], ...]:
    """The seven bobblehead catalog entries (cached)."""
    with CATALOG_FILE.open(encoding="utf-8") as handle:
        return validate_bobbleheads(json.load(handle))


@lru_cache(maxsize=1)
def bobbleheads_by_key() -> dict[str, dict[str, Any]]:
    """Catalog indexed by collectible key."""
    return {entry["key"]: entry for entry in load_bobbleheads()}


def bobblehead_for_key(key: str) -> dict[str, Any]:
    """Catalog entry for a collectible key; unknown keys raise."""
    try:
        return bobbleheads_by_key()[key]
    except KeyError:
        raise ValueError(f"Unknown bobblehead {key!r}") from None


def bobblehead_for_location(location_name: str) -> dict[str, Any] | None:
    """The bobblehead bound to a place, matched by its normalized name."""
    target = normalize_place_name(location_name)
    return next((entry for entry in load_bobbleheads() if normalize_place_name(entry["location"]) == target), None)
