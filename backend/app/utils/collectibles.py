"""Collectible catalog: SPECIAL bobbleheads, comics, magazines, and the sets they complete.

Layer-safe (no DB, no services): adding a collectible is a data edit, not a migration. Every
catalog is validated at load so a bad placement fails loud instead of shipping inert, and a set
whose bonus could be paid twice or never completed is an authoring error, not a silent no-op.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Iterable, Mapping
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.core.enums import SPECIAL_STATS
from app.utils.place_groups import get_place_group, group_for_place_name, trade_entry
from app.utils.places import normalize_place_name

DATA_ROOT = Path(__file__).parent.parent / "data" / "collectibles"
CATALOG_FILES: tuple[tuple[str, Path], ...] = (
    ("bobblehead", DATA_ROOT / "bobbleheads.json"),
    ("comic", DATA_ROOT / "comics.json"),
    ("magazine", DATA_ROOT / "magazines.json"),
)
SETS_FILE = DATA_ROOT / "sets.json"
STATIC_ROOT = Path(__file__).parent.parent / "static"
ACTIONS = frozenset({"clear", "salvage"})
PRODUCTION_PCT = "production_pct"
EXPEDITION_LOOT_PCT = "expedition_loot_pct"
MAGAZINE_BOON_INCREMENT = "magazine_boon_increment"
BONUS_TYPES = frozenset({PRODUCTION_PCT, EXPEDITION_LOOT_PCT, MAGAZINE_BOON_INCREMENT})
MAGAZINE = "magazine"


def _label(kind: str) -> str:
    return kind.replace("_", " ").capitalize()


def validate_collectibles(
    entries: list[dict[str, Any]],
    *,
    kind: str,
    known_sets: Mapping[str, dict[str, Any]] | None = None,
    static_root: Path = STATIC_ROOT,
) -> tuple[dict[str, Any], ...]:
    """Validate one catalog file and return its rows; raise ValueError on any authoring error."""
    sets = known_sets if known_sets is not None else sets_by_id()
    label = _label(kind)
    seen: set[str] = set()
    for entry in entries:
        key = entry.get("key")
        if not isinstance(key, str) or not key:
            raise ValueError(f"{label} entries need a string 'key'")
        if key in seen:
            raise ValueError(f"Duplicate {kind} key {key!r}")
        seen.add(key)
        # A wrong kind silently files the row under the other catalog's set bonus.
        if entry.get("kind") != kind:
            raise ValueError(f"{label} {key!r} must declare kind {kind!r}")
        if entry.get("set") not in sets:
            raise ValueError(f"{label} {key!r} references unknown set {entry.get('set')!r}")
        if entry.get("stat") not in SPECIAL_STATS:
            raise ValueError(f"{label} {key!r} has unknown stat {entry.get('stat')!r}")
        amount = entry.get("amount")
        if not isinstance(amount, int) or isinstance(amount, bool) or amount < 1:
            raise ValueError(f"{label} {key!r} needs a positive integer amount")
        action = entry.get("action")
        if action not in ACTIONS:
            raise ValueError(f"{label} {key!r} has unknown action {action!r}")
        if not str(entry.get("description") or "").strip():
            raise ValueError(f"{label} {key!r} needs a description")
        group = get_place_group(group_for_place_name(str(entry.get("location") or "")))
        if group is None:
            raise ValueError(f"{label} {key!r} references unknown seeded place {entry.get('location')!r}")
        if bool(group.get("clearable")) != (action == "clear"):
            raise ValueError(f"{label} {key!r} action {action!r} does not match its place archetype")
        # The map owns one action slot per place and a ready caravan outranks a search, so a
        # salvage site that also trades can hide its own collectible behind the trade button.
        if action == "salvage" and trade_entry(entry["location"]) is not None:
            raise ValueError(
                f"{label} {key!r} sits on tradeable place {entry.get('location')!r}; "
                "a caravan destination hides its salvage behind the trade action"
            )
        image = entry.get("image")
        if not image or not (static_root / image).is_file():
            raise ValueError(f"{label} {key!r} references missing image {image!r}")
    return tuple(entries)


def validate_sets(entries: list[dict[str, Any]]) -> tuple[dict[str, Any], ...]:
    """Validate set definitions: unique ids, a reachable size, a known non-negative bonus."""
    seen: set[str] = set()
    for entry in entries:
        set_id = entry.get("set")
        if not isinstance(set_id, str) or not set_id:
            raise ValueError("Set definitions need a string 'set'")
        if set_id in seen:
            raise ValueError(f"Duplicate set id {set_id!r}")
        seen.add(set_id)
        if not str(entry.get("name") or "").strip():
            raise ValueError(f"Set {set_id!r} needs a name")
        required = entry.get("required")
        if not isinstance(required, int) or isinstance(required, bool) or required < 1:
            raise ValueError(f"Set {set_id!r} needs a positive integer 'required'")
        bonus = entry.get("bonus")
        bonus_type = bonus.get("type") if isinstance(bonus, dict) else bonus
        if bonus_type not in BONUS_TYPES:
            raise ValueError(f"Set {set_id!r} has unknown bonus type {bonus_type!r}")
        value = bonus.get("value") if isinstance(bonus, dict) else None
        if not isinstance(value, int | float) or isinstance(value, bool) or value < 0:
            raise ValueError(f"Set {set_id!r} needs a non-negative bonus value")
        # The shelf bonus is a whole extra point per magazine: half a point has no meaning, and a
        # zero increment would make the completed set indistinguishable from an incomplete one.
        if bonus_type == MAGAZINE_BOON_INCREMENT and (not isinstance(value, int) or value < 1):
            raise ValueError(f"Set {set_id!r} needs a whole positive magazine_boon_increment")
    return tuple(entries)


@lru_cache(maxsize=1)
def load_sets() -> tuple[dict[str, Any], ...]:
    """Every defined set (cached)."""
    with SETS_FILE.open(encoding="utf-8") as handle:
        return validate_sets(json.load(handle))


@lru_cache(maxsize=1)
def sets_by_id() -> dict[str, dict[str, Any]]:
    """Set definitions indexed by id."""
    return {entry["set"]: entry for entry in load_sets()}


def _assert_catalogs_complete(sets: Mapping[str, dict[str, Any]], catalog: list[dict[str, Any]]) -> None:
    """A required count the catalog cannot reach is unreachable content, so refuse it at load."""
    counts = Counter(entry["set"] for entry in catalog)
    for set_id, definition in sets.items():
        if definition["required"] > counts[set_id]:
            raise ValueError(
                f"Set {set_id!r} requires {definition['required']} claims but the catalog holds {counts[set_id]}"
            )


@lru_cache(maxsize=1)
def load_collectibles() -> tuple[dict[str, Any], ...]:
    """Bobbleheads then comics, validated together (cached)."""
    sets = sets_by_id()
    catalog: list[dict[str, Any]] = []
    for kind, path in CATALOG_FILES:
        with path.open(encoding="utf-8") as handle:
            catalog.extend(validate_collectibles(json.load(handle), kind=kind, known_sets=sets))
    # One claim table backs both catalogs, so the key namespace is shared.
    duplicates = [key for key, count in Counter(entry["key"] for entry in catalog).items() if count > 1]
    if duplicates:
        raise ValueError(f"Duplicate collectible key {sorted(duplicates)!r} across catalogs")
    _assert_catalogs_complete(sets, catalog)
    return tuple(catalog)


@lru_cache(maxsize=1)
def collectibles_by_key() -> dict[str, dict[str, Any]]:
    """Catalog indexed by collectible key."""
    return {entry["key"]: entry for entry in load_collectibles()}


def collectible_for_key(key: str) -> dict[str, Any]:
    """Catalog entry for a collectible key; unknown keys raise."""
    try:
        return collectibles_by_key()[key]
    except KeyError:
        raise ValueError(f"Unknown collectible {key!r}") from None


def collectible_for_location(location_name: str, *, action: str | None = None) -> dict[str, Any] | None:
    """The collectible bound to a place by normalized name, optionally only for one action."""
    target = normalize_place_name(location_name)
    return next(
        (
            entry
            for entry in load_collectibles()
            if normalize_place_name(entry["location"]) == target and (action is None or entry["action"] == action)
        ),
        None,
    )


@lru_cache(maxsize=1)
def _set_of_key() -> dict[str, str]:
    return {entry["key"]: entry["set"] for entry in load_collectibles()}


def salvage_ready(*, searched_at: datetime | None) -> bool:
    """Whether a salvage collectible can be taken right now.

    Every salvage collectible — bobblehead, comic and magazine alike — is a one-time find: the
    site stamps ``searched_at`` on the first claim and never clears it. Dispatch validation, the
    map's action slot and the arrival resolver all ask this one predicate, so the map cannot offer
    a search the write path would refuse.
    """
    return searched_at is None


def magazine_boon_amount(entry: Mapping[str, Any], held_keys: Iterable[str]) -> int:
    """The permanent boon one magazine grants: its own amount, plus the completed shelf's increment.

    Derived from the vault's claims at read time — nothing is written when the set completes — so a
    finder who already holds the other magazines gets the larger boon on the very read that finishes
    the shelf.
    """
    held = set_held_counts(held_keys)
    increment = max(
        (
            definition["bonus"]["value"]
            for definition in load_sets()
            if definition["bonus"]["type"] == MAGAZINE_BOON_INCREMENT
            and held[definition["set"]] >= definition["required"]
        ),
        default=0,
    )
    return int(entry["amount"]) + int(increment)


def magazine_boon_bonus(boon: Mapping[str, Any] | None, stat: str) -> int:
    """The dweller's permanent magazine bonus for one stat; 0 when the boon is for another stat.

    The boon never expires, so there is no clock to read and no job to run: a hand-edited or
    malformed row is the only way this returns 0 for a stat the dweller actually holds.
    """
    if not boon or boon.get("stat") != stat:
        return 0
    amount = boon.get("amount")
    if not isinstance(amount, int) or isinstance(amount, bool):
        return 0
    return amount


def set_held_counts(held_keys: Iterable[str]) -> Counter[str]:
    """Claims per set; a key no longer in the catalog counts for nothing."""
    set_of_key = _set_of_key()
    return Counter(set_of_key[key] for key in held_keys if key in set_of_key)


def set_bonus_multiplier(bonus_type: str, held_keys: Iterable[str]) -> float:
    """Product of every completed set's bonus of this type; 1.0 when none is complete."""
    held = set_held_counts(held_keys)
    multiplier = 1.0
    for definition in load_sets():
        bonus = definition["bonus"]
        if bonus["type"] == bonus_type and held[definition["set"]] >= definition["required"]:
            multiplier *= 1 + bonus["value"] / 100
    return multiplier


def set_progress(held_keys: Iterable[str], *, enabled: bool) -> list[dict[str, Any]]:
    """Per-set progress rows for the wire; a bonus is active only while the feature is enabled."""
    held = set_held_counts(held_keys)
    return [
        {
            "set": definition["set"],
            "name": definition["name"],
            "held": held[definition["set"]],
            "required": definition["required"],
            "active": enabled and held[definition["set"]] >= definition["required"],
        }
        for definition in load_sets()
    ]
