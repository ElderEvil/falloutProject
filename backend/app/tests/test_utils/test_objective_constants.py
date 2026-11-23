import pytest

from app.utils.objective_constants import (
    ROOM_TYPE_ALIASES,
    VALID_ITEM_TYPES,
    VALID_REACH_TYPES,
    VALID_RESOURCE_TYPES,
    VALID_ROOM_TYPES,
    normalize_room_type,
    validate_target_entity,
)

VALID_TARGETS = [
    ("build", {"room_type": "living_room"}),
    ("collect", {"item_type": "weapon"}),
    ("collect", {"item_type": "outfit"}),
    ("collect", {"item_type": "any"}),
    ("collect", {"item_type": "*"}),
    ("scrap", {"item_type": "weapon", "rarity": "rare"}),
    ("scrap", {"rarity": "legendary"}),
    ("scrap", {"item_type": "any", "rarity": "rare"}),
    ("scrap", {"item_type": "*", "rarity": "any"}),
    ("reach", {"reach_type": "dweller_count"}),
    ("reach", {"reach_type": "population"}),
    ("reach", {"reach_type": "level"}),
]
INVALID_TARGETS = [
    ("build", {"room_type": "invalid_room"}, "Invalid room_type"),
    ("collect", {"resource_type": "invalid_resource"}, "Invalid resource_type"),
    ("collect", {"item_type": "invalid_item"}, "Invalid item_type"),
    ("scrap", {"item_type": "invalid_item"}, "Invalid item_type"),
    ("scrap", {"rarity": "invalid"}, "Invalid rarity"),
    ("reach", {"reach_type": "invalid"}, "Invalid reach_type"),
]


@pytest.mark.parametrize(("action", "target"), VALID_TARGETS)
def test_validate_target_entity_accepts(action: str, target: dict) -> None:
    assert validate_target_entity(action, target) == []


@pytest.mark.parametrize(("action", "target", "message"), INVALID_TARGETS)
def test_validate_target_entity_rejects(action: str, target: dict, message: str) -> None:
    errors = validate_target_entity(action, target)
    assert len(errors) == 1
    assert message in errors[0]


@pytest.mark.parametrize(
    ("collection", "member"),
    [(VALID_ROOM_TYPES, "living_room"), (VALID_ROOM_TYPES, "storage_room")]
    + [(VALID_REACH_TYPES, reach) for reach in ("dweller_count", "population", "level")],
)
def test_valid_collections_include_expected(collection, member: str) -> None:
    for values in (VALID_ROOM_TYPES, VALID_RESOURCE_TYPES, VALID_ITEM_TYPES, ROOM_TYPE_ALIASES, VALID_REACH_TYPES):
        assert len(values) > 0
    assert member in collection
    assert (normalize_room_type("invalid_room"), normalize_room_type(""), normalize_room_type(None)) == (
        None,
        None,
        None,
    )
