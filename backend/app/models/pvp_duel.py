"""Cross-vault exhibition duels: one frozen snapshot per side, resolved on accept."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.enums import PvpDuelStatus
from app.models.base import BaseUUIDModel
from app.utils.time import utcnow
from app.utils.types import UTCDateTime


class PvpDuel(BaseUUIDModel, table=True):
    """A posted challenge; both parties are frozen as snapshots before settlement."""

    __tablename__ = "pvpduel"

    __table_args__ = (Index("ix_pvpduel_status_expires_at", "status", "expires_at"),)

    challenger_vault_id: UUID = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    defender_vault_id: UUID | None = Field(default=None, foreign_key="vault.id", ondelete="CASCADE")
    # Status is VARCHAR-backed so the StrEnum needs no PostgreSQL type (and no enum migration).
    status: PvpDuelStatus = Field(
        default=PvpDuelStatus.OPEN,
        sa_column=sa.Column(sa.String(20), nullable=False, default=PvpDuelStatus.OPEN.value),
    )
    challenger_snapshot: dict[str, Any] = Field(sa_column=sa.Column(JSONB, nullable=False))
    defender_snapshot: dict[str, Any] | None = Field(default=None, sa_column=sa.Column(JSONB, nullable=True))
    outcome: str | None = Field(default=None, max_length=20)
    journal: list[dict[str, Any]] | None = Field(default=None, sa_column=sa.Column(JSONB, nullable=True))
    created_at: datetime = Field(sa_type=UTCDateTime, default_factory=utcnow)
    accepted_at: datetime | None = Field(sa_type=UTCDateTime, default=None)
    expires_at: datetime = Field(sa_type=UTCDateTime)
