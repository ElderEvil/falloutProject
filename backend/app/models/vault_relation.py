"""Per-pair diplomatic standing between two vaults: the Envoy Terminal's ledger row."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy import Index
from sqlmodel import Field

from app.core.enums import VaultRelationStatus
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.utils.types import UTCDateTime


class VaultRelation(BaseUUIDModel, TimeStampMixin, table=True):
    """One row per vault pair, keyed by the ordered pair (``vault_a_id`` is the lower UUID).

    Status is VARCHAR-backed so the StrEnum needs no PostgreSQL type and no enum migration.
    ``locked_until`` is the wall-clock refusal lock; ``met_at`` records first contact.
    """

    __tablename__ = "vaultrelation"

    __table_args__ = (
        sa.UniqueConstraint("vault_a_id", "vault_b_id", name="uq_vault_relation_pair"),
        Index("ix_vaultrelation_status_locked_until", "status", "locked_until"),
    )

    vault_a_id: UUID = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    vault_b_id: UUID = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    status: VaultRelationStatus = Field(
        default=VaultRelationStatus.UNMET,
        sa_column=sa.Column(sa.String(16), nullable=False, default=VaultRelationStatus.UNMET.value),
    )
    standing: int = Field(default=0, ge=-100, le=100)
    met_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
    locked_until: datetime | None = Field(default=None, sa_type=UTCDateTime)
