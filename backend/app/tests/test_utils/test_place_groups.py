"""Tests for the place-group (archetype) catalog."""

import pytest

from app.utils.place_groups import (
    get_place_group,
    group_for_place_name,
    load_place_groups,
    seeded_place_groups,
    validate_group_key,
)


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
