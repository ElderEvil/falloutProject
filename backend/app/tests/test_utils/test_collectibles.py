from __future__ import annotations

import pytest

from app.core.enums import SPECIAL_STATS
from app.utils.collectibles import (
    STATIC_ROOT,
    collectible_for_location,
    load_collectibles,
    load_sets,
    validate_collectibles,
    validate_sets,
)


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "key": "test",
        "name": "Test Comic",
        "stat": "strength",
        "amount": 1,
        "image": "comic_images/grognak.png",
        "kind": "comic",
        "set": "comics",
        "location": "Megaton",
        "action": "salvage",
        "description": "Test.",
    }
    entry.update(overrides)
    return entry


def _magazine(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "key": "test_magazine",
        "name": "Test Magazine",
        "stat": "perception",
        "amount": 2,
        "duration_hours": 6,
        "image": "magazine_images/guns_and_bullets.png",
        "kind": "magazine",
        "set": "magazines",
        "location": "National Archives",
        "action": "salvage",
        "description": "Test.",
    }
    entry.update(overrides)
    return entry


def _set(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "set": "comics",
        "name": "The Full Run",
        "required": 3,
        "bonus": {"type": "expedition_loot_pct", "value": 10},
    }
    entry.update(overrides)
    return entry


def test_the_comic_catalog_validates_and_binds_inert_places() -> None:
    comics = [entry for entry in load_collectibles() if entry["kind"] == "comic"]

    assert {entry["key"] for entry in comics} == {"grognak_barbarian", "astounding_tales", "silver_shroud"}
    assert {entry["stat"] for entry in comics} == {"strength", "luck", "charisma"}
    assert all(collectible_for_location(str(entry["location"]), action="salvage") == entry for entry in comics)


def test_the_bobblehead_catalog_covers_every_special_stat_once() -> None:
    bobbleheads = [entry for entry in load_collectibles() if entry["kind"] == "bobblehead"]

    assert len(bobbleheads) == 7
    assert {entry["stat"] for entry in bobbleheads} == set(SPECIAL_STATS)
    assert {entry["key"] for entry in bobbleheads if entry["action"] == "salvage"} == {"perception", "endurance"}


def test_the_magazine_catalog_carries_a_buff_length_and_binds_inert_places() -> None:
    magazines = [entry for entry in load_collectibles() if entry["kind"] == "magazine"]

    assert {entry["key"] for entry in magazines} == {"guns_and_bullets", "tesla_science", "wasteland_survival_guide"}
    assert {entry["duration_hours"] for entry in magazines} == {6}
    assert all(collectible_for_location(str(entry["location"]), action="salvage") == entry for entry in magazines)


@pytest.mark.parametrize("duration", [None, 0, 6.5, "6"], ids=["missing", "zero", "fractional", "string"])
def test_a_magazine_without_whole_positive_hours_is_refused(duration: object) -> None:
    entry = _magazine(**({} if duration is None else {"duration_hours": duration}))
    if duration is None:
        del entry["duration_hours"]

    with pytest.raises(ValueError, match="positive integer duration_hours"):
        validate_collectibles([entry], kind="magazine")


def test_every_catalog_image_exists() -> None:
    assert all((STATIC_ROOT / str(entry["image"])).is_file() for entry in load_collectibles())


def test_set_definitions_load_from_disk() -> None:
    definitions = {definition["set"]: definition for definition in load_sets()}

    assert definitions["comics"]["bonus"] == {"type": "expedition_loot_pct", "value": 10}
    assert definitions["bobbleheads"]["bonus"] == {"type": "production_pct", "value": 5}
    assert definitions["magazines"]["bonus"] == {"type": "magazine_buff_hours", "value": 12}
    assert sum(definition["required"] for definition in definitions.values()) == len(load_collectibles())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"stat": "charisma_plus"}, "unknown stat"),
        ({"location": "Nowhere At All"}, "unknown seeded place"),
        ({"location": "Poseidon Energy"}, "does not match its place archetype"),
        ({"image": "comic_images/missing.png"}, "missing image"),
        ({"description": "  "}, "needs a description"),
        ({"set": "mystery"}, "references unknown set"),
        ({"kind": "bobblehead"}, "must declare kind 'comic'"),
    ],
)
def test_validation_rejects_bad_collectibles(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_collectibles([_entry(**overrides)], kind="comic")


def test_validation_rejects_duplicate_keys() -> None:
    with pytest.raises(ValueError, match="Duplicate comic key"):
        validate_collectibles([_entry(), _entry()], kind="comic")


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"required": 0}, "positive integer"),
        ({"bonus": {"type": "loot_pct", "value": 10}}, "unknown bonus type"),
        ({"bonus": {"type": "expedition_loot_pct", "value": -1}}, "non-negative bonus value"),
        # Buff hours are whole hours: the bonus replaces the magazine's duration, it never scales it.
        ({"bonus": {"type": "magazine_buff_hours", "value": 12.5}}, "whole positive magazine_buff_hours"),
        ({"bonus": {"type": "magazine_buff_hours", "value": 0}}, "whole positive magazine_buff_hours"),
    ],
)
def test_set_validation_rejects_bad_rows(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_sets([_set(**overrides)])


def test_set_validation_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="Duplicate set id"):
        validate_sets([_set(), _set()])
