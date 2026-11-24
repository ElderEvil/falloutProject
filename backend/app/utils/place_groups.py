"""Place-group (archetype) catalog for the world-place registry.

Layer-safe (no DB, no services): each group carries shared lore, icon and risk profile;
seeded place names map onto a group, so adding a site type is a data edit, not code.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.enums import JunkTypeEnum, PlaceKindEnum
from app.core.game_config import game_config
from app.utils.place_loot import loot_table
from app.utils.place_seed import load_seed_entries
from app.utils.places import normalize_place_name

GROUPS_FILE = Path(__file__).parent.parent / "data" / "places" / "place_groups.json"
TRADE_FILE = Path(__file__).parent.parent / "data" / "places" / "settlement_trade.json"

# Tradeable groups and their caravan tier: a settlement is tier 1, a city tier 2.
TRADE_GROUPS = {"settlement": 1, "city": 2}

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


def location_xp_for(group: dict[str, Any] | None, tier: int) -> int:
    """Base XP per survivor for clearing this archetype at a tier, before the return bonuses."""
    base = (group or {}).get("xp_reward") or 0
    return int(base * (1 + game_config.exploration.dispatch.reward_per_tier * tier)) if base else 0


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


@lru_cache(maxsize=1)
def load_settlement_trade() -> dict[str, dict[str, Any]]:
    """Caravan shipment catalog, keyed by normalized place name (cached).

    Every tradeable seed place needs one entry: a real junk material, a unit band, and a
    comparable clearable site that benchmarks the half-yield guardrail. A tradeable place
    missing from the catalog is an authoring error, not a silent gap — an inert settlement
    is the bug this catalog exists to fix.
    """
    with TRADE_FILE.open(encoding="utf-8") as f:
        entries: list[dict[str, Any]] = json.load(f)["places"]

    # A material with no common junk item would pass the enum check and then ship nothing at
    # resolution time — after the fee was charged. Validate against the same common-item rule the
    # resolver uses, so a catalog edit fails here instead of costing a player caps.
    from app.utils.static_data import game_data_store

    junk = {member.value for member in JunkTypeEnum}
    shippable = {
        str(item.junk_type).lower() for item in game_data_store.junk_items if str(item.rarity).lower() == "common"
    }
    groups = seeded_place_groups()
    trade: dict[str, dict[str, Any]] = {}
    for entry in entries:
        name = entry["place"]
        key = normalize_place_name(name)
        if key in trade:
            raise ValueError(f"Duplicate caravan shipment for {name!r}")
        group_key = groups.get(key)
        if group_key not in TRADE_GROUPS:
            raise ValueError(f"Caravan shipment for {name!r} needs a settlement or city seed place")
        if entry.get("material") not in junk:
            raise ValueError(f"Caravan shipment for {name!r} needs a known junk material")
        if entry["material"] not in shippable:
            raise ValueError(f"Caravan shipment for {name!r} names a material with no common junk item")
        band = entry.get("band")
        if not (
            isinstance(band, list)
            and len(band) == 2
            and all(isinstance(v, int) and not isinstance(v, bool) for v in band)
            and 1 <= band[0] <= band[1] <= 10
        ):
            raise ValueError(f"Caravan shipment for {name!r} needs an integer band 1 <= min <= max <= 10")
        comparable = get_place_group(groups.get(normalize_place_name(entry.get("comparable") or "")))
        if comparable is None or not comparable.get("clearable"):
            raise ValueError(f"Caravan shipment for {name!r} needs a clearable comparable site")
        trade[key] = entry

    if missing := sorted(name for name, group in groups.items() if group in TRADE_GROUPS and name not in trade):
        raise ValueError(f"Tradeable places without a caravan shipment: {missing}")
    return trade


def trade_entry(name: str) -> dict[str, Any] | None:
    """Caravan shipment for a place name, else None when the place does not trade."""
    return load_settlement_trade().get(normalize_place_name(name))


def trade_tier(group: dict[str, Any] | None) -> int:
    """Caravan tier for a place group: settlement 1, city 2, anything else 0 (not tradeable)."""
    return TRADE_GROUPS.get((group or {}).get("key") or "", 0)


def trade_caps_cost(group: dict[str, Any] | None) -> int:
    """Flat per-tier caravan fee: a city costs more than a settlement, untradeable places nothing."""
    cfg = game_config.exploration.caravan
    match trade_tier(group):
        case 1:
            return cfg.caps_cost_settlement
        case 2:
            return cfg.caps_cost_city
        case _:
            return 0


def trade_revisit_hours(group: dict[str, Any] | None) -> int:
    """Cooldown after a caravan; 0 for an untradeable place.

    A city charges double the fee and hauls the same shipment, so its edge is trading more often.
    """
    cfg = game_config.exploration.caravan
    match trade_tier(group):
        case 1:
            return cfg.revisit_hours_settlement
        case 2:
            return cfg.revisit_hours_city
        case _:
            return 0
