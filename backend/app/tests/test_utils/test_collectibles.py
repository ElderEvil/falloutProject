from __future__ import annotations

import pytest

from app.core.enums import SPECIAL_STATS
from app.utils.collectibles import STATIC_ROOT, load_bobbleheads, validate_bobbleheads


def _entry(**overrides: object) -> dict[str, object]:
    entry: dict[str, object] = {
        "key": "test",
        "name": "Test Bobblehead",
        "stat": "strength",
        "amount": 1,
        "image": "bobblehead_images/strength.png",
        "location": "Poseidon Energy",
        "action": "clear",
        "description": "Test.",
    }
    entry.update(overrides)
    return entry


def test_catalog_covers_every_special_stat_once() -> None:
    catalog = load_bobbleheads()

    assert len(catalog) == 7
    assert {entry["stat"] for entry in catalog} == set(SPECIAL_STATS)
    assert {entry["key"] for entry in catalog if entry["action"] == "salvage"} == {"perception", "endurance"}


def test_catalog_images_exist() -> None:
    assert all((STATIC_ROOT / str(entry["image"])).is_file() for entry in load_bobbleheads())


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"stat": "charisma_plus"}, "unknown stat"),
        ({"location": "Nowhere At All"}, "unknown seeded place"),
        ({"action": "salvage"}, "does not match its place archetype"),
        ({"image": "bobblehead_images/missing.png"}, "missing image"),
        ({"description": "  "}, "needs a description"),
    ],
)
def test_validation_rejects_bad_rows(overrides: dict[str, object], message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validate_bobbleheads([_entry(**overrides)])


def test_validation_rejects_duplicate_keys() -> None:
    with pytest.raises(ValueError, match="Duplicate bobblehead key"):
        validate_bobbleheads([_entry(), _entry()])
