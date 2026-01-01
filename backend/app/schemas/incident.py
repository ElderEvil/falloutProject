"""Incident schemas for API responses."""

from datetime import datetime

from pydantic import UUID4

from app.models.incident import IncidentStatus, IncidentType


class IncidentRead:
    """Schema for reading incident data."""

    id: UUID4
    vault_id: UUID4
    room_id: UUID4
    type: IncidentType
    status: IncidentStatus
    difficulty: int
    start_time: datetime
    end_time: datetime | None
    duration: int
    damage_dealt: int
    enemies_defeated: int
    loot: dict | None
    rooms_affected: list[str]
    spread_count: int
    created_at: datetime
    updated_at: datetime


class IncidentResolveRequest:
    """Request to manually resolve an incident."""

    success: bool = True


class IncidentResolveResponse:
    """Response after resolving an incident."""

    message: str
    incident_id: str
    loot: dict | None
    caps_earned: int
    items_earned: list[dict]
