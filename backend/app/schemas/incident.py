"""Incident schemas for API responses."""

from pydantic import UUID4, BaseModel, Field

from app.models.incident import IncidentFamily, IncidentObjective, IncidentStatus, IncidentType


class IncidentProgress(BaseModel):
    current: int
    target: int
    label: str


class IncidentRisk(BaseModel):
    kind: str
    rooms_affected: int


class IncidentResponse(BaseModel):
    label: str


class IncidentEventRead(BaseModel):
    id: str
    kind: str
    message: str
    data: dict | None
    created_at: str


class IncidentRead(BaseModel):
    """Full incident details."""

    id: UUID4
    vault_id: UUID4
    room_id: UUID4
    room_name: str | None = None
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
    family: IncidentFamily
    objective: IncidentObjective
    progress: IncidentProgress
    risk: IncidentRisk
    response: IncidentResponse
    events: list[IncidentEventRead]


class IncidentListItem(BaseModel):
    """Summary incident info for list view."""

    id: str
    type: IncidentType
    status: IncidentStatus
    room_id: str
    room_name: str | None = None
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


class IncidentRespondersRequest(BaseModel):
    """Dwellers ordered to defend an active incident."""

    dweller_ids: list[UUID4] = Field(min_length=1, max_length=6)


class IncidentRespondersResponse(BaseModel):
    """Response after assigning defenders to an incident room."""

    incident_id: UUID4
    room_id: UUID4
    assigned_dweller_ids: list[UUID4]


class IncidentRoundResult(BaseModel):
    """Validated outcome of one incident game-loop round."""

    skipped: bool = False
    no_defenders: bool = False
    damage_to_dwellers: float = 0
    damage_to_raiders: float = 0
    dwellers_damaged: int = 0
    dwellers_killed: int = 0
    enemies_defeated: int = 0
    caps_earned: int = 0
