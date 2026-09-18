"""Central accessor for a dweller's equipped outfit.

Callers must eager-load ``outfit``; a missing relationship means "no outfit"
and must never trigger lazy IO.
"""


def equipped_outfit(entity: object) -> object | None:
    """The entity's equipped outfit, or None when not loaded/equipped.

    Reads via ``__dict__`` so a missing relationship never triggers lazy IO.
    """
    return entity.__dict__.get("outfit")
