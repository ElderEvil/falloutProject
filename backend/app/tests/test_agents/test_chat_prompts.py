"""Prompt-content tests for the dweller chat personality rules."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.agents.chat_prompts import (
    age_voice_line,
    build_chat_instructions,
    dweller_trait_lines,
    family_prompt_line,
    happiness_mood_line,
    identity_line,
)
from app.agents.chat_tools import load_family_members
from app.schemas.common import AgeGroupEnum, GenderEnum, RarityEnum
from app.services.chat.agent_runner import build_dweller_prompt


def _dweller(**overrides: object) -> SimpleNamespace:
    """Smallest object shape both prompt builders read."""
    attrs: dict[str, object] = {
        "first_name": "Nora",
        "last_name": "Kell",
        "level": 22,
        "gender": GenderEnum.FEMALE,
        "age_group": AgeGroupEnum.ADULT,
        "rarity": RarityEnum.COMMON,
        "room": SimpleNamespace(name="Science Lab"),
        "outfit": SimpleNamespace(name="Vault Suit"),
        "weapon": SimpleNamespace(name="10mm Pistol"),
        "health": 50,
        "max_health": 50,
        "radiation": 0,
        "stimpack": 2,
        "radaway": 1,
        "happiness": 62,
        "vault": SimpleNamespace(
            number=101, happiness=70, power=20, power_max=30, food=25, food_max=30, water=18, water_max=30
        ),
        "bio": "Two hundred years and a face that remembers all of them.",
        "visual_attributes": {"race": "ghoul", "state_of_being": "sane"},
        "strength": 4,
        "perception": 5,
        "endurance": 6,
        "charisma": 3,
        "intelligence": 5,
        "agility": 3,
        "luck": 4,
    }
    attrs.update(overrides)
    return SimpleNamespace(**attrs)


def test_identity_line_names_non_human_species_and_state() -> None:
    """Race and state-of-being reach the prompt so a ghoul cannot read as human."""
    line = identity_line(_dweller(visual_attributes={"race": "ghoul", "state_of_being": "wild"}))
    assert "Species: ghoul" in line
    assert "wild" in line
    assert "never claim to be human" in line


@pytest.mark.parametrize("attributes", [{"race": "human"}, None, "not-a-mapping"])
def test_identity_line_is_empty_without_a_non_human_race(attributes: object) -> None:
    assert identity_line(_dweller(visual_attributes=attributes)) == ""


def test_identity_line_ignores_an_unknown_race() -> None:
    assert identity_line(_dweller(visual_attributes={"race": "robot"})) == ""


@pytest.mark.parametrize("state", ["gen_3", None, "unknown"])
def test_identity_line_hides_passing_synths(state: str | None) -> None:
    """Gen 3 synths pass as human and usually do not know what they are: never reveal it."""
    attributes: dict[str, str] = {"race": "synth"}
    if state is not None:
        attributes["state_of_being"] = state
    assert identity_line(_dweller(visual_attributes=attributes)) == ""


@pytest.mark.parametrize("state", ["gen_1", "gen_2"])
def test_identity_line_reveals_visibly_artificial_synth_models(state: str) -> None:
    assert "Species: synth" in identity_line(_dweller(visual_attributes={"race": "synth", "state_of_being": state}))


def test_synth_race_alone_does_not_leak_into_chat_instructions() -> None:
    """A passing synth's prompt reads as an ordinary dweller profile."""
    instructions = build_chat_instructions(_dweller(visual_attributes={"race": "synth", "state_of_being": "gen_3"}))
    assert "synth" not in instructions.lower()


@pytest.mark.parametrize("age_group", [AgeGroupEnum.CHILD, AgeGroupEnum.TEEN, AgeGroupEnum.ELDER])
def test_age_voice_line_covers_every_non_adult_group(age_group: AgeGroupEnum) -> None:
    assert age_voice_line(age_group)


def test_age_voice_line_is_silent_for_adults() -> None:
    """Adults need no register override — they are the baseline voice."""
    assert age_voice_line(AgeGroupEnum.ADULT) == ""


def test_happiness_mood_line_separates_the_bands() -> None:
    """A happiness of 12 must read very differently from 90."""
    assert "deeply unhappy" in happiness_mood_line(12)
    assert "unhappy" in happiness_mood_line(40)
    assert "steady" in happiness_mood_line(60)
    assert "content" in happiness_mood_line(90)
    assert happiness_mood_line(12) != happiness_mood_line(60) != happiness_mood_line(90)


