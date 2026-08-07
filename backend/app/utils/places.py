"""Deterministic world-map place utilities.

Pure functions only: no DB access, no randomness, no time, no I/O. The same
input always yields the same output across calls and processes, so map
markers derived from place names and vault ids are stable and reproducible.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

#: Place origins that should never produce a map marker.
GENERIC_ORIGIN_SKIP: frozenset[str] = frozenset({"", "wasteland", "the wasteland", "unknown"})


def normalize_place_name(name: str) -> str:
    """Normalize a place name for stable matching and deduplication.

    Strips outer whitespace, lowercases, collapses internal whitespace runs
    to a single space, and removes trailing ``.``/``,``/``!`` characters.
    """
    collapsed = " ".join(name.strip().casefold().split())
    return collapsed.rstrip(".,!")


def schematic_coords(normalized_name: str) -> tuple[float, float]:
    """Derive deterministic schematic coordinates for a normalized place name.

    The first four bytes of the sha256 digest of the UTF-8 name are read as
    two big-endian uint16 values; each maps into the 10.0-89.9 band with one
    decimal of resolution.
    """
    digest = hashlib.sha256(normalized_name.encode("utf-8")).digest()
    h1 = int.from_bytes(digest[0:2], "big")
    h2 = int.from_bytes(digest[2:4], "big")
    return (10.0 + (h1 % 800) / 10, 10.0 + (h2 % 800) / 10)


def _spiral_offsets() -> list[tuple[float, float]]:
    """Deterministic 1.5-scaled spiral offsets, up to 16 candidates.

    Two expanding rings; within each ring the four cardinal neighbors are
    tried before the four diagonal neighbors.
    """
    offsets: list[tuple[int, int]] = []
    for ring in (1, 2):
        cardinals = [(ring, 0), (0, ring), (-ring, 0), (0, -ring)]
        diagonals = [(ring, ring), (ring, -ring), (-ring, ring), (-ring, -ring)]
        offsets.extend(cardinals)
        offsets.extend(diagonals)
    return [(dx * 1.5, dy * 1.5) for dx, dy in offsets]


def _clamp_to_grid(coord: float) -> float:
    """Round to one decimal and clamp a coordinate into the 0..100 grid."""
    return min(max(round(coord, 1), 0.0), 100.0)


def collision_nudge(base: tuple[float, float], occupied: set[tuple[float, float]]) -> tuple[float, float]:
    """Return ``base`` if free, else the first free spiral offset.

    Candidates are clamped into the 0..100 grid; when every candidate is
    occupied the clamped ``base`` itself is returned.
    """
    if base not in occupied:
        return base
    for offset in _spiral_offsets():
        candidate = (_clamp_to_grid(base[0] + offset[0]), _clamp_to_grid(base[1] + offset[1]))
        if candidate not in occupied:
            return candidate
    return (_clamp_to_grid(base[0]), _clamp_to_grid(base[1]))


@dataclass(frozen=True)
class VaultSeed:
    """Deterministic seed data for a world-map vault marker."""

    name: str
    coord_x: float
    coord_y: float


def seeded_vault_specs(vault_id: UUID, home_number: int) -> list[VaultSeed]:
    """Generate 3-7 deterministic vault marker specs from a vault UUID.

    Numbers are drawn in the 1-999 range, distinct from each other and from
    ``home_number``, from a chained sha256 stream seeded by the vault id
    (each digest is re-hashed with an appended counter byte for entropy).
    Coordinates come from the schematic hash of the vault name, nudged away
    from every previously seeded marker and from the home-vault origin.
    """
    digest = hashlib.sha256(str(vault_id).encode("utf-8")).digest()
    count = 3 + digest[0] % 5
    specs: list[VaultSeed] = []
    occupied: set[tuple[float, float]] = {(50.0, 50.0)}
    numbers: set[int] = set()
    counter = 0
    while len(specs) < count:
        number = int.from_bytes(digest[:2], "big") % 999 + 1
        digest = hashlib.sha256(digest + bytes([counter])).digest()
        counter += 1
        if number in numbers or number == home_number:
            continue
        numbers.add(number)
        name = f"Vault {number:03}"
        coord = collision_nudge(schematic_coords(normalize_place_name(name)), occupied)
        occupied.add(coord)
        specs.append(VaultSeed(name=name, coord_x=coord[0], coord_y=coord[1]))
    return specs
