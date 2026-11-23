import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pydantic_ai.exceptions import UnexpectedModelBehavior

from app.core.enums import AgeGroupEnum
from app.crud.storage import storage as storage_crud
from app.options.appearance import background_options, body_type_options, haircuts, pose_options, skin_tone_options
from app.options.factions import faction_restrictions
from app.options.presets import archetypes
from app.options.races import RaceOption, race_descriptions
from app.schemas.dweller import DwellerVisualAttributes
from app.services.dweller_ai_service import dweller_ai, restrict_equipment_fields
from app.tests.test_services.test_dweller_ai_helpers import SVC, ai_env, fake_db, make_dweller, make_user
from app.utils.exceptions import AIProviderException


def test_substantial_with_height() -> None:
    assert (
        dweller_ai._has_substantial_visual_attributes({"race": "human", "faction": "vault_dweller", "height": "tall"})
        is True
    )


async def test_avatar_race_change_normalizes_age_and_medical_inventory(async_session, dweller) -> None:
    dweller.age_group = AgeGroupEnum.ELDER
    dweller.radiation = 30
    dweller.radaway = 2
    async_session.add(dweller)
    await async_session.commit()
    with patch.object(dweller_ai, "generate_photo", new=AsyncMock(return_value=dweller)):
        await dweller_ai.generate_dweller_avatar(
            dweller_id=dweller.id,
            dweller_first_name=dweller.first_name,
            dweller_last_name=dweller.last_name,
            visual_attributes_input=DwellerVisualAttributes(race="synth", state_of_being="gen_3"),
            db_session=async_session,
            user=MagicMock(),
        )
    await async_session.refresh(dweller)
    storage = await storage_crud.get_by_vault(async_session, dweller.vault_id)
    assert dweller.age_group == AgeGroupEnum.ADULT
    assert dweller.radiation == 0
    assert dweller.radaway == 0
    assert storage is not None
    assert storage.radaway >= 2


async def test_generate_replaces_substantial_attrs() -> None:
    output = DwellerVisualAttributes(
        race="synth", faction="the_institute", state_of_being="gen_3", height="average", hair_color="red"
    )
    dweller = make_dweller(
        "A test dweller.",
        id=uuid.UUID("00000000-0000-0000-0000-000000000001"),
        visual_attributes={
            "race": "human",
            "faction": "vault_dweller",
            "height": "tall",
            "build": "athletic",
            "voice_line_text": "Stay sharp.",
            "voice_line_url": "https://audio.example/voice.mp3",
        },
    )
    updated = MagicMock()
    updated.visual_attributes = {"height": "average", "hair_color": "red"}
    with ai_env("visual_attributes_agent", output) as d:
        d.crud.get_full_info = AsyncMock(return_value=updated)
        generated = await dweller_ai.generate_visual_attributes(
            user=make_user(), db_session=fake_db(), dweller_info=dweller
        )
    deps = d.agent.run.call_args.kwargs["deps"]
    assert deps.race == "human"
    assert deps.faction == "vault_dweller"
    stored = d.crud.update.call_args.args[2].visual_attributes
    assert stored.race == "human"
    assert stored.faction == "vault_dweller"
    assert stored.height == "average"
    assert stored.hair_color == "red"
    assert stored.build is None
    assert stored.voice_line_text == "Stay sharp."
    assert stored.voice_line_url == "https://audio.example/voice.mp3"
    assert generated is updated


async def test_generate_visual_attributes_maps_invalid_ai_output_to_safe_error() -> None:
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
    with (
        ai_env("visual_attributes_agent", None) as d,
        patch(f"{SVC}.get_instructions", new_callable=AsyncMock) as instructions,
        patch(f"{SVC}.get_provider_model_snapshot", new_callable=AsyncMock) as provider_model,
    ):
        instructions.return_value = ("instructions", uuid.uuid4(), "instructions-hash")
        provider_model.return_value = ("lmstudio", "test-model")
        d.agent.run = AsyncMock(side_effect=UnexpectedModelBehavior("invalid JSON"))
        with pytest.raises(AIProviderException) as exc_info:
            await dweller_ai.generate_visual_attributes(
                user=MagicMock(id=uuid.uuid4()), db_session=fake_db(), dweller_info=dweller
            )
    assert exc_info.value.status_code == 502
    assert exc_info.value.detail == "The AI provider returned an invalid appearance response. Please try again."


def test_restrict_equipment_fields_removes_non_owned() -> None:
    attrs = {"accessory": "Fancy Hat", "object_held": "Laser Rifle", "hair_color": "brown"}
    restrict_equipment_fields(attrs, ["Leather Armor", "Pistol"])
    assert "accessory" not in attrs
    assert "object_held" not in attrs
    assert attrs["hair_color"] == "brown"


def test_race_options() -> None:
    assert len(list(RaceOption)) == 4
    assert RaceOption.HUMAN.value == "human"
    assert RaceOption.GHOUL in race_descriptions


def test_faction_restrictions() -> None:
    assert RaceOption.HUMAN in faction_restrictions
    assert len(faction_restrictions[RaceOption.HUMAN]) > 5  # Humans have many factions
    assert len(faction_restrictions[RaceOption.GHOUL]) < 5  # Ghouls have fewer
    assert len(faction_restrictions[RaceOption.SYNTH]) < 5  # Synths have fewer


def test_appearance_options_per_race() -> None:
    for race in RaceOption:
        assert race in skin_tone_options
        assert race in body_type_options
        assert race in haircuts


def test_presets_exist() -> None:
    assert len(archetypes) >= 5
    assert "Vault Dweller" in archetypes
    assert "Super Mutant Brute" in archetypes


def test_scene_options_are_part_of_the_appearance_catalogue() -> None:
    assert len(pose_options) >= 5
    assert len(background_options) >= 5
