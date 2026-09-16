"""Race and faction mechanics: modifiers, perks, breeding, ghoul immunity."""

import random
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from app.core.enums import SPECIALEnum
from app.options.factions import FACTION_PERKS, FactionOption, FactionPerks, faction_restrictions, perks_for_faction
from app.options.identity_modifiers import SPECIAL_STATS, effective_stat, weapon_damage_pct
from app.options.races import (
    BREEDING_ELIGIBLE,
    RACE_MODIFIERS,
    RaceModifiers,
    RaceOption,
    can_breed,
    modifiers_for_race,
    race_of,
)
from app.services.radiation_service import apply_radiation_gain
from app.services.resource_manager import ResourceManager
from app.utils.combat import combat_power
from app.utils.dwellers import roll_child_identity


def _dweller(race: str | None, faction: str | None = None) -> SimpleNamespace:
    attrs: dict[str, str] = {}
    if race is not None:
        attrs["race"] = race
    if faction is not None:
        attrs["faction"] = faction
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

    def test_mutation_never_keeps_a_parent_race(self) -> None:
        with patch("app.utils.dwellers.game_config.breeding.race_mutation_chance", 1.0):
            races = {
                roll_child_identity(_dweller("human"), _dweller("human"), random.Random(seed))["race"]
                for seed in range(50)
            }
        assert RaceOption.HUMAN.value not in races
        assert races <= {race.value for race in RaceOption}

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
        obj.max_health = 120
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


class TestRaceModifiers:
    """Racial deltas and perks come from one table, not branch-by-branch code."""

    def test_humans_are_the_neutral_baseline(self) -> None:
        assert RACE_MODIFIERS[RaceOption.HUMAN] == RaceModifiers()

    def test_ghoul_endurance_and_radiation_immunity(self) -> None:
        ghoul = RACE_MODIFIERS[RaceOption.GHOUL]
        assert (ghoul.endurance, ghoul.radiation_immune) == (2, True)

    def test_super_mutant_trades_perception_for_brawn(self) -> None:
        mutant = RACE_MODIFIERS[RaceOption.SUPER_MUTANT]
        assert (mutant.strength, mutant.endurance, mutant.perception) == (3, 2, -2)

    def test_synth_gets_stats_and_radiation_resistance(self) -> None:
        synth = RACE_MODIFIERS[RaceOption.SYNTH]
        assert (synth.perception, synth.intelligence, synth.radiation_resist_pct) == (1, 1, 0.5)
        assert synth.radiation_immune is False

    def test_missing_or_unknown_race_defaults_to_human(self) -> None:
        assert modifiers_for_race(_dweller(None)) == RACE_MODIFIERS[RaceOption.HUMAN]
        assert modifiers_for_race(_dweller("reptilian")) == RACE_MODIFIERS[RaceOption.HUMAN]


class TestFactionPerks:
    def test_combat_perks_reuse_weapon_types(self) -> None:
        assert FACTION_PERKS[FactionOption.BROTHERHOOD_OF_STEEL].energy_weapon_damage_pct == 0.15
        assert FACTION_PERKS[FactionOption.CAESARS_LEGION].melee_damage_pct == 0.15
        assert weapon_damage_pct(_dweller("human", faction="brotherhood_of_steel"), "energy") == 0.15
        assert weapon_damage_pct(_dweller("human", faction="brotherhood_of_steel"), "melee") == 0.0

    def test_minutemen_respond_faster_to_incidents(self) -> None:
        assert FACTION_PERKS[FactionOption.MINUTEMEN].incident_response_pct == 0.15

    def test_children_of_atom_resist_radiation(self) -> None:
        assert FACTION_PERKS[FactionOption.CHILDREN_OF_ATOM].radiation_resist_pct == 0.5

    def test_unknown_or_missing_faction_is_neutral(self) -> None:
        assert perks_for_faction(_dweller("human")) == FactionPerks()
        assert perks_for_faction(_dweller("human", faction="bogus")) == FactionPerks()


