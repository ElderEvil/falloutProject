"""Participation ledger for incidents: who fought, recorded once per incident."""

from pydantic import UUID4
from sqlalchemy import func
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import IncidentType
from app.crud.base import CRUDBase
from app.models.incident import Incident, IncidentParticipant


class CRUDIncidentParticipant(CRUDBase[IncidentParticipant, None, None]):
    async def get_credited_dweller_ids(self, db_session: AsyncSession, incident_id: UUID4) -> set[UUID4]:
        """Dwellers already credited for this incident."""
        query = select(IncidentParticipant.dweller_id).where(IncidentParticipant.incident_id == incident_id)
        return set((await db_session.execute(query)).scalars().all())

    async def record(self, db_session: AsyncSession, incident_id: UUID4, dweller_ids: list[UUID4]) -> list[UUID4]:
        """Credit each dweller for this incident once, returning the newly credited ids.

        Flushes without committing so the rows belong to the caller's transaction:
        a round that fails afterwards leaves no participation behind.
        """
        credited = await self.get_credited_dweller_ids(db_session, incident_id)
        new_ids = [dweller_id for dweller_id in dict.fromkeys(dweller_ids) if dweller_id not in credited]
        if not new_ids:
            return []
        for dweller_id in new_ids:
            db_session.add(IncidentParticipant(incident_id=incident_id, dweller_id=dweller_id))
        await db_session.flush()
        return new_ids

    async def count_incidents(
        self, db_session: AsyncSession, dweller_id: UUID4, incident_types: frozenset[IncidentType]
    ) -> int:
        """How many distinct incidents of these types the dweller has fought."""
        query = (
            select(func.count(func.distinct(IncidentParticipant.incident_id)))
            .select_from(IncidentParticipant)
            .join(Incident, Incident.id == IncidentParticipant.incident_id)
            .where(IncidentParticipant.dweller_id == dweller_id)
            .where(Incident.type.in_(list(incident_types)))
        )
        return (await db_session.execute(query)).scalar_one_or_none() or 0

    async def count_incidents_by_dweller(
        self, db_session: AsyncSession, dweller_ids: list[UUID4], incident_types: frozenset[IncidentType]
    ) -> dict[UUID4, int]:
        """Distinct incidents of these types each dweller has fought, in one grouped query.

        Members with no matching incident are absent from the map; callers default
        to 0. ``dweller_ids`` empty short-circuits so a bare roster never queries.
        """
        if not dweller_ids:
            return {}
        query = (
            select(
                IncidentParticipant.dweller_id,
                func.count(func.distinct(IncidentParticipant.incident_id)),
            )
            .select_from(IncidentParticipant)
            .join(Incident, Incident.id == IncidentParticipant.incident_id)
            .where(IncidentParticipant.dweller_id.in_(dweller_ids))
            .where(Incident.type.in_(list(incident_types)))
            .group_by(IncidentParticipant.dweller_id)
        )
        rows = (await db_session.execute(query)).all()
        return {row[0]: row[1] for row in rows}


incident_participant_crud = CRUDIncidentParticipant(IncidentParticipant)
