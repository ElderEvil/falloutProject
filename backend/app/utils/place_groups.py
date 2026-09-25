"""Place-group (archetype) catalog for the world-place registry.

Layer-safe home (no DB, no services) for the wasteland site-type taxonomy: each
group carries shared lore, an icon, and a risk profile, and seeded place names
map onto a group. Instances of one group (many Red Rockets, many Super Duper
Marts) inherit it, so adding a new site type is a data edit rather than code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.utils.place_loot import loot_table
from app.utils.place_seed import load_seed_entries
from app.utils.places import normalize_place_name

GROUPS_FILE = Path(__file__).parent.parent / "data" / "places" / "place_groups.json"


@lru_cache(maxsize=1)
def load_place_groups() -> list[dict[str, Any]]:
    """Load and validate the group catalog (cached).

    Every group needs a unique key, a label, and a description, and every group
    referenced by the seed roster must exist here. Clearable groups additionally
    need a reclear window, a base difficulty, and a loot table that exists in
    ``place_loot.json``; non-clearable groups must carry none of those.
    """
    with GROUPS_FILE.open(encoding="utf-8") as f:
        groups: list[dict[str, Any]] = json.load(f)

    keys: set[str] = set()
    for group in groups:
        key = group["key"]
        if key in keys:
            raise ValueError(f"Duplicate place group {key!r}")
        keys.add(key)
        if not group.get("label") or not group.get("description"):
            raise ValueError(f"Place group {key!r} needs a label and description")

        clearable = group.get("clearable", False)
        if not isinstance(clearable, bool):
            raise ValueError(  # ruff: ignore[type-check-without-type-error] - authoring errors surface as ValueError uniformly
                f"Place group {key!r} needs a boolean 'clearable'"
            )
        if clearable:
            reclear_hours = group.get("reclear_hours")
            base_difficulty = group.get("base_difficulty")
            loot_key = group.get("loot_table")
            if not isinstance(reclear_hours, int) or isinstance(reclear_hours, bool) or reclear_hours < 1:
                raise ValueError(f"Clearable place group {key!r} needs reclear_hours >= 1")
            if not isinstance(base_difficulty, int) or isinstance(base_difficulty, bool) or base_difficulty < 1:
                raise ValueError(f"Clearable place group {key!r} needs base_difficulty >= 1")
            if not isinstance(loot_key, str) or loot_table(loot_key) is None:
                raise ValueError(f"Clearable place group {key!r} references unknown loot table {loot_key!r}")
        else:
            for field in ("reclear_hours", "base_difficulty", "loot_table"):
                if group.get(field) is not None:
                    raise ValueError(f"Non-clearable place group {key!r} must not carry {field}")

    referenced = {entry["group"] for entry in load_seed_entries() if entry.get("group")}
    if unknown := referenced - keys:
        raise ValueError(f"Seed places reference unknown groups: {sorted(unknown)}")
    return groups


@lru_cache(maxsize=1)
def place_groups_by_key() -> dict[str, dict[str, Any]]:
    """Catalog indexed by group key."""
    return {group["key"]: group for group in load_place_groups()}


def validate_group_key(key: str) -> str:
    """Return ``key`` when it exists in the catalog, else raise.

    Called on every path that can persist a group key so an unknown site type
    fails loud instead of reaching storage or a caller's mapping.
    """
    if key not in place_groups_by_key():
        raise ValueError(f"Unknown place group {key!r}")
    return key


@lru_cache(maxsize=1)
def seeded_place_groups() -> dict[str, str]:
    """Normalized seeded place name -> group key, validated against the catalog."""
    mapping = {
        normalize_place_name(entry["name"]): entry["group"] for entry in load_seed_entries() if entry.get("group")
    }
    for key in set(mapping.values()):
        validate_group_key(key)
    return mapping


def group_for_place_name(name: str) -> str | None:
    """Group key for a known seeded place, else None (emergent places stay ungrouped)."""
    return seeded_place_groups().get(normalize_place_name(name))


def get_place_group(key: str | None) -> dict[str, Any] | None:
    """Catalog entry for a group key, or None."""
    return place_groups_by_key().get(key) if key else None
