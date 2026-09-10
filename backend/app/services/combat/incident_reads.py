"""Read-side incident queries: UI contract assembly and vault-scoped fetch."""

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.incident import incident_crud
from app.models.incident import Incident, IncidentType, get_incident_definition
from app.schemas.incident import (
    IncidentEventRead,
    IncidentProgress,
    IncidentRead,
    IncidentResponse,
    IncidentRisk,
)
from app.utils.exceptions import AccessDeniedException, ResourceNotFoundException


async def get_incident_read(db_session: AsyncSession, incident: Incident, room_name: str | None) -> IncidentRead:
    """Build the stable, type-aware incident contract consumed by the UI."""
    definition = get_incident_definition(incident.type)
    if incident.type == IncidentType.FIRE:
        progress = IncidentProgress(
            current=min(100, int(incident.combat_progress * 100)), target=100, label=definition.progress_label
        )
    else:
        progress = IncidentProgress(
            current=incident.enemies_defeated,
            target=incident.difficulty * 2,
            label=definition.progress_label,
        )
    events = [
        IncidentEventRead(id=str(event.id), kind=event.kind, message=event.message, data=event.data)
        for event in reversed(await incident_crud.get_recent_events(db_session, incident.id))
    ]
    return IncidentRead(
        id=incident.id,
        vault_id=incident.vault_id,
        room_id=incident.room_id,
        room_name=room_name,
        type=incident.type,
        status=incident.status,
        difficulty=incident.difficulty,
        start_time=incident.start_time.isoformat(),
        end_time=incident.end_time.isoformat() if incident.end_time else None,
        elapsed_time=incident.elapsed_time(),
        duration=incident.duration,
        damage_dealt=incident.damage_dealt,
        enemies_defeated=incident.enemies_defeated,
        rooms_affected=incident.rooms_affected,
        spread_count=incident.spread_count,
        loot=incident.loot,
        family=definition.family,
        objective=definition.objective,
        progress=progress,
        risk=IncidentRisk(kind=definition.risk_kind, rooms_affected=len(incident.rooms_affected)),
        response=IncidentResponse(label=definition.response_label),
        events=events,
    )


async def get_incident_for_vault(db_session: AsyncSession, incident_id: UUID4, vault_id: UUID4) -> Incident:
    incident = await incident_crud.get(db_session, incident_id)
    if not incident:
        raise ResourceNotFoundException(Incident, incident_id)
    if incident.vault_id != vault_id:
        raise AccessDeniedException("Incident does not belong to this vault")
    return incident
