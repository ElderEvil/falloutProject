"""Wasteland location models for the world map."""

from enum import StrEnum

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class LocationTypeEnum(StrEnum):
    """Type of wasteland location — row-level classification."""

    ORIGIN = "origin"
    VISITED = "visited"
    DISCOVERY = "discovery"
    HOME_VAULT = "home_vault"


class DwellerLocationRelationEnum(StrEnum):
    """How a dweller relates to a wasteland location."""

    ORIGIN = "origin"
    VISITED = "visited"


class WastelandLocationBase(SQLModel):
    """Shared fields for WastelandLocation."""

    name: str = Field(max_length=64)
    normalized_name: str = Field(max_length=64, index=True)
    type: LocationTypeEnum
    coord_x: float = Field(ge=0, le=100)
    coord_y: float = Field(ge=0, le=100)
    description: str | None = Field(default=None, max_length=255)


class WastelandLocation(BaseUUIDModel, WastelandLocationBase, TimeStampMixin, table=True):
    """A location on the wasteland world map, scoped to a vault."""

    __tablename__ = "wastelandlocation"

    vault_id: UUID4 = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    exploration_id: UUID4 | None = Field(default=None, foreign_key="exploration.id", nullable=True, ondelete="SET NULL")

    __table_args__ = (
        sa.UniqueConstraint("vault_id", "normalized_name", name="uq_wasteland_location_vault_name"),
        sa.CheckConstraint("coord_x >= 0 AND coord_x <= 100", name="ck_wasteland_location_coord_x_range"),
        sa.CheckConstraint("coord_y >= 0 AND coord_y <= 100", name="ck_wasteland_location_coord_y_range"),
        sa.UniqueConstraint("vault_id", "coord_x", "coord_y", name="uq_wasteland_location_vault_coords"),
    )


class DwellerLocationBase(SQLModel):
    """Shared fields for DwellerLocation."""

    relation: DwellerLocationRelationEnum


class DwellerLocation(BaseUUIDModel, DwellerLocationBase, TimeStampMixin, table=True):
    """Junction linking a dweller to a wasteland location with a relation type."""

    __tablename__ = "dwellerlocation"

    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")
    location_id: UUID4 = Field(foreign_key="wastelandlocation.id", index=True, ondelete="CASCADE")

    __table_args__ = (
        sa.UniqueConstraint("dweller_id", "location_id", "relation", name="uq_dweller_location_relation"),
    )
