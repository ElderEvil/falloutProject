"""Tests for DwellerAIService visual attribute generation logic."""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException
from pydantic_ai.exceptions import UnexpectedModelBehavior

from app.services.dweller_ai import dweller_ai, restrict_equipment_fields


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


@patch("app.services.dweller_ai.llm_interaction_crud")
@patch("app.services.dweller_ai.visual_attributes_agent")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_replaces_substantial_attrs(
    mock_quota: MagicMock, mock_crud: MagicMock, mock_agent: MagicMock, mock_llm: MagicMock
) -> None:
    """Regeneration replaces existing AI appearance while retaining identity fields."""
    from app.schemas.dweller import DwellerVisualAttributes

    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_crud.update = AsyncMock(return_value=MagicMock())
    mock_llm.create = AsyncMock()

    mock_dweller = MagicMock()
    mock_dweller.visual_attributes = {
        "race": "human",
        "faction": "vault_dweller",
        "height": "tall",
        "build": "athletic",
        "voice_line_text": "Stay sharp.",
        "voice_line_url": "https://audio.example/voice.mp3",
    }
    mock_dweller.first_name = "Test"
    mock_dweller.last_name = "Dweller"
    mock_dweller.gender = "male"
    mock_dweller.bio = "A test dweller."
    mock_dweller.id = uuid.UUID("00000000-0000-0000-0000-000000000001")

    output = DwellerVisualAttributes(height="average", hair_color="red")
    result = MagicMock()
    result.output = output
    result.usage.return_value = MagicMock(input_tokens=100, output_tokens=50, total_tokens=150)
    mock_agent.run = AsyncMock(return_value=result)
    updated_dweller = MagicMock()
    updated_dweller.visual_attributes = {"height": "average", "hair_color": "red"}
    mock_crud.get_full_info = AsyncMock(return_value=updated_dweller)

    user = MagicMock()
    user.id = uuid.uuid4()
    generated = await dweller_ai.generate_visual_attributes(
        user=user, db_session=MagicMock(), dweller_info=mock_dweller
    )

    deps = mock_agent.run.call_args.kwargs["deps"]
    assert deps.race == "human"
    assert deps.faction == "vault_dweller"
    stored = mock_crud.update.call_args.args[2].visual_attributes
    assert stored.race == "human"
    assert stored.faction == "vault_dweller"
    assert stored.height == "average"
    assert stored.hair_color == "red"
    assert stored.build is None
    assert stored.voice_line_text == "Stay sharp."
    assert stored.voice_line_url == "https://audio.example/voice.mp3"
    assert generated is updated_dweller


@patch("app.services.dweller_ai.get_provider_model_snapshot", new_callable=AsyncMock)
@patch("app.services.dweller_ai.get_instructions", new_callable=AsyncMock)
@patch("app.services.dweller_ai.visual_attributes_agent")
@patch("app.services.dweller_ai.dweller_crud")
@patch("app.services.dweller_ai.quota_service")
async def test_generate_visual_attributes_maps_invalid_ai_output_to_safe_error(
    mock_quota: MagicMock,
    mock_crud: MagicMock,
    mock_agent: MagicMock,
    mock_instructions: AsyncMock,
    mock_provider_model: AsyncMock,
) -> None:
    mock_quota.check_quota = AsyncMock(return_value=MagicMock(allowed=True))
    mock_instructions.return_value = ("instructions", uuid.uuid4(), "instructions-hash")
    mock_provider_model.return_value = ("lmstudio", "test-model")
    mock_agent.run = AsyncMock(side_effect=UnexpectedModelBehavior("invalid JSON"))

    dweller = MagicMock(
        id=uuid.uuid4(),
        first_name="Test",
        last_name="Dweller",
        gender="male",
        bio="A test dweller.",
        visual_attributes={"race": "human", "faction": "vault_dweller"},
        weapon=None,
        outfit=None,
    )

    with pytest.raises(HTTPException) as exc_info:
        await dweller_ai.generate_visual_attributes(
            user=MagicMock(id=uuid.uuid4()), db_session=MagicMock(), dweller_info=dweller
        )

    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "The AI provider returned an invalid appearance response. Please try again."


def test_restrict_equipment_fields_removes_non_owned() -> None:
    """accessory/object_held not among equipped items are dropped."""
    attrs = {"accessory": "Fancy Hat", "object_held": "Laser Rifle", "hair_color": "brown"}
    restrict_equipment_fields(attrs, ["Leather Armor", "Pistol"])
    assert "accessory" not in attrs
    assert "object_held" not in attrs
    assert attrs["hair_color"] == "brown"


def test_restrict_equipment_fields_keeps_owned() -> None:
    """accessory/object_held matching an equipped item are preserved."""
    attrs = {"accessory": "Leather Armor", "object_held": "Pistol"}
    restrict_equipment_fields(attrs, ["Leather Armor", "Pistol"])
    assert attrs["accessory"] == "Leather Armor"
    assert attrs["object_held"] == "Pistol"


def test_restrict_equipment_fields_keeps_one_owned_one_stripped() -> None:
    """Only the field matching an owned item survives."""
    attrs = {"accessory": "Pistol", "object_held": "Nuka-Cola Bottle"}
    restrict_equipment_fields(attrs, ["Pistol"])
    assert attrs["accessory"] == "Pistol"
    assert "object_held" not in attrs


def test_restrict_equipment_fields_empty_equipment_removes_all() -> None:
    """With no equipped items, both equipment fields are removed."""
    attrs = {"accessory": "Sunglasses", "object_held": "Crowbar"}
    restrict_equipment_fields(attrs, [])
    assert "accessory" not in attrs
    assert "object_held" not in attrs


def test_restrict_equipment_fields_noop_when_fields_absent() -> None:
    """Missing equipment fields cause no changes to unrelated attributes."""
    attrs = {"height": "tall", "hair_color": "brown"}
    restrict_equipment_fields(attrs, ["Leather Armor"])
    assert attrs == {"height": "tall", "hair_color": "brown"}


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
