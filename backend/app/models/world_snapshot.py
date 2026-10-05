"""Persisted generated world snapshot (recipe + terrain + slots in one row).

One row per (world_id, generator_version): a generated snapshot is written explicitly
once and read back; requests never regenerate it. Terrain and slots live in JSONB
columns (the repo's existing JSON-column pattern) alongside the recipe fingerprint and
a snapshot checksum, so deployment needs no filesystem artifacts.
"""

from datetime import datetime

from sqlalchemy import Column, Index, UniqueConstraint, text
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
    # Fixed public anchors baked into the recipe.
    anchors: list[dict] = Field(default_factory=list, sa_column=Column(JSONB, nullable=False))


class WorldSnapshot(BaseUUIDModel, WorldSnapshotBase, TimeStampMixin, table=True):
    """The backend-owned generated world; the map renders this, not frontend geography.

    ``is_active`` is the explicit one-shared-world selection: a partial unique index on
    ``world_id`` where the flag is set guarantees at most one active snapshot per world,
    so generating or storing a candidate never silently activates it.
    """

    __tablename__ = "worldsnapshot"

    is_active: bool = Field(default=False, index=True)
    activated_at: datetime | None = Field(default=None)

    __table_args__ = (
        UniqueConstraint("world_id", "generator_version", name="uq_worldsnapshot_world_version"),
        Index(
            "uq_worldsnapshot_active_world",
            "world_id",
            unique=True,
            postgresql_where=text("is_active"),
            sqlite_where=text("is_active"),
        ),
    )
