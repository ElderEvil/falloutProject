"""SSE event schema for real-time incident updates."""

from pydantic import BaseModel

from app.models.incident import IncidentStatus, IncidentType


class IncidentSseEvent(BaseModel):
    """Payload for SSE incident events published by incident_service.

    Represents a real-time incident state change (spawned, spreading, resolved)
    pushed to connected clients via Server-Sent Events.
    """

    event_id: str
    type: str
    incident_id: str
    vault_id: str
    incident_type: IncidentType
    status: IncidentStatus
    room_id: str | None = None
    room_name: str | None = None
    difficulty: int
    success: bool | None = None
