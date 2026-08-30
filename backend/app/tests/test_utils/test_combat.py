"""Unit tests for the weapon-type-aware combat power formula."""

import pytest

from app.models.dweller import Dweller
from app.models.weapon import Weapon
from app.schemas.common import WeaponSubtypeEnum, WeaponTypeEnum
from app.utils.combat import combat_power, total_combat_power


def make_dweller(stats: dict[str, int], weapon: Weapon | None = None, level: int = 1) -> Dweller:
    return Dweller(level=level, weapon=weapon, **stats)


def make_weapon(weapon_type: WeaponTypeEnum, damage_min: int = 5, damage_max: int = 15) -> Weapon:
    subtypes = {
        WeaponTypeEnum.MELEE: WeaponSubtypeEnum.EDGED,
        WeaponTypeEnum.GUN: WeaponSubtypeEnum.PISTOL,
        WeaponTypeEnum.ENERGY: WeaponSubtypeEnum.RIFLE,
        WeaponTypeEnum.HEAVY: WeaponSubtypeEnum.EXPLOSIVE,
    }
    return Weapon(
        name="Test Weapon",
        weapon_type=weapon_type,
        weapon_subtype=subtypes[weapon_type],
        stat="strength",
        damage_min=damage_min,
        damage_max=damage_max,
    )


ALL_STATS = {"strength": 5, "perception": 5, "endurance": 5, "charisma": 5, "intelligence": 5, "agility": 5, "luck": 5}


class TestWeaponTypeWeights:
    def test_melee_favors_strength_agility_over_endurance_luck(self):
        primary = make_dweller(
            {
                "strength": 10,
                "agility": 10,
                "perception": 1,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 1,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.MELEE),
        )
        secondary = make_dweller(
            {
                "strength": 1,
                "agility": 1,
                "perception": 1,
                "endurance": 10,
                "charisma": 1,
                "intelligence": 1,
                "luck": 10,
            },
            make_weapon(WeaponTypeEnum.MELEE),
        )
        assert combat_power(primary) > combat_power(secondary)

    def test_gun_favors_perception_agility_over_strength_endurance(self):
        primary = make_dweller(
            {
                "strength": 1,
                "perception": 10,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 1,
                "agility": 10,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.GUN),
        )
        secondary = make_dweller(
            {
                "strength": 10,
                "perception": 1,
                "endurance": 10,
                "charisma": 1,
                "intelligence": 1,
                "agility": 1,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.GUN),
        )
        assert combat_power(primary) > combat_power(secondary)

    def test_energy_favors_intelligence_perception_over_strength_agility(self):
        primary = make_dweller(
            {
                "strength": 1,
                "perception": 10,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 10,
                "agility": 1,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.ENERGY),
        )
        secondary = make_dweller(
            {
                "strength": 10,
                "perception": 1,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 1,
                "agility": 10,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.ENERGY),
        )
        assert combat_power(primary) > combat_power(secondary)

    def test_heavy_favors_strength_endurance_over_intelligence_perception(self):
        primary = make_dweller(
            {
                "strength": 10,
                "perception": 1,
                "endurance": 10,
                "charisma": 1,
                "intelligence": 1,
                "agility": 1,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.HEAVY),
        )
        secondary = make_dweller(
            {
                "strength": 1,
                "perception": 10,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 10,
                "agility": 1,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.HEAVY),
        )
        assert combat_power(primary) > combat_power(secondary)

    def test_primary_beats_secondary_only_for_matching_weapon_type(self):
        strength_agility = make_dweller(
            {
                "strength": 10,
                "agility": 10,
                "perception": 1,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 1,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.MELEE),
        )
        perception_agility = make_dweller(
            {
                "strength": 1,
                "perception": 10,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 1,
                "agility": 10,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.MELEE),
        )
        assert combat_power(strength_agility) > combat_power(perception_agility)

        gun_primary = make_dweller(
            {
                "strength": 1,
                "perception": 10,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 1,
                "agility": 10,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.GUN),
        )
        gun_secondary = make_dweller(
            {
                "strength": 10,
                "agility": 10,
                "perception": 1,
                "endurance": 1,
                "charisma": 1,
                "intelligence": 1,
                "luck": 1,
            },
            make_weapon(WeaponTypeEnum.GUN),
        )
        assert combat_power(gun_primary) > combat_power(gun_secondary)


class TestUnarmed:
    def test_unarmed_uses_balanced_spread_with_strength_lean(self):
        strength = make_dweller(
            {"strength": 10, "perception": 1, "endurance": 1, "charisma": 1, "intelligence": 1, "agility": 1, "luck": 1}
        )
        charisma = make_dweller(
            {"strength": 1, "perception": 1, "endurance": 1, "charisma": 10, "intelligence": 1, "agility": 1, "luck": 1}
        )
        assert combat_power(strength) > combat_power(charisma)

    def test_unarmed_is_balanced_across_non_strength_stats(self):
        endurance = make_dweller(
            {"strength": 1, "perception": 1, "endurance": 10, "charisma": 1, "intelligence": 1, "agility": 1, "luck": 1}
        )
        agility = make_dweller(
            {"strength": 1, "perception": 1, "endurance": 1, "charisma": 1, "intelligence": 1, "agility": 10, "luck": 1}
        )
        assert combat_power(endurance) == pytest.approx(combat_power(agility))


class TestDamageAndLevel:
    def test_weapon_damage_contributes(self):
        weak = make_dweller(ALL_STATS, make_weapon(WeaponTypeEnum.MELEE, damage_min=1, damage_max=3))
        strong = make_dweller(ALL_STATS, make_weapon(WeaponTypeEnum.MELEE, damage_min=10, damage_max=20))
        assert combat_power(strong) > combat_power(weak)

    def test_level_bonus_contributes(self):
        low = make_dweller(ALL_STATS, level=1)
        high = make_dweller(ALL_STATS, level=10)
        assert combat_power(high) - combat_power(low) == pytest.approx(9 * 2)

    def test_magnitude_comparable_to_old_formula(self):
        # A 5-across-the-board dweller with a weapon should land near the old
        # value (5 stat power + avg damage 10 + level 2*1) so difficulty tuning holds.
        dweller = make_dweller(ALL_STATS, make_weapon(WeaponTypeEnum.MELEE), level=1)
        power = combat_power(dweller)
        assert 12 < power < 22


class TestTotalCombatPower:
    def test_total_sums_individual_powers(self):
        a = make_dweller(ALL_STATS, level=1)
        b = make_dweller(ALL_STATS, level=2)
        assert total_combat_power([a, b]) == pytest.approx(combat_power(a) + combat_power(b))
