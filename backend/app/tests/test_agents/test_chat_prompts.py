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
    state_mind_line,
)
from app.agents.chat_tools import load_family_members
from app.core.enums import AgeGroupEnum, GenderEnum, RarityEnum
from app.services.chat.agent_runner import build_dweller_prompt

BASE = {
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


def _dweller(**overrides: object) -> SimpleNamespace:
    return SimpleNamespace(**(BASE | overrides))


def test_identity_line_names_non_human_species_and_state() -> None:
    line = identity_line(_dweller(visual_attributes={"race": "ghoul", "state_of_being": "wild"}))
    assert "Species: ghoul" in line
    assert "wild" in line
    assert "never claim to be human" in line


@pytest.mark.parametrize("attributes", [{"race": "human"}, None, "not-a-mapping", {"race": "robot"}])
def test_identity_line_is_empty_without_a_known_non_human_race(attributes: object) -> None:
    assert identity_line(_dweller(visual_attributes=attributes)) == ""


@pytest.mark.parametrize(
    ("state", "expected"),
    [("gen_3", None), (None, None), ("unknown", None), ("gen_1", "Species: synth"), ("gen_2", "Species: synth")],
)
def test_identity_line_synth_visibility(state: str | None, expected: str | None) -> None:
    attributes: dict[str, str] = {"race": "synth"}
    if state is not None:
        attributes["state_of_being"] = state
    line = identity_line(_dweller(visual_attributes=attributes))
    assert (line == "") if expected is None else (expected in line)


def test_synth_race_alone_does_not_leak_into_chat_instructions() -> None:
    instructions = build_chat_instructions(_dweller(visual_attributes={"race": "synth", "state_of_being": "gen_3"}))
    assert "synth" not in instructions.lower()


@pytest.mark.parametrize(
    ("attributes", "expected"),
    [
        ({"race": "ghoul", "state_of_being": "feral"}, ["growl", "no_action"]),
        ({"race": "ghoul", "state_of_being": "wild"}, ["fragment"]),
    ],
)
def test_state_mind_line_marks_degraded_ghouls(attributes: dict, expected: list[str]) -> None:
    line = state_mind_line(_dweller(visual_attributes=attributes))
    for phrase in expected:
        assert phrase in line


def test_state_mind_line_grades_mutant_and_synth_models() -> None:
    behemoth = state_mind_line(_dweller(visual_attributes={"race": "super_mutant", "state_of_being": "behemoth"}))
    assert "no_action" in behemoth
    mild = state_mind_line(_dweller(visual_attributes={"race": "super_mutant", "state_of_being": "mild"}))
    assert "no_action" not in mild
    gen_1 = state_mind_line(_dweller(visual_attributes={"race": "synth", "state_of_being": "gen_1"}))
    assert "literal" in gen_1


def test_state_mind_line_hides_passing_synths() -> None:
    assert (
        state_mind_line(_dweller(visual_attributes={"race": "synth", "state_of_being": "gen_3"})),
        state_mind_line(_dweller(visual_attributes={"race": "human"})),
    ) == ("", "")


def test_dweller_trait_lines_carry_the_state_of_being_mind() -> None:
    lines = dweller_trait_lines(_dweller(visual_attributes={"race": "ghoul", "state_of_being": "feral"}))
    assert "Species: ghoul" in lines
    assert "growl" in lines


@pytest.mark.parametrize(
    ("age_group", "silent"),
    [(AgeGroupEnum.CHILD, False), (AgeGroupEnum.TEEN, False), (AgeGroupEnum.ELDER, False), (AgeGroupEnum.ADULT, True)],
)
def test_age_voice_line_covers_every_non_adult_group(age_group: AgeGroupEnum, silent: bool) -> None:
    assert (age_voice_line(age_group) == "") is silent


def test_happiness_mood_line_separates_the_bands() -> None:
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
    assert "Family in the vault" not in build_chat_instructions(_dweller())


def test_fallback_prompt_includes_bio_traits_guardrail_and_length_rule() -> None:
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
    assert "under 150 words" in build_dweller_prompt(_dweller(), for_audio=True)


def _family_session(relatives: list, record: SimpleNamespace | None):
    result = MagicMock()
    result.scalars.return_value.all.return_value = relatives
    return MagicMock(get=AsyncMock(return_value=record), execute=AsyncMock(return_value=result))


async def test_load_family_members_reports_partner_and_children() -> None:
    dweller_id, partner_id, child_id = uuid4(), uuid4(), uuid4()
    record = SimpleNamespace(id=dweller_id, partner_id=partner_id, parent_1_id=None, parent_2_id=None)
    partner = SimpleNamespace(id=partner_id, first_name="Ana", last_name="Reyes", parent_1_id=None, parent_2_id=None)
    child = SimpleNamespace(
        id=child_id, first_name="Tomas", last_name="Reyes", parent_1_id=dweller_id, parent_2_id=None
    )
    family = await load_family_members(_family_session([partner, child], record), SimpleNamespace(id=dweller_id))
    assert family == [
        {"name": "Ana Reyes", "relation": "partner"},
        {"name": "Tomas Reyes", "relation": "child"},
    ]


@pytest.mark.parametrize("kind", ["no_relatives", "missing_record"])
async def test_load_family_members_returns_empty_without_relatives(kind: str) -> None:
    dweller_id = uuid4()
    if kind == "no_relatives":
        record = SimpleNamespace(id=dweller_id, partner_id=None, parent_1_id=None, parent_2_id=None)
        session = _family_session([], record)
    else:
        session = MagicMock(get=AsyncMock(return_value=None))
    assert await load_family_members(session, SimpleNamespace(id=dweller_id)) == []
