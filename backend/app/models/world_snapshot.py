"""Persisted generated world snapshot (recipe + terrain + slots in one row).

One row per (world_id, generator_version): a generated snapshot is written explicitly
once and read back; requests never regenerate it. Terrain and slots live in JSONB
columns (the repo's existing JSON-column pattern) alongside the recipe fingerprint and
a snapshot checksum, so deployment needs no filesystem artifacts.
"""

from sqlalchemy import Column, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class WorldSnapshotBase(SQLModel):
    """Recipe identity and generated payload for a single world version."""

    world_id: str = Field(max_length=32, index=True)
    generator_version: int = Field(ge=1)
    seed: str = Field(max_length=64)
    # Full generation config, as stored JSON, so the recipe is self-contained.
    config: dict = Field(default_factory=dict, sa_column=Column(JSONB, nullable=False))
    # Stable recipe fingerprint (hash of version/seed/config/anchors).
    recipe_fingerprint: str = Field(max_length=64, index=True)
    # Checksum of the canonical snapshot payload (terrain + slots).
    snapshot_checksum: str = Field(max_length=64)
    # Generated terrain cells (row-major) and land-safe slots.
    terrain: list[str] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    slots: list[dict] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))
    # Display-only road mask: flat, sorted tile indices over the terrain grid.
    # server_default '[]' keeps pre-roads rows readable (legitimate empty mask).
    roads: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    # Display-only river mask: same convention, never carved into terrain.
    # server_default '[]' keeps pre-rivers rows readable (legitimate empty mask).
    rivers: list[int] = Field(
        default_factory=list,
        sa_column=Column(JSONB, nullable=False, server_default="[]"),
    )
    # Fixed public anchors baked into the recipe.
    anchors: list[dict] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))


class WorldSnapshot(BaseUUIDModel, WorldSnapshotBase, TimeStampMixin, table=True):
    """The backend-owned generated world; the map renders this, not frontend geography."""

    __tablename__ = "worldsnapshot"

    __table_args__ = (UniqueConstraint("world_id", "generator_version", name="uq_worldsnapshot_world_version"),)
