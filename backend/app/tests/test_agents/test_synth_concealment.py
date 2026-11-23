"""Gen 3 synths must never be revealed — not in dialogue, not in their portrait."""

from types import SimpleNamespace

import pytest

from app.agents.chat_prompts import identity_line
from app.agents.deps import VisualAttributesDeps
from app.agents.dweller_agents import visual_attributes_instructions
from app.core.enums import RaceEnum, SynthTypeEnum
from app.options.races import passes_as_human

SYNTHETIC_MARKERS = ("metallic_silver", "exposed_component", "synthetic_fair")


@pytest.mark.parametrize("state", ["gen_3", None, "unknown"])
def test_passing_synth_models_present_as_human(state: str | None) -> None:
    assert passes_as_human(RaceEnum.SYNTH, state) is True
    assert passes_as_human("synth", state) is True


@pytest.mark.parametrize("state", [SynthTypeEnum.GEN_1.value, SynthTypeEnum.GEN_2.value])
def test_visible_synth_models_do_not_present_as_human(state: str) -> None:
    assert passes_as_human(RaceEnum.SYNTH, state) is False


@pytest.mark.parametrize("race", [RaceEnum.HUMAN, RaceEnum.GHOUL, RaceEnum.SUPER_MUTANT, None])
def test_non_synth_races_never_pass_as_human(race: RaceEnum | None) -> None:
    assert passes_as_human(race, None) is False


def _portrait_instructions(race: str | None) -> str:
    deps = VisualAttributesDeps(first_name="Nora", last_name="Kell", gender=None, bio=None, race=race)
    return visual_attributes_instructions(SimpleNamespace(deps=deps))


@pytest.mark.parametrize("state", ["gen_3", None, "unknown"])
def test_passing_synths_are_presented_to_the_portrait_agent_as_human(state: str | None) -> None:
    # dweller_ai feeds passes_as_human into the portrait race, so this is the branch a passing synth reaches.
    assert passes_as_human("synth", state) is True
    human_branch = _portrait_instructions("human")
    assert "natural skin tones" in human_branch
    for marker in SYNTHETIC_MARKERS:
        assert marker not in human_branch


def test_visible_synth_portrait_keeps_synthetic_options() -> None:
    assert "metallic_silver" in _portrait_instructions("synth")


def test_ghoul_portrait_is_unaffected() -> None:
    assert "radiation-scarred" in _portrait_instructions("ghoul")


def test_gen3_dialogue_identity_stays_hidden() -> None:
    dweller = SimpleNamespace(visual_attributes={"race": "synth", "state_of_being": "gen_3"})
    assert identity_line(dweller) == ""
