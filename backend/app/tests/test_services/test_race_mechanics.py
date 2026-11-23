"""Race and faction mechanics: modifiers, perks, breeding, ghoul immunity."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from app.core.enums import SPECIALEnum
from app.core.game_config import game_config
from app.models.pet import Pet
from app.options.factions import FACTION_PERKS, FactionOption, FactionPerks, faction_restrictions, perks_for_faction
from app.options.identity_modifiers import SPECIAL_STATS, effective_stat, identity_modifiers_for, weapon_damage_pct
from app.options.races import (
    BREEDING_ELIGIBLE,
    RACE_MODIFIERS,
    DiscomfortSeverity,
    RaceModifiers,
    RaceOption,
    SocialPresence,
    can_breed,
    can_take_purposeful_action,
    can_use_radaway,
    chronological_years,
    discomfort_between,
    is_ageless,
    modifiers_for_race,
    race_of,
    social_presence,
    state_of_being_of,
    state_stat_deltas_for,
    visual_vs_real_age,
)
from app.services.resource_manager_service import ResourceManager
from app.utils.combat import combat_power
from app.utils.dwellers import roll_child_identity
from app.utils.radiation import apply_radiation_gain


@pytest.fixture(autouse=True)
def _identity_mechanics_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """The faction half ships dark, so behaviour tests state both switches as a precondition."""
    monkeypatch.setattr(game_config.features, "race_mechanics", True)
    monkeypatch.setattr(game_config.features, "faction_mechanics", True)


@pytest.fixture(params=[True, False], ids=["race_on", "race_off"])
def race_flag(request, monkeypatch: pytest.MonkeyPatch) -> bool:
    monkeypatch.setattr(game_config.features, "race_mechanics", request.param)
    return request.param


@pytest.fixture(params=[True, False], ids=["faction_on", "faction_off"])
def faction_flag(request, monkeypatch: pytest.MonkeyPatch) -> bool:
    monkeypatch.setattr(game_config.features, "faction_mechanics", request.param)
    return request.param


@pytest.fixture
def flag_state(race_flag: bool, faction_flag: bool) -> tuple[bool, bool]:
    return race_flag, faction_flag


def _dweller(race: str | None, faction: str | None = None, state: str | None = None) -> SimpleNamespace:
    attrs: dict[str, str] = {}
    if race is not None:
        attrs["race"] = race
    if faction is not None:
        attrs["faction"] = faction
    if state is not None:
        attrs["state_of_being"] = state
    return SimpleNamespace(visual_attributes=attrs)


def _living(entity, radiation: int = 10):
    entity.is_dead = False
    entity.radiation = radiation
    entity.max_health = entity.health = entity.effective_max_health = 100
    return entity


def _pet(name: str) -> Pet:
    return Pet(name=name, rarity="Legendary")


def _room() -> SimpleNamespace:
    return SimpleNamespace(name="Power Generator", ability=SPECIALEnum.STRENGTH, output=10, tier=1)


def _fighter(race: str, weapon=None, faction: str | None = None, **stats: int):
    dweller = _dweller(race, faction=faction)
    dweller.level = 1
    dweller.weapon = weapon
    dweller.apprentice_stat = None
    for stat in SPECIAL_STATS:
        setattr(dweller, stat, stats.get(stat, 5))
    return dweller


def _weapon(weapon_type: str, damage: int = 10) -> SimpleNamespace:
    weapon = SimpleNamespace()
    weapon.weapon_type = SimpleNamespace(value=weapon_type)
    weapon.damage_min = weapon.damage_max = damage
    return weapon


class TestRaceHelpers:
    def test_race_of_reads_valid_race_and_rejects_missing_or_invalid(self) -> None:
        assert race_of(_dweller("ghoul")) == RaceOption.GHOUL
        assert race_of(_dweller(None)) is None
        assert race_of(_dweller("reptilian")) is None
        assert race_of(SimpleNamespace(visual_attributes=None)) is None

    def test_social_presence_classifies_race_and_state(self) -> None:
        assert social_presence(_dweller("human")) is SocialPresence.NORMAL
        assert social_presence(_dweller("ghoul")) is SocialPresence.GHOUL
        assert social_presence(_dweller("ghoul", state="feral")) is SocialPresence.FERAL
        assert social_presence(_dweller("super_mutant")) is SocialPresence.MUTANT
        assert social_presence(_dweller("super_mutant", state="behemoth")) is SocialPresence.BEHEMOTH
        assert social_presence(_dweller("synth", state="gen_1")) is SocialPresence.SYNTH_GEN_1
        assert social_presence(_dweller("synth", state="gen_2")) is SocialPresence.SYNTH_GEN_2
        assert social_presence(_dweller("synth", state="gen_3")) is SocialPresence.NORMAL

    def test_discomfort_matrix_ferals_super_mutants_and_synths(self) -> None:
        human, ghoul, mutant = _dweller("human"), _dweller("ghoul"), _dweller("super_mutant")
        feral, behemoth = _dweller("ghoul", state="feral"), _dweller("super_mutant", state="behemoth")
        gen_1, gen_2, gen_3 = (_dweller("synth", state=gen) for gen in ("gen_1", "gen_2", "gen_3"))

        assert discomfort_between(human, human) is None
        assert discomfort_between(human, ghoul) is None
        human_feral = discomfort_between(human, feral)
        assert human_feral is not None
        assert human_feral.severity is DiscomfortSeverity.STRONG
        assert human_feral.source is SocialPresence.FERAL
        assert discomfort_between(ghoul, feral).severity is DiscomfortSeverity.MILD
        assert discomfort_between(human, mutant).severity is DiscomfortSeverity.MODERATE
        assert discomfort_between(human, behemoth).severity is DiscomfortSeverity.STRONG
        assert discomfort_between(mutant, behemoth) is None
        assert discomfort_between(feral, feral) is None
        assert discomfort_between(human, gen_3) is None
        assert discomfort_between(human, gen_2).severity is DiscomfortSeverity.MILD
        assert discomfort_between(human, gen_1).severity is DiscomfortSeverity.MODERATE
        assert discomfort_between(gen_2, gen_2) is None
        assert discomfort_between(gen_1, gen_1) is None

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
        assert can_breed(_dweller("synth", state="gen_3")) is False
        assert can_breed(_dweller("super_mutant")) is False
        assert can_breed(_dweller(None)) is True


class TestAgelessRaces:
    def test_only_humans_senesce(self) -> None:
        assert is_ageless(RaceOption.HUMAN) is False
        assert is_ageless(RaceOption.GHOUL) is True
        assert is_ageless(RaceOption.SUPER_MUTANT) is True
        assert is_ageless(RaceOption.SYNTH) is True
        assert is_ageless(None) is False
        assert is_ageless("reptilian") is False

    def test_visual_vs_real_age_keeps_ghoul_birth_date(self) -> None:
        ghoul = SimpleNamespace(
            visual_attributes={"race": "ghoul", "state_of_being": "sane"},
            age_group="adult",
            birth_date=datetime(1800, 1, 1),
        )
        view = visual_vs_real_age(ghoul, now=datetime(2000, 1, 1))
        assert view["visual"] == "adult"
        assert view["real_years"] == pytest.approx(200.0, abs=1.0)
        assert view["ageless"] is True

    def test_pregen_non_humans_never_spawn_as_elders(self) -> None:
        from app.utils.dwellers import create_random_common_dweller

        for seed in range(50):
            dweller = create_random_common_dweller(seed=seed)
            race = (dweller["visual_attributes"] or {}).get("race")
            if race != RaceOption.HUMAN.value:
                assert dweller["age_group"] != "elder", f"seed {seed} spawned {race} elder"

    def test_chronological_age_handles_timezones(self) -> None:
        assert chronological_years(datetime.now(UTC) - timedelta(days=365)) == pytest.approx(1.0, abs=0.01)
        assert chronological_years(datetime(2000, 1, 1, tzinfo=UTC), datetime(2001, 1, 1)) == pytest.approx(
            366 / 365.2425
        )


class TestStateOfBeingDeltas:
    def test_state_reader(self) -> None:
        assert state_of_being_of(_dweller("ghoul")) is None
        assert state_of_being_of(_dweller("ghoul", state="feral")) == "feral"

    def test_feral_ghoul_and_behemoth_trade_mind_for_body(self) -> None:
        feral = state_stat_deltas_for(_dweller("ghoul", state="feral"))
        assert feral["charisma"] < 0
        assert feral["intelligence"] < 0
        assert feral["strength"] > 0
        behemoth = state_stat_deltas_for(_dweller("super_mutant", state="behemoth"))
        assert behemoth["strength"] > 0
        assert behemoth["intelligence"] < 0

    def test_gen_3_passing_synth_has_no_delta(self) -> None:
        assert state_stat_deltas_for(_dweller("synth", state="gen_3")) == {}

    def test_effective_stat_includes_state_delta(self) -> None:
        feral = _dweller("ghoul", state="feral")
        feral.charisma = 5
        assert effective_stat(feral, "charisma") == 1  # 5 - 4, floored at 1

    def test_state_delta_follows_race_switch(self, monkeypatch) -> None:
        monkeypatch.setattr(game_config.features, "race_mechanics", False)
        feral = _dweller("ghoul", state="feral")
        feral.charisma = 5
        assert effective_stat(feral, "charisma") == 5

    def test_chronological_years_needs_a_birth_date(self) -> None:
        assert chronological_years(None) is None


@pytest.mark.parametrize(
    ("race", "state"),
    [("ghoul", None), ("super_mutant", None), ("synth", None), ("synth", "gen_1"), ("synth", "gen_2")],
)
def test_synthetic_and_mutated_races_are_radiation_immune(race: str, state: str | None) -> None:
    entity = _living(_dweller(race, state=state), 0)
    assert identity_modifiers_for(entity).radiation_immune is True
    assert can_use_radaway(entity) is False
    assert apply_radiation_gain(entity, 25, resisted_by_outfit=False) is False
    assert entity.radiation == 0


def test_gen_3_synth_accumulates_radiation_and_can_use_radaway() -> None:
    entity = _living(_dweller("synth", state="gen_3"), 0)
    assert identity_modifiers_for(entity).radiation_immune is False
    assert can_use_radaway(entity) is True
    assert apply_radiation_gain(entity, 25, resisted_by_outfit=False) is True
    assert entity.radiation == 25


def test_humans_can_use_radaway() -> None:
    assert can_use_radaway(_dweller("human")) is True


@pytest.mark.parametrize(("race", "state"), [("ghoul", "feral"), ("super_mutant", "behemoth")])
def test_non_reasoning_states_cannot_take_purposeful_actions(race: str, state: str) -> None:
    assert can_take_purposeful_action(_dweller(race, state=state)) is False


class TestNewbornIdentity:
    def test_child_inherits_parent_race(self) -> None:
        assert roll_child_identity(_dweller("human"), _dweller("human"))["race"] == RaceOption.HUMAN.value

    def test_newborn_gets_no_faction_while_switch_off(self, monkeypatch) -> None:
        """System assignment must not create factions the switch hides."""
        monkeypatch.setattr(game_config.features, "faction_mechanics", False)
        assert roll_child_identity(_dweller("human"), _dweller("human"))["faction"] == "none"

    def test_child_identity_uses_lore_valid_faction(self) -> None:
        identity = roll_child_identity(_dweller("human"), _dweller("human"))
        valid = {faction.value for faction in faction_restrictions[RaceOption(identity["race"])]}
        assert identity["faction"] in valid


class TestGhoulRadiationImmunity:
    def _dweller(self, race: str, radiation: int = 50) -> MagicMock:
        obj = MagicMock()
        obj.is_dead = False
        obj.radiation = radiation
        obj.max_health, obj.health, obj.effective_max_health = 120, 80, 100
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
    def test_race_modifier_table(self) -> None:
        assert RACE_MODIFIERS[RaceOption.HUMAN] == RaceModifiers()
        ghoul, mutant = RACE_MODIFIERS[RaceOption.GHOUL], RACE_MODIFIERS[RaceOption.SUPER_MUTANT]
        synth = RACE_MODIFIERS[RaceOption.SYNTH]
        assert (ghoul.endurance, ghoul.radiation_immune) == (2, True)
        assert (mutant.strength, mutant.endurance, mutant.perception) == (3, 2, -2)
        assert (synth.perception, synth.intelligence, synth.radiation_immune) == (1, 1, True)

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

    def test_pet_damage_bonus_stacks_with_faction_perk(self) -> None:
        dweller = _dweller("human", faction="brotherhood_of_steel")
        dweller.pet = _pet("dogmeat (fallout 4)")  # damage_pct 0.25
        assert weapon_damage_pct(dweller, "energy") == pytest.approx(0.15 + 0.25)

    def test_pet_damage_bonus_applies_without_faction_perk(self) -> None:
        dweller = _dweller("human")
        dweller.pet = _pet("husky")  # damage_pct 0.25
        assert weapon_damage_pct(dweller, "energy") == pytest.approx(0.25)

    def test_weapon_damage_pct_caps_total_multiplier(self, monkeypatch) -> None:
        from app.options.pet_modifiers import PET_EFFECT_BY_NAME, PetEffect

        monkeypatch.setitem(PET_EFFECT_BY_NAME, "cap test pet", PetEffect(damage_pct=1.5))
        dweller = _dweller("human", faction="brotherhood_of_steel")
        dweller.pet = _pet("cap test pet")
        # 1 + 0.15 + 1.5 = 2.65 → capped at 2.0 → bonus 1.0
        assert weapon_damage_pct(dweller, "energy") == pytest.approx(1.0)

    def test_impossible_race_faction_pair_earns_no_perk(self) -> None:
        assert perks_for_faction(_dweller("synth", faction="brotherhood_of_steel")) == FactionPerks()
        assert perks_for_faction(_dweller("ghoul", faction="caesars_legion")) == FactionPerks()
        assert perks_for_faction(_dweller("human", faction="brotherhood_of_steel")) != FactionPerks()


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

    def test_effective_stat_includes_equipped_pet(self) -> None:
        mutant = _dweller("super_mutant")
        mutant.strength = 5
        mutant.pet = _pet("dogmeat (fallout 4)")  # strength +2
        assert effective_stat(mutant, "strength") == 10  # 5 + 3 (race) + 2 (pet)

    def test_effective_stat_ignores_pet_without_stat_bonus(self) -> None:
        mutant = _dweller("super_mutant")
        mutant.strength = 5
        mutant.pet = _pet("cx404")  # luck/caps/xp only
        assert effective_stat(mutant, "strength") == 8

    def test_unknown_stat_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="Unknown SPECIAL stat"):
            effective_stat(_dweller("human"), "charimsa")


class TestCombatAndProductionApplication:
    def test_racial_stats_change_combat_power(self) -> None:
        assert combat_power(_fighter("super_mutant")) > combat_power(_fighter("human"))
        assert combat_power(_fighter("ghoul")) > combat_power(_fighter("human"))

    def test_faction_perk_boosts_only_its_weapon_type(self) -> None:
        energy = _weapon("energy")
        neutral = _fighter("human", weapon=energy)
        assert combat_power(_fighter("human", weapon=energy, faction="brotherhood_of_steel")) > combat_power(neutral)

        melee = _weapon("melee")
        neutral = _fighter("human", weapon=melee)
        assert combat_power(_fighter("human", weapon=melee, faction="caesars_legion")) > combat_power(neutral)

    def test_racial_and_faction_stats_reach_room_production(self) -> None:
        manager = ResourceManager()
        human = _fighter("human", faction="vault_dweller")
        mutant = _fighter("super_mutant", faction="vault_dweller")
        human_output = manager._calculate_room_production(_room(), [human], 60)
        assert manager._calculate_room_production(_room(), [mutant], 60) > human_output
        assert human_output == pytest.approx(10 * 5 * game_config.resource.base_production_rate * 1.0 * 1.05 * 60)

    def test_production_perk_is_per_worker_not_per_room(self) -> None:
        """A single faction bonus must not inflate neutral coworkers in the same room."""
        manager = ResourceManager()
        vault_dweller, neutral = _fighter("human", faction="vault_dweller"), _fighter("human", faction="none")
        mixed = manager._calculate_room_production(_room(), [vault_dweller, neutral], 60)
        # 5 stats x 1.05 for the Vault Dweller plus 5 stats x 1.0 for the neutral worker.
        rate = game_config.resource.base_production_rate
        assert mixed == pytest.approx(10 * (5 * 1.05 + 5 * 1.0) * rate * 1.0 * 60)
        assert mixed < 10 * (5 + 5) * rate * 1.0 * 1.05 * 60

    def test_visible_synth_immunity_blocks_the_dose(self) -> None:
        synth = _living(_dweller("synth", state="gen_1"))
        assert apply_radiation_gain(synth, 10) is False
        assert synth.radiation == 10

    def test_radiation_immunity_comes_from_the_table(self) -> None:
        ghoul = _living(_dweller("ghoul"))
        assert apply_radiation_gain(ghoul, 10) is False
        assert ghoul.radiation == 10


class TestIncidentResponsePerk:
    async def test_minutemen_responder_takes_less_incident_damage(self) -> None:
        from app.core.enums import IncidentType
        from app.services.combat.incident_round import apply_damage

        minuteman = _living(_dweller("human", faction="minutemen"))
        plain = _living(_dweller("human"))
        incident = SimpleNamespace(type=IncidentType.RAIDER_ATTACK)
        await apply_damage(MagicMock(), incident, [minuteman, plain], damage_to_dwellers=40)
        assert minuteman.health > plain.health

    async def test_reported_damage_reflects_the_response_perk(self) -> None:
        """Callers report what responders took, so a mitigated round cannot read as raw damage."""
        from app.core.enums import IncidentType
        from app.services.combat.incident_round import apply_damage

        minuteman = _living(_dweller("human", faction="minutemen"))
        incident = SimpleNamespace(type=IncidentType.RAIDER_ATTACK)
        _, _, damage_taken = await apply_damage(MagicMock(), incident, [minuteman], damage_to_dwellers=20)
        assert damage_taken == 17  # 20 less the 15% response perk


class TestFeatureFlag:
    """Race and faction ship on separate switches, so either can go dark alone."""

    def test_racial_stat_delta_follows_race_switch(self, race_flag: bool) -> None:
        mutant = _dweller("super_mutant")
        mutant.strength = 5
        assert effective_stat(mutant, "strength") == (8 if race_flag else 5)

    def test_radiation_immunity_survives_race_switch(self, race_flag: bool) -> None:
        assert identity_modifiers_for(_dweller("synth", state="gen_1")).radiation_immune is True
        assert identity_modifiers_for(_dweller("synth", state="gen_3")).radiation_immune is False

    def test_faction_perks_follow_faction_switch(self, faction_flag: bool) -> None:
        assert weapon_damage_pct(_dweller("human", faction="brotherhood_of_steel"), "energy") == (
            0.15 if faction_flag else 0.0
        )
        assert identity_modifiers_for(_dweller("human", faction="vault_dweller")).production_pct == (
            0.05 if faction_flag else 0.0
        )

    def test_ghoul_immunity_survives_either_switch(self, flag_state) -> None:
        """Ghoul immunity predates both flags and must survive every combination."""
        ghoul = _living(_dweller("ghoul"))
        assert identity_modifiers_for(ghoul).radiation_immune is True
        assert apply_radiation_gain(ghoul, 10) is False
        assert ghoul.radiation == 10

    def test_flag_off_reverts_combat_and_production_to_raw_stats(self, monkeypatch) -> None:
        monkeypatch.setattr(game_config.features, "race_mechanics", False)
        monkeypatch.setattr(game_config.features, "faction_mechanics", False)
        mutant = _fighter("super_mutant", faction="super_mutant_tribe")
        assert ResourceManager()._calculate_room_production(_room(), [mutant], 60) == pytest.approx(
            10 * 5 * game_config.resource.base_production_rate * 1.0 * 60
        )
        assert combat_power(mutant) == combat_power(_fighter("human"))

    def test_faction_off_alone_leaves_race_mechanics_working(self, monkeypatch) -> None:
        """The faction switch must not drag race down with it."""
        monkeypatch.setattr(game_config.features, "race_mechanics", True)
        monkeypatch.setattr(game_config.features, "faction_mechanics", False)
        mutant = _dweller("super_mutant")
        mutant.strength = 5
        assert effective_stat(mutant, "strength") == 8
        assert weapon_damage_pct(_dweller("human", faction="brotherhood_of_steel"), "energy") == 0.0
        assert identity_modifiers_for(_dweller("human", faction="vault_dweller")).production_pct == 0.0
