"""Schemas for wasteland location CRUD and map responses."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import UUID4
from sqlmodel import SQLModel

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum


class LocationClearStateRead(SQLModel):
    """Per-point clear state for a clearable map point (issue 772, phase 1).

    Read-only projection of ``VaultLocationState`` clear fields; availability is
    derived from ``now`` at read time and never persisted by this phase.
    """

    clearable: bool
    cleared: bool
    clear_count: int
    tier: int
    time_remaining_seconds: int
    loot_table: str | None = None


class WastelandLocationRead(SQLModel):
    """All row fields for a WastelandLocation, serialized for the API."""

    id: UUID4
    name: str
    normalized_name: str
    type: LocationTypeEnum
    coord_x: float
    coord_y: float
    description: str | None
    group_key: str | None = None
    vault_id: UUID4
    exploration_id: UUID4 | None
    created_at: datetime | None
    clear_state: LocationClearStateRead | None = None


class PlaceGroupRead(SQLModel):
    """A wasteland site-type archetype from the group catalog."""

    key: str
    label: str
    icon: str
    risk: str
    description: str
    clearable: bool = False
    reclear_hours: int | None = None
    loot_table: str | None = None
    base_difficulty: int | None = None


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


class DiscoveryRoutePoint(SQLModel):
    """One persisted discovery event, projected into map coordinates."""

    location_id: UUID4
    coord_x: float
    coord_y: float
    timestamp: str


class DiscoveryRouteRead(SQLModel):
    """Ordered discovery trail for a single exploration."""

    exploration_id: UUID4
    points: list[DiscoveryRoutePoint]


class VaultMapResponse(SQLModel):
    """Full world-map payload: persisted locations + computed vault markers."""

    locations: list[WastelandLocationWithDwellers]
    vault_markers: list[VaultMarkerRead]
    discovery_routes: list[DiscoveryRouteRead] = []
    place_groups: list[PlaceGroupRead] = []
