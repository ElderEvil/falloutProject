"""Outfit protection against vault hazards.

Pure helpers over an already-loaded outfit: no session, no lazy IO. Radiation
resistance keeps its own module (``services/radiation_service.py``) because it
also owns the radiation tick, the RadAway rules, and the type/name fallback
table for outfits that predate the explicit column.
"""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.models.outfit import Outfit


def outfit_fire_resist(outfit: "Outfit | None") -> float:
    """Share of fire damage an equipped outfit removes."""
    if outfit is None:
        return 0.0
    return float(getattr(outfit, "fire_resist", 0.0) or 0.0)
