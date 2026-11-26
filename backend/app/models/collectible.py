"""Per-vault bobblehead claim.

The claim is durable: deleting the finder nulls ``finder_dweller_id`` instead of removing the
row, so death, deletion, revival or recycling can never reopen a place. The finder's bonus is
stored separately on the dweller, is cleared when that dweller stops being itself, and the claim
marks itself revoked so readback stops promising a bonus that is gone.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.utils.types import UTCDateTime


class VaultCollectible(BaseUUIDModel, TimeStampMixin, table=True):
    """One claimed bobblehead per vault; the unique pair is the once-per-vault rule."""

    __tablename__ = "vaultcollectible"

    vault_id: UUID = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    collectible_key: str = Field(max_length=32, index=True)
    finder_dweller_id: UUID | None = Field(default=None, foreign_key="dweller.id", ondelete="SET NULL")
    location_id: UUID | None = Field(default=None, foreign_key="worldlocation.id", ondelete="SET NULL")
    found_at: datetime = Field(sa_type=UTCDateTime)
    # The vault keeps a claim forever, but the finder's bonus can be cleared (death, recycling).
    # Readback must not promise a bonus the dweller no longer holds, so the claim records it.
    bonus_live: bool = Field(
        default=True,
        sa_column=sa.Column(sa.Boolean, nullable=False, server_default=sa.true()),
    )

    __table_args__ = (sa.UniqueConstraint("vault_id", "collectible_key", name="uq_vault_collectible_key"),)
