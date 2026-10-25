"""Weapon-specific attack policy for the Arena active-skill prototype."""

from dataclasses import dataclass

from app.models.dweller import Dweller
from app.schemas.combat import CombatEffect

MAX_CHARGE = 100


@dataclass(frozen=True)
class WeaponSkill:
    """Bonus damage per target, measured as a multiple of one ordinary attack."""

    name: str
    multiplier: float
    area: bool = False

    @property
    def description(self) -> str:
        target = "each standing enemy" if self.area else "the chosen enemy"
        return f"Deal {self.multiplier:g}x normal attack damage to {target}. Extra attack on this fighter's next team turn."


# Both type and subtype matter: an energy rifle differs from a ballistic rifle.
WEAPON_SKILLS = {
    ("melee", "blunt"): WeaponSkill("Crushing Blow", 1.75),
    ("melee", "edged"): WeaponSkill("Cleave", 0.9, area=True),
    ("melee", "pointed"): WeaponSkill("Piercing Strike", 2),
    ("gun", "pistol"): WeaponSkill("Quick Draw", 1.5),
    ("gun", "rifle"): WeaponSkill("Aimed Shot", 2),
    ("gun", "shotgun"): WeaponSkill("Scattershot", 0.9, area=True),
    ("energy", "pistol"): WeaponSkill("Overcharge", 1.75),
    ("energy", "rifle"): WeaponSkill("Beam Sweep", 1, area=True),
    ("heavy", "automatic"): WeaponSkill("Full Auto", 1.75),
    ("heavy", "flamer"): WeaponSkill("Firestorm", 0.9, area=True),
    ("heavy", "explosive"): WeaponSkill("Blast Wave", 1, area=True),
}
UNARMED_SKILL = WeaponSkill("Haymaker", 1.5)


def weapon_skill(dweller: Dweller) -> WeaponSkill:
    """Use the equipped weapon, with an unarmed fallback for legacy equipment."""
    weapon = dweller.weapon
    if weapon is None:
        return UNARMED_SKILL
    return WEAPON_SKILLS.get((weapon.weapon_type, weapon.weapon_subtype), UNARMED_SKILL)


def attack_effect(dweller: Dweller | None, skill: WeaponSkill | None = None) -> CombatEffect:
    """Small visual vocabulary; combat outcomes never depend on this choice."""
    weapon = dweller.weapon if dweller else None
    if weapon is None:
        return "strike"
    if weapon.weapon_type == "energy":
        return "beam"
    if weapon.weapon_subtype == "flamer":
        return "flame"
    if weapon.weapon_subtype == "explosive":
        return "blast"
    if weapon.weapon_type == "melee":
        return "sweep" if skill and skill.area else "strike"
    return "blast" if skill and skill.area else "shot"
