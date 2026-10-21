"""Named starter residents used by the guided objective rewards."""

import json
from functools import lru_cache
from typing import Any

from app.utils.static_data import DATA_DIR


@lru_cache(maxsize=1)
def starter_residents() -> dict[str, dict[str, Any]]:
    """Resident profiles keyed by their full display name (case-insensitive)."""
    path = DATA_DIR / "dwellers/starter_residents.json"
    profiles = json.loads(path.read_text(encoding="utf-8"))
    return {str(name).strip().lower(): profile for name, profile in profiles.items()}


def get_starter_resident(name: str) -> dict[str, Any] | None:
    return starter_residents().get(name.strip().lower())
