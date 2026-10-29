"""Schemas for the backend-owned world snapshot (public base world)."""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class RoadEdgeRead(SQLModel):
    """One smoothed road polyline; ``class`` stays the wire name for the renderer."""

    road_class: str = Field(alias="class")
    points: list[list[float]]


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
    road_edges: list[RoadEdgeRead] = Field(default_factory=list)
    road_anchors: list[dict] = Field(default_factory=list)
    towns: list[dict] = Field(default_factory=list)
    regions: list[dict] = Field(default_factory=list)
    region_map: list[int] = Field(default_factory=list)
    places: list[dict] = Field(default_factory=list)
    validation: dict = Field(default_factory=dict)
