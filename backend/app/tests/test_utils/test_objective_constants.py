"""Tests for objective constants and validation."""

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


class TestNormalizeRoomType:
    """Tests for normalize_room_type function."""

    def test_normalize_living_room(self):
        assert normalize_room_type("Living room") == "living_room"
        assert normalize_room_type("living room") == "living_room"
        assert normalize_room_type("living_room") == "living_room"
        assert normalize_room_type("LIVING ROOM") == "living_room"

    def test_normalize_aliases(self):
        assert normalize_room_type("living quarters") == "living_room"
        assert normalize_room_type("living_quarters") == "living_room"
        assert normalize_room_type("quarters") == "living_room"

    def test_normalize_storage(self):
        assert normalize_room_type("storage room") == "storage_room"
        assert normalize_room_type("Storage") == "storage_room"

    def test_normalize_power(self):
        assert normalize_room_type("power generator") == "power_generator"
        assert normalize_room_type("Power Plant") == "power_generator"

    def test_normalize_invalid(self):
        assert normalize_room_type("invalid_room") is None
        assert normalize_room_type("") is None
        assert normalize_room_type(None) is None


class TestValidateTargetEntity:
    """Tests for validate_target_entity function."""

    def test_validate_build_room_type_valid(self):
        errors = validate_target_entity("build", {"room_type": "living_room"})
        assert errors == []

    def test_validate_build_room_type_alias(self):
        errors = validate_target_entity("build", {"room_type": "living quarters"})
        assert errors == []

    def test_validate_build_room_type_invalid(self):
        errors = validate_target_entity("build", {"room_type": "invalid_room"})
        assert len(errors) == 1
        assert "Invalid room_type" in errors[0]

    def test_validate_build_room_type_wildcard(self):
        errors = validate_target_entity("build", {"room_type": "*"})
        assert errors == []

    def test_validate_collect_resource_valid(self):
        errors = validate_target_entity("collect", {"resource_type": "power"})
        assert errors == []
        errors = validate_target_entity("collect", {"resource_type": "caps"})
        assert errors == []
        errors = validate_target_entity("collect", {"resource_type": "any"})
        assert errors == []

    def test_validate_collect_resource_invalid(self):
        errors = validate_target_entity("collect", {"resource_type": "invalid_resource"})
        assert len(errors) == 1
        assert "Invalid resource_type" in errors[0]

    def test_validate_collect_item_valid(self):
        errors = validate_target_entity("collect", {"item_type": "weapon"})
        assert errors == []
        errors = validate_target_entity("collect", {"item_type": "outfit"})
        assert errors == []

    def test_validate_collect_item_invalid(self):
        errors = validate_target_entity("collect", {"item_type": "invalid_item"})
        assert len(errors) == 1
        assert "Invalid item_type" in errors[0]

    def test_validate_reach_valid(self):
        errors = validate_target_entity("reach", {"reach_type": "dweller_count"})
        assert errors == []
        errors = validate_target_entity("reach", {"reach_type": "population"})
        assert errors == []
        errors = validate_target_entity("reach", {"reach_type": "level"})
        assert errors == []

    def test_validate_reach_invalid(self):
        errors = validate_target_entity("reach", {"reach_type": "invalid"})
        assert len(errors) == 1
        assert "Invalid reach_type" in errors[0]

    def test_validate_none(self):
        errors = validate_target_entity("assign", None)
        assert errors == []


class TestValidConstants:
    """Tests that constants are properly defined."""

    def test_valid_room_types_not_empty(self):
        assert len(VALID_ROOM_TYPES) > 0

    def test_living_room_in_valid(self):
        assert "living_room" in VALID_ROOM_TYPES

    def test_storage_room_in_valid(self):
        assert "storage_room" in VALID_ROOM_TYPES

    def test_valid_resource_types_not_empty(self):
        assert len(VALID_RESOURCE_TYPES) > 0

    def test_valid_item_types_not_empty(self):
        assert len(VALID_ITEM_TYPES) > 0

    def test_room_type_aliases_not_empty(self):
        assert len(ROOM_TYPE_ALIASES) > 0

    def test_valid_reach_types_not_empty(self):
        assert len(VALID_REACH_TYPES) > 0

    def test_reach_types_contains_expected(self):
        assert "dweller_count" in VALID_REACH_TYPES
        assert "population" in VALID_REACH_TYPES
        assert "level" in VALID_REACH_TYPES
