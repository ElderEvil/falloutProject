"""Canonical world-place registry and per-vault fog state.

Phase 1 of the shared places registry (see ``docs/WORLD_MAP_PLAN.md``): the global
``WorldLocation`` authority plus per-vault ``VaultLocationState``. Both are
backfilled from the retired per-vault ``wastelandlocation`` table; the service
layer is rewired onto these in phase 2.
"""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum, PlaceKindEnum
from app.models.base import BaseUUIDModel, TimeStampMixin


class WorldLocationBase(SQLModel):
    """Shared fields for the canonical registry row."""

    name: str = Field(max_length=64)
    normalized_name: str = Field(max_length=64, index=True, unique=True)
    vault_number: int | None = Field(default=None)
    coord_x: float = Field(ge=0, le=100)
    coord_y: float = Field(ge=0, le=100)
    description: str | None = Field(default=None, max_length=255)
    # Site-type archetype key (see data/places/place_groups.json). A data-defined
    # string rather than an enum so new site types need no migration.
    group_key: str | None = Field(default=None, max_length=32, index=True)
    source: str = Field(default="emergent", max_length=16)


class WorldLocation(BaseUUIDModel, WorldLocationBase, TimeStampMixin, table=True):
    """Global canonical place; ``normalized_name`` is the unique merge key.

    Coordinates are name-derived (``schematic_coords`` plus a registry-level
    collision nudge) and therefore stable for every viewer. ``vault_number`` is
    set only for real-vault rows and is uniquely constrained among them.
    """

    __tablename__ = "worldlocation"

    kind: PlaceKindEnum = Field(
        sa_column=sa.Column(sa.Enum(PlaceKindEnum, name="placekind"), nullable=False, default=PlaceKindEnum.PLACE)
    )

    __table_args__ = (
        sa.CheckConstraint("coord_x >= 0 AND coord_x <= 100", name="ck_world_location_coord_x_range"),
        sa.CheckConstraint("coord_y >= 0 AND coord_y <= 100", name="ck_world_location_coord_y_range"),
        sa.CheckConstraint(
            "(kind = 'VAULT' AND vault_number IS NOT NULL) OR (kind = 'PLACE' AND vault_number IS NULL)",
            name="ck_world_location_kind_fields",
        ),
        sa.Index(
            "uq_world_location_vault_number",
            "vault_number",
            unique=True,
            postgresql_where=sa.text("kind = 'VAULT'"),
        ),
    )


class VaultLocationStateBase(SQLModel):
    """Shared fields for a vault's fog entry over a canonical location."""

    type: LocationTypeEnum
    description: str | None = Field(default=None, max_length=255)


class VaultLocationState(BaseUUIDModel, VaultLocationStateBase, TimeStampMixin, table=True):
    """Per-vault visibility state (origin / visited / discovery / home) for a location.

    ``type`` stays per-vault: one vault's origin is another vault's discovery.
    """

    __tablename__ = "vaultlocationstate"

    vault_id: UUID4 = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    location_id: UUID4 = Field(foreign_key="worldlocation.id", index=True, ondelete="CASCADE")
    exploration_id: UUID4 | None = Field(default=None, foreign_key="exploration.id", nullable=True, ondelete="SET NULL")

    # Map-point clear state (issue 772). NULL / 0 is the "never cleared" state;
    # reclear_available_at is cleared_at + the place group's reclear_hours.
    cleared_at: datetime | None = Field(default=None)
    reclear_available_at: datetime | None = Field(default=None)
    clear_count: int = Field(default=0, ge=0, description="Successful clears; drives escalation tier")

    __table_args__ = (sa.UniqueConstraint("vault_id", "location_id", name="uq_vault_location_state"),)

    def is_cleared(self, now: datetime) -> bool:
        """True while the point is cleared and not yet available for re-looting."""
        return self.reclear_available_at is not None and now < self.reclear_available_at

    def time_remaining_seconds(self, now: datetime) -> int:
        """Seconds until the point can be re-looted; 0 when never cleared or already available."""
        if self.reclear_available_at is None:
            return 0
        return max(0, int((self.reclear_available_at - now).total_seconds()))

    def is_dispatchable(self, now: datetime) -> bool:
        """True when the point is not currently cleared.

        Group clearability is the caller's concern (checked against the place
        group before dispatch); this only reflects the per-vault clear window.
        """
        return not self.is_cleared(now)


class DwellerLocationBase(SQLModel):
    """Shared fields for a dweller's link to a world location."""

    relation: DwellerLocationRelationEnum
    is_unlocked: bool = Field(default=False)


class DwellerLocation(BaseUUIDModel, DwellerLocationBase, TimeStampMixin, table=True):
    """Junction linking a dweller to a canonical world location with a relation type."""

    __tablename__ = "dwellerlocation"

    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")
    location_id: UUID4 = Field(foreign_key="worldlocation.id", index=True, ondelete="CASCADE")

    __table_args__ = (
        sa.UniqueConstraint("dweller_id", "location_id", "relation", name="uq_dweller_location_relation"),
    )
