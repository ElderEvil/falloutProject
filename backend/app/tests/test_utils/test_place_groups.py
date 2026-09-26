"""Tests for the place-group (archetype) catalog."""

import json

import pytest

from app.utils.place_groups import (
    GROUPS_FILE,
    get_place_group,
    group_for_place_name,
    load_place_groups,
    place_groups_by_key,
    seeded_place_groups,
    validate_group_key,
)

CLEARABLE_GROUPS = {
    "gas_station",
    "supermarket",
    "factory",
    "metro",
    "military",
    "brotherhood_outpost",
    "research",
    "power",
    "entertainment",
    "vault_tec",
    "ruin",
    "exclusion_zone",
}
NON_CLEARABLE_GROUPS = {"settlement", "city", "landmark", "region"}


def test_catalog_is_valid_and_covers_seeded_groups() -> None:
    """Every group is complete and every seeded group reference resolves."""
    groups = load_place_groups()
    keys = {group["key"] for group in groups}
    assert {"gas_station", "supermarket", "settlement", "vault_tec"} <= keys
    for group in groups:
        assert group["label"]
        assert group["description"]
        assert group["icon"]
    assert set(seeded_place_groups().values()) <= keys


def test_seeded_names_resolve_to_their_group() -> None:
    """Group lookup normalizes names and leaves unknown (emergent) places ungrouped."""
    assert group_for_place_name("Red Rocket") == "gas_station"
    assert group_for_place_name("  RED ROCKET ") == "gas_station"
    assert group_for_place_name("Super Duper Mart") == "supermarket"
    assert group_for_place_name("An Emergent Place") is None


def test_groups_can_have_multiple_instances() -> None:
    """A group hosts several named instances, which is the point of the taxonomy."""
    by_group: dict[str, list[str]] = {}
    for name, key in seeded_place_groups().items():
        by_group.setdefault(key, []).append(name)
    assert len(by_group["gas_station"]) >= 3
    assert len(by_group["supermarket"]) >= 2


def test_get_place_group_returns_catalog_entry() -> None:
    entry = get_place_group("gas_station")
    assert entry is not None
    assert entry["label"] == "Gas Station"
    assert get_place_group(None) is None
    assert get_place_group("not_a_group") is None


def test_validate_group_key_accepts_known_and_rejects_unknown() -> None:
    """Every write path validates the key against the catalog."""
    assert validate_group_key("gas_station") == "gas_station"
    with pytest.raises(ValueError, match="Unknown place group"):
        validate_group_key("not_a_group")


def test_quiet_zone_resolves_to_the_exclusion_zone_group() -> None:
    """The seeded Quiet Zone is grouped as a Restricted Exclusion Site."""
    assert group_for_place_name("The Quiet Zone") == "exclusion_zone"
    entry = get_place_group("exclusion_zone")
    assert entry is not None
    assert entry["label"] == "Restricted Exclusion Site"


def test_clearable_groups_carry_valid_clear_fields() -> None:
    """Every clearable group has a reclear window, a difficulty, and a resolvable loot table."""
    groups = {group["key"]: group for group in load_place_groups()}
    assert set(groups) == CLEARABLE_GROUPS | NON_CLEARABLE_GROUPS
    for key in CLEARABLE_GROUPS:
        group = groups[key]
        assert group["clearable"] is True
        assert isinstance(group["reclear_hours"], int)
        assert group["reclear_hours"] >= 1
        assert isinstance(group["base_difficulty"], int)
        assert group["base_difficulty"] >= 1
        assert isinstance(group["loot_table"], str)
        assert group["loot_table"]


def test_non_clearable_groups_carry_no_clear_fields() -> None:
    """Landmarks, cities, settlements, and regions are never clearable."""
    groups = {group["key"]: group for group in load_place_groups()}
    for key in NON_CLEARABLE_GROUPS:
        group = groups[key]
        assert group["clearable"] is False
        assert group["reclear_hours"] is None
        assert group["base_difficulty"] is None
        assert group["loot_table"] is None


def test_reclear_hours_and_difficulty_follow_risk_bands() -> None:
    """Low/medium/high risk map to 48/72/96 hours and 2/3/4 difficulty."""
    expected = {"low": (48, 2), "medium": (72, 3), "high": (96, 4)}
    for group in load_place_groups():
        if not group["clearable"]:
            continue
        hours, difficulty = expected[group["risk"]]
        assert group["reclear_hours"] == hours
        assert group["base_difficulty"] == difficulty
        assert group["loot_table"] == group["risk"]


def _write_groups(tmp_path, groups: list[dict]) -> pytest.MonkeyPatch:
    """Point the loader at a scratch catalog and reset its cache."""
    scratch = tmp_path / "place_groups.json"
    scratch.write_text(json.dumps(groups), encoding="utf-8")
    load_place_groups.cache_clear()
    place_groups_by_key.cache_clear()
    seeded_place_groups.cache_clear()
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr("app.utils.place_groups.GROUPS_FILE", scratch)
    return monkeypatch


def test_clearable_group_missing_reclear_hours_is_rejected(tmp_path) -> None:
    groups = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    for group in groups:
        if group["key"] == "gas_station":
            group.pop("reclear_hours")
    monkeypatch = _write_groups(tmp_path, groups)
    try:
        with pytest.raises(ValueError, match="reclear_hours"):
            load_place_groups()
    finally:
        monkeypatch.undo()
        load_place_groups.cache_clear()


def test_clearable_group_with_unknown_loot_table_is_rejected(tmp_path) -> None:
    groups = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    for group in groups:
        if group["key"] == "gas_station":
            group["loot_table"] = "not_a_table"
    monkeypatch = _write_groups(tmp_path, groups)
    try:
        with pytest.raises(ValueError, match="unknown loot table"):
            load_place_groups()
    finally:
        monkeypatch.undo()
        load_place_groups.cache_clear()


def test_non_clearable_group_carrying_clear_fields_is_rejected(tmp_path) -> None:
    groups = json.loads(GROUPS_FILE.read_text(encoding="utf-8"))
    for group in groups:
        if group["key"] == "settlement":
            group["reclear_hours"] = 48
    monkeypatch = _write_groups(tmp_path, groups)
    try:
        with pytest.raises(ValueError, match="must not carry reclear_hours"):
            load_place_groups()
    finally:
        monkeypatch.undo()
        load_place_groups.cache_clear()
