"""Tests for the unified DwellerVisualAttributes schema."""

import pytest
from pydantic import ValidationError

from app.schemas.dweller import DwellerVisualAttributes, DwellerVisualAttributesInput
from app.services.dweller_service import dweller_service


@pytest.fixture(autouse=True)
def _faction_mechanics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """These cover the on-state, so the dark-by-default switch is stated."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.features, "faction_mechanics", True)


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


def test_appearance_options_match_the_canonical_module() -> None:
    """The editor catalogue is served from app/options/appearance.py, not mirrored."""
    from app.options.appearance import (
        background_options,
        body_type_options,
        expression_options,
        eye_color_options,
        hair_color_options,
        haircuts,
        headgear_options,
        height_options,
        pose_options,
        skin_tone_options,
    )
    from app.options.races import RaceOption

    options = dweller_service.get_appearance_options()

    assert set(options.skin_tones_by_race) == {race.value for race in RaceOption}
    assert options.skin_tones_by_race["human"] == skin_tone_options[RaceOption.HUMAN]
    assert options.builds_by_race["ghoul"] == body_type_options[RaceOption.GHOUL]
    assert options.haircuts_by_race["synth"] == haircuts[RaceOption.SYNTH]
    assert options.headgear_by_race["super_mutant"] == headgear_options[RaceOption.SUPER_MUTANT]
    assert options.expressions == list(expression_options)
    assert options.poses == pose_options
    assert options.backgrounds == background_options
    assert options.heights == height_options
    assert options.eye_colors == eye_color_options
    assert options.hair_colors == hair_color_options


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


def test_none_faction_accepted_while_switch_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """System-assigned 'none' still passes while the switch is off."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.features, "faction_mechanics", False)
    attributes = DwellerVisualAttributes.model_validate({"race": "ghoul", "faction": "none"})

    assert attributes.faction == "none"


def test_identity_options_empty_factions_while_switch_off(monkeypatch: pytest.MonkeyPatch) -> None:
    """Clients are offered no factions while the switch is off — races still are."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.features, "faction_mechanics", False)
    options = dweller_service.get_identity_options()

    assert options.races == ["human", "ghoul", "super_mutant", "synth"]
    assert options.factions_by_race == {}
