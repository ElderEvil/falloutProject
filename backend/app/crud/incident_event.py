"""CRUD for incident journal entries, read as the vault's narration stream."""

from datetime import datetime
from uuid import UUID

from sqlmodel import col, select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.base import CRUDBase
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent


class CRUDIncidentEvent(CRUDBase[IncidentEvent, IncidentEvent, IncidentEvent]):
    async def list_latest_per_incident_since(
        self, db: AsyncSession, *, vault_id: UUID, since: datetime, limit: int
    ) -> list[IncidentEvent]:
        """One entry per incident touched since ``since``, newest incidents first.

        A single fire writes several journal rows; the dweller should hear about the fire
        once, so only the latest row per incident is returned.
        """
        query = (
            select(IncidentEvent)
            .join(Incident, col(Incident.id) == col(IncidentEvent.incident_id))
            .where(col(Incident.vault_id) == vault_id, col(IncidentEvent.created_at) > since)
            .order_by(col(IncidentEvent.created_at).desc())
        )
        events = (await db.exec(query)).all()
        latest: dict[UUID, IncidentEvent] = {}
        for event in events:
            latest.setdefault(event.incident_id, event)
        return list(latest.values())[:limit]


incident_event = CRUDIncidentEvent(IncidentEvent)
