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
        result = await db_session.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_active_by_vault(db_session: AsyncSession, vault_id: UUID4) -> list[Incident]:
        """Get all active incidents for a vault."""
        query = select(Incident).where(
            (Incident.vault_id == vault_id) & (Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.SPREADING]))
        )
        result = await db_session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_by_room(db_session: AsyncSession, room_id: UUID4) -> list[Incident]:
        """Get active incidents in a specific room."""
        query = select(Incident).where(
            (Incident.room_id == room_id) & (Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.SPREADING]))
        )
        result = await db_session.execute(query)
        return list(result.scalars().all())

    @staticmethod
    async def get_active_incident_types_in_vault(db_session: AsyncSession, vault_id: UUID4) -> set[IncidentType]:
        """Get set of unique active incident types in a vault."""
        query = select(Incident.type).where(
            (Incident.vault_id == vault_id) & (Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.SPREADING]))
        )
        result = await db_session.execute(query)
        return set(result.scalars().all())

    @staticmethod
    async def get_rooms_with_active_incidents(db_session: AsyncSession, vault_id: UUID4) -> set[UUID4]:
        """Get set of room IDs that have active incidents."""
        query = select(Incident.room_id).where(
            (Incident.vault_id == vault_id) & (Incident.status.in_([IncidentStatus.ACTIVE, IncidentStatus.SPREADING]))
        )
        result = await db_session.execute(query)
        return set(result.scalars().all())

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
        result = await db_session.execute(query)
        incidents = list(result.scalars().all())

        # Filter for incidents that should spread
        return [inc for inc in incidents if inc.should_spread()]

    @staticmethod
    async def remove(db_session: AsyncSession, incident_id: UUID4) -> bool:
        """Delete an incident."""
        incident = await CRUDIncident.get(db_session, incident_id)
        if incident:
            await db_session.delete(incident)
            await db_session.commit()
            return True
        return False

    @staticmethod
    async def remove_all_by_vault(db_session: AsyncSession, vault_id: UUID4) -> int:
        """Delete all incidents for a vault."""
        query = select(Incident).where(Incident.vault_id == vault_id)
        result = await db_session.execute(query)
        incidents = list(result.scalars().all())
        count = len(incidents)
        for incident in incidents:
            await db_session.delete(incident)
        await db_session.commit()
        return count


# Global instance
incident_crud = CRUDIncident()
