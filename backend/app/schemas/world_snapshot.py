"""Schemas for the backend-owned world snapshot (public base world)."""

from __future__ import annotations

from sqlmodel import SQLModel


class WorldSlotRead(SQLModel):
    """One land-safe slot: stable index + registry coordinate."""

    slot_index: int
    coord_x: float
    coord_y: float


class WorldSnapshotRead(SQLModel):
    """Public base-world snapshot the production map renders.

    Terrain is row-major over ``width x height`` tiles. Private ownership,
    discoveries, and expedition state are never part of this payload.
    """

    world_id: str
    generator_version: int
    recipe_fingerprint: str
    snapshot_checksum: str
    width: int
    height: int
    terrain: list[str]
    slots: list[WorldSlotRead]
    roads: list[int]
    rivers: list[int]
