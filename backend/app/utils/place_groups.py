"""Place-group (archetype) catalog for the world-place registry.

Layer-safe (no DB, no services): each group carries shared lore, icon and risk profile;
seeded place names map onto a group, so adding a site type is a data edit, not code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.enums import PlaceKindEnum
from app.core.game_config import game_config
from app.utils.place_loot import loot_table
from app.utils.place_seed import load_seed_entries
from app.utils.places import normalize_place_name

GROUPS_FILE = Path(__file__).parent.parent / "data" / "places" / "place_groups.json"

DEFAULT_EMERGENT_GROUP = "wasteland_site"


@lru_cache(maxsize=1)
def load_place_groups() -> list[dict[str, Any]]:
    """Load and validate the group catalog (cached).

    Groups need unique key, label, description; seed-roster references must exist. Clearable
    groups additionally need a reclear window, base difficulty, an XP reward and a loot table
    present in place_loot.json; non-clearable groups must carry none of those.
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
            xp_reward = group.get("xp_reward")
            if not isinstance(reclear_hours, int) or isinstance(reclear_hours, bool) or reclear_hours < 1:
                raise ValueError(f"Clearable place group {key!r} needs reclear_hours >= 1")
            if not isinstance(base_difficulty, int) or isinstance(base_difficulty, bool) or base_difficulty < 1:
                raise ValueError(f"Clearable place group {key!r} needs base_difficulty >= 1")
            if not isinstance(loot_key, str) or loot_table(loot_key) is None:
                raise ValueError(f"Clearable place group {key!r} references unknown loot table {loot_key!r}")
            if not isinstance(xp_reward, int) or isinstance(xp_reward, bool) or xp_reward < 0:
                raise ValueError(f"Clearable place group {key!r} needs xp_reward >= 0")
        else:
            for field in ("reclear_hours", "base_difficulty", "loot_table", "xp_reward"):
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
    """Return key when it exists in the catalog, else raise; called on every persist path so
    unknown site types fail loud.
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


def effective_place_group(group_key: str | None, kind: PlaceKindEnum | None) -> dict[str, Any] | None:
    """Catalog entry for a place: its own group, or the default archetype for an ungrouped PLACE."""
    group = get_place_group(group_key)
    if group is not None:
        return group
    if group_key:
        return None
    if kind == PlaceKindEnum.PLACE and game_config.features.emergent_sites:
        return get_place_group(DEFAULT_EMERGENT_GROUP)
    return None
