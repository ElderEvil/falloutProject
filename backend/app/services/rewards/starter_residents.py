"""Named starter residents used by the guided objective rewards."""

import json
from functools import lru_cache
from typing import Any

from app.core.enums import GenderEnum
from app.utils.static_data import DATA_DIR


@lru_cache(maxsize=1)
def _starter_resident_variants() -> dict[str, dict[str, Any]]:
    """Alternate profiles keyed by the standard reward they can replace."""
    path = DATA_DIR / "dwellers/starter_resident_variants.json"
    return json.loads(path.read_text(encoding="utf-8"))


def _display_name(profile: dict[str, Any]) -> str:
    return f"{profile['first_name']} {profile['last_name']}"


@lru_cache(maxsize=1)
def starter_residents() -> dict[str, dict[str, Any]]:
    """Resident profiles keyed by their full display name (case-insensitive)."""
    path = DATA_DIR / "dwellers/starter_residents.json"
    profiles = json.loads(path.read_text(encoding="utf-8"))
    for standard_name, variant in _starter_resident_variants().items():
        base = profiles[standard_name]
        profiles[_display_name(variant)] = {
            **base,
            **variant,
            "visual_attributes": base["visual_attributes"] | variant["visual_attributes"],
        }
    return {name.strip().lower(): profile for name, profile in profiles.items()}


def starter_reward_overrides(majority: GenderEnum | None) -> dict[str, str]:
    """Keep the standard milestones and swap only the authored recruit rewards."""
    if majority is None:
        return {}
    return {
        f"dweller:{standard_name}": f"dweller:{_display_name(variant)}"
        for standard_name, variant in _starter_resident_variants().items()
        if variant["gender"] == majority
    }


def get_starter_resident(name: str) -> dict[str, Any] | None:
    return starter_residents().get(name.strip().lower())