def test_family_prompt_line_lists_names_with_relations() -> None:
    line = family_prompt_line(
        [{"name": "Ana Reyes", "relation": "partner"}, {"name": "Tomas Reyes", "relation": "child"}]
    )
    assert "Ana Reyes (partner)" in line
    assert "Tomas Reyes (child)" in line


@pytest.mark.parametrize("family", [[], [{"name": "", "relation": "partner"}], [{"relation": "partner"}]])
def test_family_prompt_line_is_empty_without_named_members(family: list[dict]) -> None:
    assert family_prompt_line(family) == ""


def test_dweller_trait_lines_combine_identity_age_mood_and_family() -> None:
    lines = dweller_trait_lines(
        _dweller(
            age_group=AgeGroupEnum.ELDER,
            happiness=12,
            visual_attributes={"race": "super_mutant", "state_of_being": "average"},
        ),
        [{"name": "Ana Reyes", "relation": "partner"}],
    )
    assert "Species: super_mutant" in lines
    assert "elder" in lines
    assert "deeply unhappy" in lines
    assert "Ana Reyes (partner)" in lines


def test_chat_instructions_carry_identity_age_mood_and_family() -> None:
    """The structured agent prompt gains every personality axis."""
    instructions = build_chat_instructions(
        _dweller(age_group=AgeGroupEnum.CHILD, happiness=12),
        family=[{"name": "Ana Reyes", "relation": "partner"}],
    )
    assert "Species: ghoul" in instructions
    assert "You are a child" in instructions
    assert "deeply unhappy" in instructions
    assert "Ana Reyes (partner)" in instructions
    assert "irradiated water" in instructions


def test_chat_instructions_default_to_no_family_registered() -> None:
    """Existing callers keep working without a family lookup."""
    assert "Family in the vault" not in build_chat_instructions(_dweller())


def test_fallback_prompt_includes_bio_traits_guardrail_and_length_rule() -> None:
    """The fallback prompt now carries the biography it must not contradict."""
    prompt = build_dweller_prompt(
        _dweller(age_group=AgeGroupEnum.ELDER, happiness=90),
        family=[{"name": "Ana Reyes", "relation": "partner"}],
    )
    assert "Two hundred years and a face that remembers all of them." in prompt
    assert "Species: ghoul" in prompt
    assert "You are an elder" in prompt
    assert "Ana Reyes (partner)" in prompt
    assert "Never contradict or invent biography details" in prompt
    assert "80 and 120 words" in prompt


def test_fallback_prompt_for_audio_keeps_the_audio_length_rule() -> None:
    prompt = build_dweller_prompt(_dweller(), for_audio=True)
    assert "under 150 words" in prompt


@pytest.mark.asyncio
async def test_load_family_members_reports_partner_and_children() -> None:
    """The shared resolver feeds the prompt from partner/parent links in one query."""
    dweller_id, partner_id, child_id = uuid4(), uuid4(), uuid4()
    record = SimpleNamespace(id=dweller_id, partner_id=partner_id, parent_1_id=None, parent_2_id=None)
    partner = SimpleNamespace(id=partner_id, first_name="Ana", last_name="Reyes", parent_1_id=None, parent_2_id=None)
    child = SimpleNamespace(
        id=child_id, first_name="Tomas", last_name="Reyes", parent_1_id=dweller_id, parent_2_id=None
    )
    result = MagicMock()
    result.scalars.return_value.all.return_value = [partner, child]
    session = MagicMock(get=AsyncMock(return_value=record), execute=AsyncMock(return_value=result))

    family = await load_family_members(session, SimpleNamespace(id=dweller_id))

    assert family == [
        {"name": "Ana Reyes", "relation": "partner"},
        {"name": "Tomas Reyes", "relation": "child"},
    ]


@pytest.mark.asyncio
async def test_load_family_members_returns_empty_without_relatives() -> None:
    dweller_id = uuid4()
    record = SimpleNamespace(id=dweller_id, partner_id=None, parent_1_id=None, parent_2_id=None)
    result = MagicMock()
    result.scalars.return_value.all.return_value = []
    session = MagicMock(get=AsyncMock(return_value=record), execute=AsyncMock(return_value=result))

    assert await load_family_members(session, SimpleNamespace(id=dweller_id)) == []


@pytest.mark.asyncio
async def test_load_family_members_returns_empty_for_a_missing_record() -> None:
    """A deleted or vanished dweller must not fail the chat prompt."""
    session = MagicMock(get=AsyncMock(return_value=None))

    assert await load_family_members(session, SimpleNamespace(id=uuid4())) == []
