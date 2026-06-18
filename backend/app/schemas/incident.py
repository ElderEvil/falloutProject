"""Incident schemas for API responses."""

from pydantic import UUID4, BaseModel

from app.models.incident import IncidentStatus, IncidentType


class IncidentRead(BaseModel):
    """Full incident details."""

    id: UUID4
    vault_id: UUID4
    room_id: UUID4
    type: IncidentType
    status: IncidentStatus
    difficulty: int
    start_time: str
    end_time: str | None
    elapsed_time: int
    duration: int
    damage_dealt: int
    enemies_defeated: int
    rooms_affected: list[str]
    spread_count: int
    loot: dict | None


class IncidentListItem(BaseModel):
    """Summary incident info for list view."""

    id: str
    type: IncidentType
    status: IncidentStatus
    room_id: str
    difficulty: int
    start_time: str
    elapsed_time: int
    damage_dealt: int
    enemies_defeated: int


class IncidentListResponse(BaseModel):
    """List of active incidents in a vault."""

    vault_id: str
    incident_count: int
    incidents: list[IncidentListItem]


class PauseResumeResponse(BaseModel):
    """Response for pause/resume vault operations."""

    message: str
    vault_id: str
    is_paused: bool
    paused_at: str | None = None
    resumed_at: str | None = None


class IncidentSpawnResponse(BaseModel):
    """Response after spawning a debug incident."""

    message: str
    vault_id: str
    incident_id: str
    type: str
    room_id: str
    difficulty: int


class DeleteIncidentsResponse(BaseModel):
    """Response after deleting incidents."""

    message: str
    vault_id: str
    deleted_count: int


class ManualTickResponse(BaseModel):
    """Response after triggering a manual game tick."""

    message: str
    tick_duration_ms: int = 0
    resources_updated: bool = False
    incidents_processed: int = 0
    training_completed: int = 0
    breeding_processed: int = 0


class IncidentResolveResponse(BaseModel):
    """Response after resolving an incident."""

    message: str
    incident_id: str
    loot: dict | None
    caps_earned: int
    items_earned: list[dict]
