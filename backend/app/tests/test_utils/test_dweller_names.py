import random
import re

import pytest
from faker import Faker

from app.core.enums import GenderEnum, SynthTypeEnum
from app.options.dweller_names import SUPER_MUTANT_EPITHETS, SUPER_MUTANT_NAMES
from app.options.races import RaceOption
from app.utils.dweller_generation import create_random_common_dweller
from app.utils.dwellers import get_race_based_name, get_super_mutant_name, get_synth_designation

DESIGNATION = re.compile(r"^[A-Z]\d-\d{2}$")
EPITHETS = {epithet.removeprefix("the ") for epithet in SUPER_MUTANT_EPITHETS}


def _faker(seed: int) -> Faker:
    faker = Faker()
    faker.seed_instance(seed)
    return faker


def test_super_mutant_name_pools() -> None:
    rng = random.Random(1)
    for _ in range(100):
        assert get_super_mutant_name("mild", rng) in SUPER_MUTANT_NAMES["mild"]

    rng = random.Random(2)
    names = [get_super_mutant_name("average", rng) for _ in range(200)]
    assert any(" the " in name for name in names)
    assert any(name in SUPER_MUTANT_NAMES["average"] for name in names)
    for name in names:
        base, _, epithet = name.partition(" the ")
        assert base in SUPER_MUTANT_NAMES["average"]
        if epithet:
            assert epithet in EPITHETS


def test_synth_name_shapes() -> None:
    rng = random.Random(3)
    for _ in range(100):
        assert DESIGNATION.fullmatch(get_synth_designation(rng))
    gen1_rng, faker = random.Random(5), _faker(5)
    for _ in range(20):
        first, last = get_race_based_name(RaceOption.SYNTH, SynthTypeEnum.GEN_1.value, GenderEnum.MALE, faker, gen1_rng)
        assert DESIGNATION.fullmatch(first)
        assert last is None
    visible_rng, faker = random.Random(4), _faker(4)
    results = [
        get_race_based_name(RaceOption.SYNTH, SynthTypeEnum.GEN_2.value, GenderEnum.FEMALE, faker, visible_rng)
        for _ in range(200)
    ]
    assert any(DESIGNATION.fullmatch(first) and last is None for first, last in results)
    assert any(last is not None for _, last in results)


def test_human_passing_races_keep_faker_names() -> None:
    for race in (RaceOption.HUMAN, RaceOption.GHOUL, RaceOption.SYNTH):
        state = SynthTypeEnum.GEN_3.value if race == RaceOption.SYNTH else None
        first, last = get_race_based_name(race, state, GenderEnum.MALE, _faker(6), random.Random(6))
        assert first
        assert last
        assert not DESIGNATION.fullmatch(first)


@pytest.mark.parametrize(
    ("identity", "check", "seed"),
    [
        ({"race": "super_mutant", "faction": "super_mutant_tribe", "state_of_being": "average"}, "mutant", 11),
        ({"race": "synth", "faction": "the_institute", "state_of_being": "gen_1"}, "synth", 12),
        ({"race": "human", "faction": "vault_dweller"}, "human", 13),
    ],
)
def test_random_dweller_uses_race_appropriate_names(
    monkeypatch: pytest.MonkeyPatch, identity: dict, check: str, seed: int
) -> None:
    monkeypatch.setattr("app.utils.dweller_generation._roll_identity", lambda _rng: identity)
    dweller = create_random_common_dweller(seed=seed)
    assert dweller["first_name"]
    if check == "mutant":
        assert dweller["last_name"] is None
        assert dweller["first_name"].split(" the ")[0] in SUPER_MUTANT_NAMES["average"]
    elif check == "synth":
        assert DESIGNATION.fullmatch(dweller["first_name"])
        assert dweller["last_name"] is None
    else:
        assert dweller["last_name"]
