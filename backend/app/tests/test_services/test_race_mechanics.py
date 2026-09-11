"""Race mechanics: breeding eligibility, newborn inheritance/mutation, ghoul immunity."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.options.factions import faction_restrictions
from app.options.races import BREEDING_ELIGIBLE, RaceOption, can_breed, race_of
from app.services.radiation_service import apply_radiation_gain
from app.utils.dwellers import roll_child_identity


def _dweller(race: str | None) -> SimpleNamespace:
    attrs = {"race": race} if race is not None else {}
    return SimpleNamespace(visual_attributes=attrs)


class TestRaceHelpers:
    def test_race_of_reads_valid_race(self) -> None:
        assert race_of(_dweller("ghoul")) == RaceOption.GHOUL

    def test_race_of_returns_none_for_missing_or_invalid(self) -> None:
        assert race_of(_dweller(None)) is None
        assert race_of(_dweller("reptilian")) is None
        assert race_of(SimpleNamespace(visual_attributes=None)) is None

    def test_only_humans_are_breeding_eligible(self) -> None:
        assert BREEDING_ELIGIBLE == {
            RaceOption.HUMAN: True,
            RaceOption.GHOUL: False,
            RaceOption.SUPER_MUTANT: False,
            RaceOption.SYNTH: False,
        }
        assert can_breed(_dweller("human")) is True
        assert can_breed(_dweller("ghoul")) is False
        assert can_breed(_dweller("synth")) is False
        assert can_breed(_dweller("super_mutant")) is False

    def test_entity_without_race_defaults_to_human(self) -> None:
        assert can_breed(_dweller(None)) is True


class TestNewbornIdentity:
    def test_child_inherits_parent_race_without_mutation(self) -> None:
        with patch("app.utils.dwellers.game_config.breeding.race_mutation_chance", 0.0):
            identity = roll_child_identity(_dweller("human"), _dweller("human"))
        assert identity["race"] == RaceOption.HUMAN.value

    def test_mutation_rolls_a_different_race(self) -> None:
        with patch("app.utils.dwellers.game_config.breeding.race_mutation_chance", 1.0):
            identity = roll_child_identity(_dweller("human"), _dweller("human"))
        assert identity["race"] in {race.value for race in RaceOption}
        assert identity["faction"]

    def test_child_identity_uses_lore_valid_faction(self) -> None:
        with patch("app.utils.dwellers.game_config.breeding.race_mutation_chance", 0.0):
            identity = roll_child_identity(_dweller("human"), _dweller("human"))
        valid = {faction.value for faction in faction_restrictions[RaceOption(identity["race"])]}
        assert identity["faction"] in valid


class TestGhoulRadiationImmunity:
    def _dweller(self, race: str, radiation: int = 50) -> MagicMock:
        obj = MagicMock()
        obj.is_dead = False
        obj.radiation = radiation
        obj.health = 80
        obj.effective_max_health = 100
        obj.visual_attributes = {"race": race}
        return obj

    def test_ghoul_gains_no_radiation(self) -> None:
        ghoul = self._dweller("ghoul")
        assert apply_radiation_gain(ghoul, 25) is False
        assert ghoul.radiation == 50

    def test_human_still_accumulates_radiation(self) -> None:
        human = self._dweller("human")
        assert apply_radiation_gain(human, 25) is True
        assert human.radiation == 75

    def test_dead_dweller_unchanged(self) -> None:
        human = self._dweller("human")
        human.is_dead = True
        assert apply_radiation_gain(human, 25) is False
        assert human.radiation == 50
