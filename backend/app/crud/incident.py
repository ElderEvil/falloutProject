"""CRUD operations for Incident model."""

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.incident import Incident, IncidentStatus, IncidentType


class CRUDIncident:
    """CRUD operations for incident management."""

    @staticmethod
    async def create(  # noqa: PLR0913
        db_session: AsyncSession,
        *,
        vault_id: UUID4,
        room_id: UUID4,
        incident_type: IncidentType,
        difficulty: int,
        duration: int = 60,
    ) -> Incident:
        """Create a new incident."""
        incident = Incident(
            vault_id=vault_id,
            room_id=room_id,
            type=incident_type,
            difficulty=difficulty,
            duration=duration,
            rooms_affected=[str(room_id)],
        )
        db_session.add(incident)
        await db_session.commit()
        await db_session.refresh(incident)
        return incident

    @staticmethod
    async def get(db_session: AsyncSession, incident_id: UUID4) -> Incident | None:
        """Get incident by ID."""
        query = select(Incident).where(Incident.id == incident_id)
        result = await db_session.exec(query)
        return result.first()

    @staticmethod
    async def get_active_by_vault(db_session: AsyncSession, vault_id: UUID4) -> list[Incident]:
        """Get all active incidents for a vault."""
        query = select(Incident).where(
            (Incident.vault_id == vault_id) & (Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.SPREADING]))
        )
        result = await db_session.exec(query)
        return list(result.all())

    @staticmethod
    async def get_by_room(db_session: AsyncSession, room_id: UUID4) -> list[Incident]:
        """Get active incidents in a specific room."""
        query = select(Incident).where(
            (Incident.room_id == room_id) & (Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.SPREADING]))
        )
        result = await db_session.exec(query)
        return list(result.all())

    @staticmethod
    async def resolve(db_session: AsyncSession, incident_id: UUID4, success: bool = True) -> Incident:  # noqa: FBT001, FBT002
        """Resolve an incident."""
        incident = await CRUDIncident.get(db_session, incident_id)
        if incident:
            incident.resolve(success=success)
            db_session.add(incident)
            await db_session.commit()
            await db_session.refresh(incident)
        return incident

    @staticmethod
    async def spread_to_room(db_session: AsyncSession, incident_id: UUID4, new_room_id: UUID4) -> Incident:
        """Mark incident as spreading to a new room."""
        incident = await CRUDIncident.get(db_session, incident_id)
        if incident:
            incident.spread_to_room(str(new_room_id))
            db_session.add(incident)
            await db_session.commit()
            await db_session.refresh(incident)
        return incident

    @staticmethod
    async def get_spreading_incidents(db_session: AsyncSession) -> list[Incident]:
        """Get all incidents that should spread."""
        query = select(Incident).where(Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.SPREADING]))
        result = await db_session.exec(query)
        incidents = list(result.all())

        # Filter for incidents that should spread
        return [inc for inc in incidents if inc.should_spread()]


# Global instance
incident_crud = CRUDIncident()
