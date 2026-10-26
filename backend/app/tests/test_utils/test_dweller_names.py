"""Tests for race-aware dweller name generation."""

import random
import re

import pytest
from faker import Faker

from app.core.enums import GenderEnum, SynthTypeEnum
from app.options.dweller_names import SUPER_MUTANT_EPITHETS, SUPER_MUTANT_NAMES
from app.options.races import RaceOption
from app.utils.dwellers import (
    create_random_common_dweller,
    get_race_based_name,
    get_super_mutant_name,
    get_synth_designation,
)

DESIGNATION = re.compile(r"^[A-Z]\d-\d{2}$")
EPITHETS = {epithet.removeprefix("the ") for epithet in SUPER_MUTANT_EPITHETS}


def test_mild_super_mutants_use_the_articulate_pool() -> None:
    rng = random.Random(1)
    for _ in range(100):
        assert get_super_mutant_name("mild", rng) in SUPER_MUTANT_NAMES["mild"]


def test_average_and_behemoth_super_mutants_mix_names_and_epithets() -> None:
    rng = random.Random(2)
    names = [get_super_mutant_name("average", rng) for _ in range(200)]

    assert any(" the " in name for name in names)
    assert any(name in SUPER_MUTANT_NAMES["average"] for name in names)
    for name in names:
        base, _, epithet = name.partition(" the ")
        assert base in SUPER_MUTANT_NAMES["average"]
        if epithet:
            assert epithet in EPITHETS


def test_synth_designation_shape_is_stable() -> None:
    rng = random.Random(3)
    for _ in range(100):
        assert DESIGNATION.fullmatch(get_synth_designation(rng))


def test_visible_synths_mix_designations_and_cover_names() -> None:
    rng = random.Random(4)
    faker = Faker()
    faker.seed_instance(4)
    results = [
        get_race_based_name(RaceOption.SYNTH, SynthTypeEnum.GEN_2.value, GenderEnum.FEMALE, faker, rng)
        for _ in range(200)
    ]

    assert any(DESIGNATION.fullmatch(first) and last is None for first, last in results)
    assert any(last is not None for _, last in results)


def test_gen_one_synths_only_get_designations() -> None:
    rng = random.Random(5)
    faker = Faker()
    faker.seed_instance(5)
    for _ in range(20):
        first, last = get_race_based_name(RaceOption.SYNTH, SynthTypeEnum.GEN_1.value, GenderEnum.MALE, faker, rng)
        assert DESIGNATION.fullmatch(first)
        assert last is None


@pytest.mark.parametrize("race", [RaceOption.HUMAN, RaceOption.GHOUL, RaceOption.SYNTH])
def test_human_passing_races_keep_faker_names(race: RaceOption) -> None:
    rng = random.Random(6)
    faker = Faker()
    faker.seed_instance(6)
    state = SynthTypeEnum.GEN_3.value if race == RaceOption.SYNTH else None

    first, last = get_race_based_name(race, state, GenderEnum.MALE, faker, rng)

    assert first
    assert last
    assert not DESIGNATION.fullmatch(first)


def test_random_dweller_uses_super_mutant_names(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.utils.dwellers._roll_identity",
        lambda _rng: {"race": "super_mutant", "faction": "super_mutant_tribe", "state_of_being": "average"},
    )

    dweller = create_random_common_dweller(seed=11)

    assert dweller["last_name"] is None
    assert dweller["first_name"].split(" the ")[0] in SUPER_MUTANT_NAMES["average"]


def test_random_dweller_uses_synth_designations(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.utils.dwellers._roll_identity",
        lambda _rng: {"race": "synth", "faction": "the_institute", "state_of_being": "gen_1"},
    )

    dweller = create_random_common_dweller(seed=12)

    assert DESIGNATION.fullmatch(dweller["first_name"])
    assert dweller["last_name"] is None


def test_random_human_dweller_keeps_a_last_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.utils.dwellers._roll_identity",
        lambda _rng: {"race": "human", "faction": "vault_dweller"},
    )

    dweller = create_random_common_dweller(seed=13)

    assert dweller["first_name"]
    assert dweller["last_name"]
