"""Server-wide co-op world events.

One WorldEvent row is the shared goal every vault contributes to; WorldEventParticipation
records each vault's contribution and one-time reward claim. At most one event may be ACTIVE
at a time (partial unique index), enforced by the database rather than the application.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Index, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.core.enums import WorldEventStatus
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.utils.types import UTCDateTime


class WorldEventBase(SQLModel):
    """Shared fields for a co-op world event."""

    kind: str = Field(max_length=50, index=True)
    title: str = Field(max_length=120)
    description: str = Field(max_length=500)
    target_amount: int = Field(ge=1)
    progress_amount: int = Field(default=0, ge=0)
    personal_min: int = Field(ge=0)
    reward: list[dict] = Field(default_factory=list, sa_column=sa.Column(JSONB, nullable=False))
    starts_at: datetime = Field(sa_type=UTCDateTime)
    ends_at: datetime = Field(sa_type=UTCDateTime)
    status: WorldEventStatus = Field(
        default=WorldEventStatus.SCHEDULED,
        sa_column=sa.Column(
            sa.Enum(WorldEventStatus, name="worldeventstatus"),
            nullable=False,
            default=WorldEventStatus.SCHEDULED,
        ),
    )
    # Set when the end time was pushed back; NULL when the event runs as first scheduled.
    extended_at: datetime | None = Field(sa_type=UTCDateTime, default=None)


class WorldEvent(BaseUUIDModel, WorldEventBase, TimeStampMixin, table=True):
    """The server-wide event every vault contributes to."""

    __tablename__ = "worldevent"

    __table_args__ = (
        Index(
            "uq_world_event_single_active",
            "status",
            unique=True,
            postgresql_where=text("status = 'ACTIVE'"),
        ),
    )


class WorldEventParticipation(BaseUUIDModel, TimeStampMixin, table=True):
    """One vault's contribution to a world event; one row per (event, vault)."""

    __tablename__ = "worldeventparticipation"

    world_event_id: UUID = Field(foreign_key="worldevent.id", index=True, ondelete="CASCADE")
    vault_id: UUID = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    contribution: int = Field(default=0, ge=0)
    # NULL until the vault collects its reward; set once, never cleared.
    reward_claimed_at: datetime | None = Field(sa_type=UTCDateTime, default=None)

    __table_args__ = (UniqueConstraint("world_event_id", "vault_id", name="uq_world_event_participation"),)