class TestEffectiveStats:
    def test_modifiers_apply_on_read_without_persisting(self) -> None:
        mutant = _dweller("super_mutant")
        mutant.strength, mutant.perception = 5, 5
        assert effective_stat(mutant, "strength") == 8
        assert effective_stat(mutant, "perception") == 3
        assert mutant.strength == 5  # stored value untouched

    def test_effective_stats_never_drop_below_one(self) -> None:
        mutant = _dweller("super_mutant")
        mutant.perception = 1
        assert effective_stat(mutant, "perception") == 1

    def test_unknown_stat_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown SPECIAL stat"):
            effective_stat(_dweller("human"), "charimsa")


class TestCombatAndProductionApplication:
    def _fighter(self, race: str, weapon=None, faction: str | None = None, **stats: int):
        dweller = _dweller(race, faction=faction)
        dweller.level = 1
        dweller.weapon = weapon
        dweller.apprentice_stat = None
        for stat in SPECIAL_STATS:
            setattr(dweller, stat, stats.get(stat, 5))
        return dweller

    @staticmethod
    def _weapon(weapon_type: str, damage: int = 10):
        weapon = SimpleNamespace()
        weapon.weapon_type = SimpleNamespace(value=weapon_type)
        weapon.damage_min = weapon.damage_max = damage
        return weapon

    def test_racial_stats_change_combat_power(self) -> None:
        assert combat_power(self._fighter("super_mutant")) > combat_power(self._fighter("human"))
        assert combat_power(self._fighter("ghoul")) > combat_power(self._fighter("human"))

    def test_faction_perk_boosts_only_its_weapon_type(self) -> None:
        energy = self._weapon("energy")
        brotherhood = self._fighter("human", weapon=energy, faction="brotherhood_of_steel")
        neutral = self._fighter("human", weapon=energy)
        assert combat_power(brotherhood) > combat_power(neutral)

        melee = self._weapon("melee")
        legionnaire = self._fighter("human", weapon=melee, faction="caesars_legion")
        assert combat_power(legionnaire) > combat_power(self._fighter("human", weapon=melee))

    def test_racial_and_faction_stats_reach_room_production(self) -> None:
        room = SimpleNamespace(name="Power Generator", ability=SPECIALEnum.STRENGTH, output=10, tier=1)
        manager = ResourceManager()

        human = self._fighter("human", faction="vault_dweller")
        mutant = self._fighter("super_mutant", faction="vault_dweller")

        human_output = manager._calculate_room_production(room, [human], 60)
        mutant_output = manager._calculate_room_production(room, [mutant], 60)

        assert mutant_output > human_output
        assert human_output == pytest.approx(10 * 5 * 0.1 * 1.0 * 1.05 * 60)

    def test_radiation_resist_scales_the_dose(self) -> None:
        synth = _dweller("synth")
        synth.is_dead = False
        synth.radiation, synth.max_health, synth.health = 10, 120, 100
        synth.effective_max_health = 100

        assert apply_radiation_gain(synth, 10) is True
        assert synth.radiation == 15  # 50% racial resist

    def test_radiation_immunity_comes_from_the_table(self) -> None:
        ghoul = _dweller("ghoul")
        ghoul.is_dead = False
        ghoul.radiation, ghoul.max_health, ghoul.health = 10, 120, 100
        ghoul.effective_max_health = 100

        assert apply_radiation_gain(ghoul, 10) is False
        assert ghoul.radiation == 10


class TestIncidentResponsePerk:
    async def test_minutemen_responder_takes_less_incident_damage(self) -> None:
        from app.models.incident import IncidentType
        from app.services.combat.incident_round import apply_damage

        def responder(faction: str | None):
            dweller = _dweller("human", faction=faction)
            dweller.health = 100
            dweller.is_dead = False
            dweller.effective_max_health = 100
            return dweller

        minuteman, plain = responder("minutemen"), responder(None)
        incident = SimpleNamespace(type=IncidentType.RAIDER_ATTACK)

        await apply_damage(MagicMock(), incident, [minuteman, plain], damage_to_dwellers=40)

        assert minuteman.health > plain.health
