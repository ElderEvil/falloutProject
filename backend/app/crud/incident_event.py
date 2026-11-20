"""CRUD for incident journal entries, read as the vault's narration stream."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import and_, func
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
        # The latest row per incident in SQL: a long absence would otherwise load every
        # journal row in the vault to return at most ``limit`` of them.
        latest_per_incident = (
            select(
                col(IncidentEvent.incident_id).label("incident_id"),
                func.max(col(IncidentEvent.created_at)).label("latest"),
            )
            .join(Incident, col(Incident.id) == col(IncidentEvent.incident_id))
            .where(col(Incident.vault_id) == vault_id, col(IncidentEvent.created_at) > since)
            .group_by(col(IncidentEvent.incident_id))
            .subquery()
        )
        query = (
            select(IncidentEvent)
            .join(
                latest_per_incident,
                and_(
                    col(IncidentEvent.incident_id) == latest_per_incident.c.incident_id,
                    col(IncidentEvent.created_at) == latest_per_incident.c.latest,
                ),
            )
            .order_by(col(IncidentEvent.created_at).desc())
            .limit(limit)
        )
        return list((await db.exec(query)).all())


incident_event = CRUDIncidentEvent(IncidentEvent)
