"""One structured filing between two vaults: kind, terms, expiry and answer."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.core.enums import DiplomaticFilingKind, DiplomaticFilingStatus
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.utils.types import UTCDateTime


class DiplomaticFiling(BaseUUIDModel, TimeStampMixin, table=True):
    """An offer that waits for an answer until it expires; no free text, only structured terms."""

    __tablename__ = "diplomaticfiling"

    __table_args__ = (
        Index("ix_diplomaticfiling_pair_kind_status", "from_vault_id", "to_vault_id", "kind", "status"),
        Index("ix_diplomaticfiling_status_expires_at", "status", "expires_at"),
    )

    from_vault_id: UUID = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    to_vault_id: UUID = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    kind: DiplomaticFilingKind = Field(sa_column=sa.Column(sa.String(16), nullable=False))
    terms: dict[str, Any] = Field(sa_column=sa.Column(JSONB, nullable=False))
    status: DiplomaticFilingStatus = Field(
        default=DiplomaticFilingStatus.PENDING,
        sa_column=sa.Column(sa.String(16), nullable=False, default=DiplomaticFilingStatus.PENDING.value),
    )
    expires_at: datetime = Field(sa_type=UTCDateTime)
    responded_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
