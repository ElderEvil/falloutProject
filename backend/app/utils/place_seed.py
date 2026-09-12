"""Seed-roster loading for the canonical world-place registry.

Layer-safe home (no DB, no services) for the JSON roster so both the seed
service and vault-number reservation can share it without import cycles.
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from app.utils.places import normalize_place_name

SEED_FILE = Path(__file__).parent.parent / "data" / "places" / "seed_places.json"


@lru_cache(maxsize=1)
def load_seed_entries() -> list[dict[str, Any]]:
    """Load and validate the seed roster (cached)."""
    with SEED_FILE.open(encoding="utf-8") as f:
        entries = json.load(f)
    seen: set[str] = set()
    for entry in entries:
        normalized = normalize_place_name(entry["name"])
        if normalized in seen:
            raise ValueError(f"Duplicate seed place {entry['name']!r}")
        seen.add(normalized)
    return entries


@lru_cache(maxsize=1)
def get_seeded_vault_numbers() -> frozenset[int]:
    """Vault numbers claimed by seeded NPC signals; reserved at vault creation."""
    return frozenset(int(entry["vault_number"]) for entry in load_seed_entries() if entry.get("kind") == "vault")
