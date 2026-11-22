"""Schemas for wasteland location CRUD and map responses."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from sqlmodel import SQLModel

from app.core.enums import DwellerLocationRelationEnum, LocationTypeEnum
from app.utils.serialize_types import OptionalUTCDateTimeJSON


class LocationLootEntryRead(SQLModel):
    """One declared loot roll for the pre-dispatch preview.

    Every entry rolls on a win, so the preview promises no odds. ``signature`` marks the table's
    identity entry — the material the archetype stands for. Proportional haul loss trims from the
    tail, so the signature survives a partial loss and the last entries do not.
    """

    item_type: str
    rarity: str
    junk_types: list[str] = []
    weapon_types: list[str] = []
    signature: bool = False


class LocationClearStateRead(SQLModel):
    """Read-only projection of VaultLocationState clear fields; availability is
    derived from now at read time, never persisted.
    """

    clearable: bool
    cleared: bool
    clear_count: int
    tier: int
    time_remaining_seconds: int
    loot_table: str | None = None
    xp_per_survivor: int = 0
    loot_preview: list[LocationLootEntryRead] = []


class WastelandLocationRead(SQLModel):
    """All row fields for a WastelandLocation, serialized for the API."""

    id: UUID
    name: str
    normalized_name: str
    type: LocationTypeEnum
    coord_x: float
    coord_y: float
    description: str | None
    group_key: str | None = None
    vault_id: UUID
    exploration_id: UUID | None
    created_at: OptionalUTCDateTimeJSON
    clear_state: LocationClearStateRead | None = None
    # What the map offers here: a clearable site, a one-time salvage point, or nothing.
    action: Literal["clear", "salvage", "none"] = "none"


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
    xp_reward: int | None = None


class DwellerRef(SQLModel):
    """Lightweight dweller reference for a location's dweller list."""

    dweller_id: UUID
    first_name: str
    last_name: str | None
    relation: DwellerLocationRelationEnum
    is_unlocked: bool = False


class WastelandLocationWithDwellers(WastelandLocationRead):
    """A location row with its linked dweller references."""

    dwellers: list[DwellerRef]
    is_unlocked: bool = False
    dispatch_in_progress: bool = False


class VaultMarkerRead(SQLModel):
    """A computed vault marker for the world map (never persisted)."""

    name: str
    coord_x: float
    coord_y: float
    type: Literal["vault"]
    description: str


class PlayerVaultMarkerRead(SQLModel):
    """A real player vault placed on the shared atlas, discoverable by other users."""

    vault_id: UUID
    number: int
    coord_x: float
    coord_y: float
    is_mine: bool = False


class DiscoveryRoutePoint(SQLModel):
    """One journey point in map coordinates; location_id is None for spatial-run
    trail points (legacy runs contribute discovery events with a location).
    """

    location_id: UUID | None = None
    coord_x: float
    coord_y: float
    timestamp: str


class DiscoveryRouteRead(SQLModel):
    """Ordered discovery trail for one exploration. All routes are returned (the
    fog corridor derives from every route); only is_active ones draw a trail.
    """

    exploration_id: UUID
    points: list[DiscoveryRoutePoint]
    is_active: bool


class ExpeditionSiteMarkerRead(SQLModel):
    """Interactive expedition site with per-vault state. block_reason mirrors the
    anti-farm gate: "open" while a run is in progress, "cooldown" during the
    post-run window, None when ready.
    """

    id: str
    name: str
    flavor: str
    coord_x: float
    coord_y: float
    min_dweller_level: int
    room_total: int
    cleared: bool
    cooldown_remaining_seconds: int
    block_reason: Literal["open", "cooldown"] | None = None
    # Journey identity for temporary encounter offers; None for catalog/legacy markers.
    exploration_id: UUID | None = None


class VaultMapResponse(SQLModel):
    """Full world-map payload: persisted locations + computed vault markers."""

    locations: list[WastelandLocationWithDwellers]
    vault_markers: list[VaultMarkerRead]
    player_vaults: list[PlayerVaultMarkerRead] = []
    discovery_routes: list[DiscoveryRouteRead] = []
    place_groups: list[PlaceGroupRead] = []
    expedition_sites: list[ExpeditionSiteMarkerRead] = []
