import pytest
from pydantic import ValidationError

from app.core.game_config import game_config
from app.options import appearance as ap
from app.options.races import RaceOption
from app.schemas.dweller import DwellerVisualAttributes, DwellerVisualAttributesInput
from app.services.dweller_service import dweller_service

_RAW_FIELDS = (
    "race faction height appearance clothing_style distinguishing_features build hair_style skin_tone eye_color "
    "hair_color facial_hair makeup headgear expression accessory object_held pose background voice_line_text "
    "voice_line_url age state_of_being"
)
ALL_FIELDS = _RAW_FIELDS.split()


@pytest.fixture(autouse=True)
def _faction_mechanics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # These cover the on-state, so the dark-by-default switch is stated.
    monkeypatch.setattr(game_config.features, "faction_mechanics", True)


def test_unified_schema_has_all_fields() -> None:
    fields = DwellerVisualAttributes.model_fields
    for name in ALL_FIELDS:
        assert name in fields
    assert len(fields) == 23
    assert "haircut" not in fields, "haircut should be renamed to hair_style"
    assert "body_type" not in fields, "body_type should be renamed to build"
    assert DwellerVisualAttributesInput is DwellerVisualAttributes


def test_identity_options_match_the_canonical_faction_restrictions() -> None:
    options = dweller_service.get_identity_options()
    assert (options.races, options.factions_by_race["synth"]) == (
        ["human", "ghoul", "super_mutant", "synth"],
        ["the_institute", "railroad", "none"],
    )
    assert (options.states_by_race["ghoul"], options.states_by_race["super_mutant"]) == (
        ["sane", "wild", "feral"],
        ["mild", "average", "behemoth"],
    )


def test_appearance_options_match_the_canonical_module() -> None:
    options = dweller_service.get_appearance_options()
    assert (set(options.skin_tones_by_race), options.skin_tones_by_race["human"]) == (
        {race.value for race in RaceOption},
        ap.skin_tone_options[RaceOption.HUMAN],
    )
    assert (options.builds_by_race["ghoul"], options.haircuts_by_race["synth"]) == (
        ap.body_type_options[RaceOption.GHOUL],
        ap.haircuts[RaceOption.SYNTH],
    )
    assert (options.headgear_by_race["super_mutant"], options.expressions) == (
        ap.headgear_options[RaceOption.SUPER_MUTANT],
        list(ap.expression_options),
    )
    assert ((options.poses, options.backgrounds), (options.heights, options.eye_colors)) == (
        (ap.pose_options, ap.background_options),
        (ap.height_options, ap.eye_color_options),
    )
    assert options.hair_colors == ap.hair_color_options


def test_normalizes_single_item_provider_lists_for_scalar_attributes() -> None:
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
    assert DwellerVisualAttributes.model_validate({"distinguishing_features": ["scar"]}).distinguishing_features == [
        "scar"
    ]


def test_none_faction_accepted_while_switch_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(game_config.features, "faction_mechanics", False)
    assert DwellerVisualAttributes.model_validate({"race": "ghoul", "faction": "none"}).faction == "none"


def test_identity_options_empty_factions_while_switch_off(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(game_config.features, "faction_mechanics", False)
    options = dweller_service.get_identity_options()
    assert (options.races, options.factions_by_race) == (["human", "ghoul", "super_mutant", "synth"], {})
