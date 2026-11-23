from types import SimpleNamespace

import pytest

from app.core.enums import DamageChannel
from app.core.game_config import game_config
from app.models.pet import Pet
from app.options.pet_modifiers import MAX_RESIST_PCT, PET_EFFECT_BY_NAME, PetEffect
from app.utils.damage_reductions import DamageReductions, damage_reductions


@pytest.fixture(autouse=True)
def _identity_mechanics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    # Faction perks ship dark, so source-selection tests state both switches as a precondition.
    monkeypatch.setattr(game_config.features, "race_mechanics", True)
    monkeypatch.setattr(game_config.features, "faction_mechanics", True)


def _dweller(race: str | None = None, faction: str | None = None, outfit=None) -> SimpleNamespace:
    attrs = {key: value for key, value in (("race", race), ("faction", faction)) if value is not None}
    dweller = SimpleNamespace(visual_attributes=attrs)
    dweller.outfit = outfit
    return dweller


def _outfit(**fields) -> SimpleNamespace:
    return SimpleNamespace(**fields)


def _pet(name: str) -> Pet:
    return Pet(name=name, rarity="Legendary")


POWER_ARMOR = {"outfit_type": "power_armor", "name": "T-51d power armor"}
SOURCE_CASES = [
    (
        {"faction": "minutemen", "outfit": _outfit(fire_resist=0.5, radiation_resist=1.0)},
        None,
        DamageChannel.PHYSICAL,
        (0.15,),
    ),
    ({"faction": "minutemen", "outfit": _outfit(fire_resist=0.5)}, None, DamageChannel.FIRE, (0.15, 0.5)),
    ({"outfit": _outfit(radiation_resist=1.0)}, None, DamageChannel.FIRE, ()),
    (
        {"race": "human", "faction": "children_of_atom", "outfit": _outfit(**POWER_ARMOR)},
        None,
        DamageChannel.RADIATION,
        (0.5, 0.75),
    ),
    ({"outfit": _outfit(fire_resist=0.5)}, None, DamageChannel.RADIATION, ()),
    ({"faction": "minutemen"}, "pallas's cat", DamageChannel.PHYSICAL, (0.15, 0.25)),
    (
        {"faction": "minutemen", "outfit": _outfit(fire_resist=0.5)},
        "pallas's cat",
        DamageChannel.FIRE,
        (0.15, 0.25, 0.5),
    ),
    ({"race": "human", "faction": "children_of_atom"}, "st. bernard", DamageChannel.RADIATION, (0.5, 0.25)),
    ({}, "pallas's cat", DamageChannel.RADIATION, ()),
    ({}, "st. bernard", DamageChannel.PHYSICAL, ()),
]


@pytest.mark.parametrize(("dweller_kwargs", "pet", "channel", "expected"), SOURCE_CASES)
def test_channel_source_selection(
    dweller_kwargs: dict, pet: str | None, channel: DamageChannel, expected: tuple
) -> None:
    dweller = _dweller(**dweller_kwargs)
    if pet:
        dweller.pet = _pet(pet)
    reductions = damage_reductions(dweller, channel)
    assert reductions.shares == expected
    assert reductions.immune is False


def test_team_share_and_plain_dweller() -> None:
    for channel in DamageChannel:
        assert damage_reductions(_dweller(), channel, team_share=0.2).shares == (0.2,)
    for channel in DamageChannel:
        reductions = damage_reductions(_dweller(), channel)
        assert reductions.shares == ()
        assert reductions.immune is False


def test_combined_share_math(monkeypatch) -> None:
    assert DamageReductions(shares=(0.15, 0.2)).combined_share == pytest.approx(1 - 0.85 * 0.8)
    a = DamageReductions(shares=(0.15, 0.2, 0.5))
    b = DamageReductions(shares=(0.5, 0.15, 0.2))
    c = DamageReductions(shares=(0.2, 0.5, 0.15))
    assert a.combined_share == b.combined_share == c.combined_share
    assert DamageReductions(shares=(0.9, 0.9)).combined_share == pytest.approx(MAX_RESIST_PCT)
    monkeypatch.setitem(PET_EFFECT_BY_NAME, "cap test pet", PetEffect(radiation_resist_pct=0.95))
    human = _dweller(race="human", faction="children_of_atom")
    human.pet = _pet("cap test pet")
    # 1 - 0.5 * 0.05 = 0.975, capped at 0.95
    assert damage_reductions(human, DamageChannel.RADIATION).combined_share == pytest.approx(MAX_RESIST_PCT)
    for shares, amount, expected in [((0.15,), 20, 17), ((), 10, 10), ((0.15, 0.2), 3, 2)]:
        assert DamageReductions(shares=shares).apply(amount) == expected


def test_immunity_rules() -> None:
    for race, state in [("ghoul", None), ("super_mutant", None), ("synth", "gen_1"), ("synth", "gen_2")]:
        dweller = _dweller(race=race)
        if state is not None:
            dweller.visual_attributes["state_of_being"] = state
        reductions = damage_reductions(dweller, DamageChannel.RADIATION)
        assert reductions.immune is True
        assert reductions.apply(100) == 0
    dweller = _dweller(race="synth")
    dweller.visual_attributes["state_of_being"] = "gen_3"
    reductions = damage_reductions(dweller, DamageChannel.RADIATION)
    assert reductions.immune is False
    assert reductions.apply(100) == 100
    physical = damage_reductions(_dweller(race="ghoul"), DamageChannel.PHYSICAL)
    assert physical.immune is False
    assert physical.apply(100) == 100


@pytest.mark.parametrize(("resisted_by_outfit", "shares", "applied"), [(False, (0.5,), 5), (True, (0.5, 0.75), 1)])
def test_resisted_by_outfit(resisted_by_outfit: bool, shares: tuple, applied: int) -> None:
    human = _dweller(race="human", faction="children_of_atom", outfit=_outfit(**POWER_ARMOR))
    reductions = damage_reductions(human, DamageChannel.RADIATION, resisted_by_outfit=resisted_by_outfit)
    assert reductions.shares == shares
    assert reductions.apply(10) == applied
