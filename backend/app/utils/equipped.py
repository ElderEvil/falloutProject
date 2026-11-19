"""Central accessor for a dweller's equipped outfit and pet.

Callers must eager-load outfit/pet; a missing relationship means "not equipped" and must
never trigger lazy IO.
"""

from app.models.pet import Pet


def equipped_outfit(entity: object) -> object | None:
    """Equipped outfit, or None when not loaded/equipped; reads via __dict__ to avoid lazy IO."""
    return entity.__dict__.get("outfit")


def equipped_pet(entity: object) -> Pet | None:
    """Equipped pet, or None when not loaded/equipped; reads via __dict__ to avoid lazy IO."""
    return entity.__dict__.get("pet")
