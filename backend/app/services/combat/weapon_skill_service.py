"""Weapon-specific attack policy for the Arena active-skill prototype."""

from dataclasses import dataclass

from app.models.dweller import Dweller

CHARGE_PER_SECOND = 20
MAX_CHARGE = 100


@dataclass(frozen=True)
class WeaponSkill:
    """Bonus damage as a multiple of combat power, per target."""

    name: str
    multiplier: float
    area: bool = False

    @property
    def description(self) -> str:
        target = "each standing enemy" if self.area else "the weakest standing enemy"
        return f"Deal {self.multiplier:g}x combat power to {target}. Resolves next combat tick."


# Both type and subtype matter: an energy rifle differs from a ballistic rifle.
WEAPON_SKILLS = {
    ("melee", "blunt"): WeaponSkill("Crushing Blow", 2.5),
    ("melee", "edged"): WeaponSkill("Cleave", 1.5, area=True),
    ("melee", "pointed"): WeaponSkill("Piercing Strike", 3),
    ("gun", "pistol"): WeaponSkill("Quick Draw", 2.5),
    ("gun", "rifle"): WeaponSkill("Aimed Shot", 3),
    ("gun", "shotgun"): WeaponSkill("Scattershot", 1.5, area=True),
    ("energy", "pistol"): WeaponSkill("Overcharge", 3),
    ("energy", "rifle"): WeaponSkill("Beam Sweep", 1.5, area=True),
    ("heavy", "automatic"): WeaponSkill("Full Auto", 3),
    ("heavy", "flamer"): WeaponSkill("Firestorm", 1.5, area=True),
    ("heavy", "explosive"): WeaponSkill("Blast Wave", 2, area=True),
}
UNARMED_SKILL = WeaponSkill("Haymaker", 2)


def weapon_skill(dweller: Dweller) -> WeaponSkill:
    """Use the equipped weapon, with an unarmed fallback for legacy equipment."""
    weapon = dweller.weapon
    if weapon is None:
        return UNARMED_SKILL
    return WEAPON_SKILLS.get((weapon.weapon_type, weapon.weapon_subtype), UNARMED_SKILL)
