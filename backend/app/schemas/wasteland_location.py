"""Schemas for wasteland location CRUD and map responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import UUID4
from sqlmodel import SQLModel

from app.models.wasteland_location import DwellerLocationRelationEnum, LocationTypeEnum


class WastelandLocationRead(SQLModel):
    """All row fields for a WastelandLocation, serialized for the API."""

    id: UUID4
    name: str
    normalized_name: str
    type: LocationTypeEnum
    coord_x: float
    coord_y: float
    description: str | None
    vault_id: UUID4
    exploration_id: UUID4 | None
    created_at: datetime | None


class DwellerRef(SQLModel):
    """Lightweight dweller reference for a location's dweller list."""

    dweller_id: UUID4
    first_name: str
    last_name: str | None
    relation: DwellerLocationRelationEnum
    is_unlocked: bool = False


class WastelandLocationWithDwellers(WastelandLocationRead):
    """A location row with its linked dweller references."""

    dwellers: list[DwellerRef]
    is_unlocked: bool = False


class VaultMarkerRead(SQLModel):
    """A computed vault marker for the world map (never persisted)."""

    name: str
    coord_x: float
    coord_y: float
    type: Literal["vault"]
    description: str


class VaultMapResponse(SQLModel):
    """Full world-map payload: persisted locations + computed vault markers."""

    locations: list[WastelandLocationWithDwellers]
    vault_markers: list[VaultMarkerRead]
