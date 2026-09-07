"""Tests for the unified DwellerVisualAttributes schema."""

import pytest

from app.schemas.dweller import DwellerVisualAttributes, DwellerVisualAttributesInput
from app.services.dweller_service import dweller_service


def test_unified_schema_has_all_fields() -> None:
    """Unified schema should contain both input and AI-generated fields."""
    fields = DwellerVisualAttributes.model_fields

    assert "race" in fields
    assert "faction" in fields

    assert "height" in fields
    assert "appearance" in fields
    assert "clothing_style" in fields
    assert "distinguishing_features" in fields

    assert "build" in fields  # was body_type in input
    assert "hair_style" in fields  # was haircut in input

    assert "skin_tone" in fields
    assert "eye_color" in fields
    assert "hair_color" in fields
    assert "facial_hair" in fields
    assert "makeup" in fields

    # Input-only fields
    assert "headgear" in fields
    assert "expression" in fields
    assert "accessory" in fields
    assert "object_held" in fields
    assert "pose" in fields
    assert "background" in fields
    assert "voice_line_text" in fields
    assert "voice_line_url" in fields
    assert "age" in fields
    assert "state_of_being" in fields

    # Count total fields
    assert len(fields) == 23


def test_canonical_field_names() -> None:
    """Old names (haircut, body_type) should NOT be in the schema."""
    fields = DwellerVisualAttributes.model_fields
    assert "haircut" not in fields, "haircut should be renamed to hair_style"
    assert "body_type" not in fields, "body_type should be renamed to build"


def test_identity_options_match_the_canonical_faction_restrictions() -> None:
    """Clients receive only the combinations the API accepts for identity editing."""
    options = dweller_service.get_identity_options()

    assert options.races == ["human", "ghoul", "super_mutant", "synth"]
    assert options.factions_by_race["synth"] == ["the_institute", "railroad", "none"]
    assert options.states_by_race["ghoul"] == ["sane", "wild", "feral"]
    assert options.states_by_race["super_mutant"] == ["mild", "average", "behemoth"]


def test_normalizes_single_item_provider_lists_for_scalar_attributes() -> None:
    """Local models sometimes wrap every structured scalar in a one-item list."""
    attributes = DwellerVisualAttributes.model_validate(
        {
            "race": ["human"],
            "faction": ["vault_dweller"],
            "build": ["athletic"],
            "skin_tone": ["tan"],
            "age": ["20s"],
            "appearance": ["average"],
            "clothing_style": ["rugged"],
            "accessory": ["dirty bandana"],
            "distinguishing_features": ["scar", "freckles"],
        }
    )

    assert attributes.model_dump(exclude_none=True) == {
        "race": "human",
        "faction": "vault_dweller",
        "build": "athletic",
        "skin_tone": "tan",
        "age": 20,
        "appearance": "average",
        "clothing_style": "rugged",
        "accessory": "dirty bandana",
        "distinguishing_features": ["scar", "freckles"],
    }

    singleton = DwellerVisualAttributes.model_validate({"distinguishing_features": ["scar"]})
    assert singleton.distinguishing_features == ["scar"]


def test_backward_compatibility_alias() -> None:
    """DwellerVisualAttributesInput should be an alias of DwellerVisualAttributes."""
    assert DwellerVisualAttributesInput is DwellerVisualAttributes
