"""Resolve a dweller's equipped pet into one set of mechanical modifiers.

The single reader for pet mechanics: combat, production, radiation, happiness,
caps, XP and training resolution all ask this module instead of branching on
pet names themselves. Pure and session-free, so game-loop actors and API paths
share the same rules. Effects are catalog-resolved by pet name — the ``Pet``
model carries no effect columns, so unlisted pets are neutral pending balance
tuning.
"""

from dataclasses import dataclass

from app.utils.equipped import equipped_pet

#: Damage bonus cap: ``1 + faction + pet`` must not exceed this (pets plan §5.3).
MAX_DAMAGE_PCT_BONUS = 2.0
#: Resist cap for multiplicative-complement resists (pets plan §5.3).
MAX_RESIST_PCT = 0.95
#: Cap for additive happiness/caps/XP/training percentage bonuses (pets plan §5.3).
MAX_PCT_BONUS = 0.5


@dataclass(frozen=True)
class PetEffect:
    """Mechanical bonuses granted by one pet.

    SPECIAL and ``max_health`` are additive integers; the percentage fields are
    additive fractions (``0.25`` = +25%) and are capped by the module constants
    at the application points.
    """

    strength: int = 0
    perception: int = 0
    endurance: int = 0
    charisma: int = 0
    intelligence: int = 0
    agility: int = 0
    luck: int = 0
    max_health: int = 0
    damage_pct: float = 0.0
    incident_response_pct: float = 0.0
    radiation_resist_pct: float = 0.0
    happiness: float = 0.0
    caps_pct: float = 0.0
    xp_pct: float = 0.0
    training_speed_pct: float = 0.0


#: The no-bonus effect returned for unlisted pets.
NEUTRAL_EFFECT = PetEffect()

#: Name-keyed catalog, keyed by the same ``.strip().casefold()`` names as
#: ``PET_NAME_TO_IMAGE_FILE`` so art and effects stay aligned. Seeded so every
#: effect field is covered at least once; extend by adding a line per pet.
PET_EFFECT_BY_NAME: dict[str, PetEffect] = {
    "dogmeat (fallout 4)": PetEffect(strength=2, max_health=20, damage_pct=0.25),
    "cx404": PetEffect(luck=2, caps_pct=0.25, xp_pct=0.25),
    "vault-tec parrot": PetEffect(intelligence=2, training_speed_pct=0.25),
    "mr. pebbles": PetEffect(charisma=2, happiness=0.25),
    "pallas's cat": PetEffect(perception=2, incident_response_pct=0.25),
    "st. bernard": PetEffect(endurance=2, max_health=30, radiation_resist_pct=0.25),
    "husky": PetEffect(agility=2, damage_pct=0.25),
    "abyssinian": PetEffect(intelligence=1, xp_pct=0.25),
}


def pet_effect_for_name(name: str | None) -> PetEffect:
    """The catalog effect for a pet name, or neutral for None/blank/unknown.

    Names are normalized with ``.strip().casefold()`` to match the art map's
    keys; anything not in the catalog resolves to ``NEUTRAL_EFFECT``.
    """
    if not name:
        return NEUTRAL_EFFECT
    return PET_EFFECT_BY_NAME.get(name.strip().casefold(), NEUTRAL_EFFECT)


def pet_modifiers_for(entity: object) -> PetEffect:
    """The equipped pet's effect for an entity, or neutral when none is equipped.

    Reads the pet via ``equipped_pet`` (``__dict__``, no lazy IO) and resolves
    its name through the catalog.
    """
    pet = equipped_pet(entity)
    if pet is None:
        return NEUTRAL_EFFECT
    return pet_effect_for_name(pet.name)
