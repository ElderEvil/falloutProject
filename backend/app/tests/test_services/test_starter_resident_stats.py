"""Curated starter residents must carry plausible, budget-balanced SPECIAL stats.

The guided objective arc hands out nine named residents. Before this data was
curated they arrived with one random value copied into all seven SPECIAL fields
(all 1s, all 2s or all 3s), so a "scavenger who reads ruins" and a "builder who
learned from collapse patterns" were indistinguishable. These tests keep the
numbers honest: every profile complete, in range, and on the same 21-point budget
as the best legacy roll (all 3s).
"""

import json

import pytest

from app.core.enums import GenderEnum
from app.services.rewards.starter_residents import get_starter_resident, starter_residents, starter_reward_overrides
from app.utils.static_data import DATA_DIR

SPECIAL_KEYS = ("strength", "perception", "endurance", "charisma", "intelligence", "agility", "luck")
STAT_BUDGET = 21


def _profiles() -> dict[str, dict]:
    return starter_residents()


def test_every_profile_defines_a_complete_special_block() -> None:
    for name, profile in _profiles().items():
        missing = [key for key in SPECIAL_KEYS if key not in profile]
        assert not missing, f"{name} is missing {missing}"


def test_every_stat_is_within_the_common_range() -> None:
    for name, profile in _profiles().items():
        for key in SPECIAL_KEYS:
            value = profile[key]
            # type(...) is int (not isinstance) so a JSON true can't masquerade as 1.
            assert type(value) is int, f"{name}.{key} is not an int: {value!r}"
            assert 1 <= value <= 10, f"{name}.{key} out of range: {value}"


def test_profiles_share_one_stat_budget() -> None:
    for name, profile in _profiles().items():
        total = sum(profile[key] for key in SPECIAL_KEYS)
        assert total == STAT_BUDGET, f"{name} totals {total}, expected {STAT_BUDGET}"


def test_no_profile_is_a_flat_block() -> None:
    """A flat profile is the bug this data change fixed — never reintroduce it."""
    for name, profile in _profiles().items():
        distinct = {profile[key] for key in SPECIAL_KEYS}
        assert len(distinct) >= 3, f"{name} has only {sorted(distinct)} — that is a flat clone"


def test_every_dweller_reward_names_a_curated_resident() -> None:
    objectives = json.loads((DATA_DIR / "objectives/starter.json").read_text(encoding="utf-8"))
    steps = objectives if isinstance(objectives, list) else next(iter(objectives.values()))
    known = _profiles()

    granted = []
    for step in steps:
        reward = step.get("reward")
        if isinstance(reward, str) and reward.startswith("dweller:"):
            granted.append(reward.split(":", 1)[1].strip())

    assert granted, "starter arc unexpectedly grants no dwellers"
    unknown = [name for name in granted if name.strip().lower() not in known]
    assert not unknown, f"objective rewards reference uncurated residents: {unknown}"


@pytest.mark.parametrize("name", sorted(_profiles()))
def test_named_resident_has_a_standout_stat(name: str) -> None:
    """Every resident is good at something; a 5 marks the character's edge."""
    profile = _profiles()[name]
    assert max(profile[key] for key in SPECIAL_KEYS) >= 5, f"{name} has no standout stat"


@pytest.mark.parametrize("majority", [GenderEnum.MALE, GenderEnum.FEMALE])
def test_starter_variants_keep_each_rewards_special_profile(majority: GenderEnum) -> None:
    replacements = starter_reward_overrides(majority)
    assert len(set(replacements.values())) == len(replacements)
    for original_reward, variant_reward in replacements.items():
        original = get_starter_resident(original_reward.removeprefix("dweller:"))
        variant = get_starter_resident(variant_reward.removeprefix("dweller:"))
        assert original is not None
        assert variant is not None
        assert len(variant_reward) <= 32  # reward_snapshot column
        assert original["gender"] != variant["gender"]
        assert variant["gender"] == majority
        assert tuple(variant[key] for key in SPECIAL_KEYS) == tuple(original[key] for key in SPECIAL_KEYS)
