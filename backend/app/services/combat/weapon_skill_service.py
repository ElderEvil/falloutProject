"""Weapon-specific attack policy for the Arena active-skill prototype."""

from dataclasses import dataclass

from app.models.dweller import Dweller
from app.options.races import passes_as_human, race_of, state_of_being_of
from app.schemas.combat import CombatBody, CombatEffect, CombatSkillIcon
from app.utils.weapon_naming import family_key

MAX_CHARGE = 100


@dataclass(frozen=True)
class WeaponSkill:
    """Bonus damage per target, measured as a multiple of one ordinary attack."""

    name: str
    multiplier: float
    area: bool = False
    icon: CombatSkillIcon = "unarmed"

    @property
    def description(self) -> str:
        target = "each standing enemy" if self.area else "the chosen enemy"
        return f"Deal {self.multiplier:g}x normal attack damage to {target}. Extra attack on this fighter's next team turn."


# Both type and subtype matter: an energy rifle differs from a ballistic rifle.
WEAPON_SKILLS = {
    ("melee", "blunt"): WeaponSkill("Crushing Blow", 1.75, icon="melee-blunt"),
    ("melee", "edged"): WeaponSkill("Cleave", 0.9, area=True, icon="melee-edged"),
    ("melee", "pointed"): WeaponSkill("Piercing Strike", 2, icon="melee-pointed"),
    ("gun", "pistol"): WeaponSkill("Quick Draw", 1.5, icon="gun-pistol"),
    ("gun", "rifle"): WeaponSkill("Aimed Shot", 2, icon="gun-rifle"),
    ("gun", "shotgun"): WeaponSkill("Scattershot", 0.9, area=True, icon="gun-shotgun"),
    ("energy", "pistol"): WeaponSkill("Overcharge", 1.75, icon="energy-pistol"),
    ("energy", "rifle"): WeaponSkill("Beam Sweep", 1, area=True, icon="energy-rifle"),
    ("heavy", "automatic"): WeaponSkill("Full Auto", 1.75, icon="heavy-automatic"),
    ("heavy", "flamer"): WeaponSkill("Firestorm", 0.9, area=True, icon="heavy-flamer"),
    ("heavy", "explosive"): WeaponSkill("Blast Wave", 1, area=True, icon="heavy-explosive"),
}
UNARMED_SKILL = WeaponSkill("Haymaker", 1.5)


def weapon_skill(dweller: Dweller) -> WeaponSkill:
    """Use the equipped weapon, with an unarmed fallback for legacy equipment."""
    weapon = dweller.weapon
    if weapon is None:
        return UNARMED_SKILL
    return WEAPON_SKILLS.get((weapon.weapon_type, weapon.weapon_subtype), UNARMED_SKILL)


def combat_body(dweller: Dweller | None) -> CombatBody:
    """Snapshot presentation from actual equipment and identity; never infer armor from art."""
    if dweller is None:
        return "human"
    if dweller.outfit and dweller.outfit.outfit_type == "power_armor":
        return "power-armor"
    race = race_of(dweller)
    state = state_of_being_of(dweller)
    if race == "ghoul":
        return "feral" if state in {"wild", "feral"} else "ghoul"
    if race == "super_mutant":
        return "behemoth" if state == "behemoth" else "mutant"
    if race == "synth" and not passes_as_human(race, state):
        return "synth"
    return "human"


def attack_effect(dweller: Dweller | None, skill: WeaponSkill | None = None) -> CombatEffect:
    """Small visual vocabulary; combat outcomes never depend on this choice."""
    weapon = dweller.weapon if dweller else None
    if weapon is None:
        return "punch" if dweller else "strike"
    family = family_key(weapon.name)
    if family == "power fist":
        return "punch"
    if family == "pool cue" or weapon.weapon_subtype == "pointed":
        return "thrust"
    if family == "junk jet":
        return "debris"
    if family in {"plasma pistol", "plasma rifle", "alien blaster", "alien disintegrator", "pulse rifle"}:
        return "pulse"
    if family in {"gatling laser", "ultracite gatling laser"}:
        return "beam"
    if weapon.weapon_type == "energy":
        return "beam"
    if weapon.weapon_subtype == "flamer":
        return "flame"
    if weapon.weapon_subtype == "explosive":
        return "blast"
    if weapon.weapon_type == "melee":
        return "sweep" if weapon.weapon_subtype == "edged" or (skill and skill.area) else "strike"
    if weapon.weapon_subtype in {"automatic", "shotgun"}:
        return "burst"
    return "shot"
