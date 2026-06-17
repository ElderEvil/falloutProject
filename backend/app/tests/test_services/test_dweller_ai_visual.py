"""Tests for DwellerAIService visual attribute generation logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.dweller_ai import dweller_ai

# --- _has_substantial_visual_attributes ---


def test_substantial_none() -> None:
    """None should be considered not substantial."""
    assert dweller_ai._has_substantial_visual_attributes(None) is False


def test_substantial_empty_dict() -> None:
    """Empty dict should be considered not substantial."""
    assert dweller_ai._has_substantial_visual_attributes({}) is False


def test_substantial_only_identity() -> None:
    """Only race+faction (defaults) should be considered not substantial."""
    assert dweller_ai._has_substantial_visual_attributes({"race": "human", "faction": "vault_dweller"}) is False


def test_substantial_identity_and_state() -> None:
    """Identity + state_of_being should still be not substantial."""
    assert (
        dweller_ai._has_substantial_visual_attributes({"race": "ghoul", "faction": "none", "state_of_being": "sane"})
        is False
    )


def test_substantial_identity_and_age() -> None:
    """Identity + age should still be not substantial."""
    assert (
        dweller_ai._has_substantial_visual_attributes({"race": "human", "faction": "vault_dweller", "age": 30}) is False
    )


def test_substantial_with_height() -> None:
    """A physical attribute like height should make it substantial."""
    assert (
        dweller_ai._has_substantial_visual_attributes({"race": "human", "faction": "vault_dweller", "height": "tall"})
        is True
    )


def test_substantial_with_hair_color() -> None:
    """Hair color alone should make it substantial."""
    assert dweller_ai._has_substantial_visual_attributes({"race": "human", "hair_color": "brown"}) is True


def test_substantial_full_ai_data() -> None:
    """Full AI-generated data should be substantial."""
    assert (
        dweller_ai._has_substantial_visual_attributes(
            {
                "race": "human",
                "faction": "vault_dweller",
                "height": "tall",
                "build": "athletic",
                "skin_tone": "tan",
                "eye_color": "brown",
                "hair_style": "short",
                "hair_color": "brown",
                "clothing_style": "casual",
            }
        )
        is True
    )


# --- generate_visual_attributes ---


@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.dweller_crud")
async def test_generate_raises_if_substantial_attrs_exist(mock_crud: MagicMock, mock_quota: MagicMock) -> None:
    """Should raise ContentNoChangeException if dweller already has substantial VA."""
    from app.utils.exceptions import ContentNoChangeException

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_crud.update = AsyncMock(return_value=MagicMock())

    mock_dweller = MagicMock()
    mock_dweller.visual_attributes = {
        "race": "human",
        "faction": "vault_dweller",
        "height": "tall",
        "build": "athletic",
    }
    mock_dweller.first_name = "Test"
    mock_dweller.last_name = "Dweller"
    mock_dweller.gender = "male"
    mock_dweller.bio = "A test dweller."
    mock_dweller.id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    with pytest.raises(ContentNoChangeException, match="already has visual attributes"):
        await dweller_ai.generate_visual_attributes(user=MagicMock(), db_session=MagicMock(), dweller_info=mock_dweller)


@patch("app.services.dweller_ai.quota_service")
@patch("app.services.dweller_ai.dweller_crud")  # Mock crud to avoid DB
@patch("app.services.dweller_ai.visual_attributes_agent")
@patch("app.services.dweller_ai.llm_interaction_crud")
async def test_generate_allows_with_only_defaults(
    mock_llm: MagicMock, mock_agent: MagicMock, mock_crud: MagicMock, mock_quota: MagicMock
) -> None:
    """Should allow generation when dweller only has identity defaults."""
    import app.schemas.dweller as dweller_schemas

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_crud.update = AsyncMock(return_value=MagicMock())
    mock_llm.create = AsyncMock(return_value=MagicMock())

    mock_dweller = MagicMock()
    mock_dweller.visual_attributes = {"race": "human", "faction": "vault_dweller"}
    mock_dweller.first_name = "Test"
    mock_dweller.last_name = "Dweller"
    mock_dweller.gender = "male"
    mock_dweller.bio = None
    mock_dweller.id = uuid.UUID("00000000-0000-0000-0000-000000000002")

    mock_user = MagicMock()
    mock_user.id = uuid.UUID("00000000-0000-0000-0000-000000000099")

    # Mock agent to return a full set of attributes
    mock_output = dweller_schemas.DwellerVisualAttributes(
        height="average",
        build="athletic",
        skin_tone="fair",
        eye_color="blue",
        hair_color="brown",
        hair_style="short",
    )
    mock_result = MagicMock()
    mock_result.output = mock_output
    mock_result.usage.return_value = MagicMock(input_tokens=100, output_tokens=50, total_tokens=150)
    mock_agent.run = AsyncMock(return_value=mock_result)

    # Should not raise
    result = await dweller_ai.generate_visual_attributes(
        user=mock_user, db_session=MagicMock(), dweller_info=mock_dweller
    )

    # Verify the agent was called with deps containing race/faction
    call_args = mock_agent.run.call_args
    assert call_args is not None
    deps = call_args[1]["deps"]
    assert deps.race == "human"
    assert deps.faction == "vault_dweller"

    # Verify result is returned
    assert result is not None


# --- Options module ---


def test_race_options() -> None:
    """Race options should be importable with correct values."""
    from app.options.races import RaceOption, race_descriptions

    assert len(list(RaceOption)) == 4
    assert RaceOption.HUMAN.value == "human"
    assert RaceOption.GHOUL in race_descriptions


def test_faction_restrictions() -> None:
    """Faction restrictions should map correctly per race."""
    from app.options.factions import faction_restrictions
    from app.options.races import RaceOption

    assert RaceOption.HUMAN in faction_restrictions
    assert len(faction_restrictions[RaceOption.HUMAN]) > 5  # Humans have many factions
    assert len(faction_restrictions[RaceOption.GHOUL]) < 5  # Ghouls have fewer
    assert len(faction_restrictions[RaceOption.SYNTH]) < 5  # Synths have fewer


def test_appearance_options_per_race() -> None:
    """Appearance options should be organized by race."""
    from app.options.appearance import body_type_options, haircuts, skin_tone_options
    from app.options.races import RaceOption

    for race in RaceOption:
        assert race in skin_tone_options
        assert race in body_type_options
        assert race in haircuts


def test_presets_exist() -> None:
    """Archetype presets should be importable with core archetypes."""
    from app.options.presets import archetypes

    assert len(archetypes) >= 5
    assert "Vault Dweller" in archetypes
    assert "Super Mutant Brute" in archetypes


def test_scenes_import() -> None:
    """Scene options should be importable."""
    from app.options.scenes import background_options, pose_options

    assert len(pose_options) >= 5
    assert len(background_options) >= 5
