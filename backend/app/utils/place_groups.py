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

from app.utils.place_seed import load_seed_entries
from app.utils.places import normalize_place_name

GROUPS_FILE = Path(__file__).parent.parent / "data" / "places" / "place_groups.json"


@lru_cache(maxsize=1)
def load_place_groups() -> list[dict[str, Any]]:
    """Load and validate the group catalog (cached).

    Every group needs a unique key, a label, and a description, and every group
    referenced by the seed roster must exist here.
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

    referenced = {entry["group"] for entry in load_seed_entries() if entry.get("group")}
    if unknown := referenced - keys:
        raise ValueError(f"Seed places reference unknown groups: {sorted(unknown)}")
    return groups


@lru_cache(maxsize=1)
def place_groups_by_key() -> dict[str, dict[str, Any]]:
    """Catalog indexed by group key."""
    return {group["key"]: group for group in load_place_groups()}


@lru_cache(maxsize=1)
def seeded_place_groups() -> dict[str, str]:
    """Normalized seeded place name -> group key."""
    return {normalize_place_name(entry["name"]): entry["group"] for entry in load_seed_entries() if entry.get("group")}


def group_for_place_name(name: str) -> str | None:
    """Group key for a known seeded place, else None (emergent places stay ungrouped)."""
    return seeded_place_groups().get(normalize_place_name(name))


def get_place_group(key: str | None) -> dict[str, Any] | None:
    """Catalog entry for a group key, or None."""
    return place_groups_by_key().get(key) if key else None
