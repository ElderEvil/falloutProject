"""Schemas for the backend-owned world snapshot (public base world)."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field
from sqlmodel import SQLModel

RoadCoordinate = Annotated[float, Field(ge=0, le=100, allow_inf_nan=False)]


class WorldRoadRead(SQLModel):
    """Backend-validated centerline in registry coordinates, including rounded bends."""

    id: str
    kind: Literal["highway", "country", "railroad"]
    points: Annotated[list[tuple[RoadCoordinate, RoadCoordinate]], Field(min_length=2)]


class WorldRoadsRead(SQLModel):
    """Additive cartography; versioning this layer never reseeds the base world."""

    version: int
    base_checksum: str
    checksum: str
    segments: list[WorldRoadRead]


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
    roads: WorldRoadsRead | None = None
