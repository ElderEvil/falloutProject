"""Admin incident deletes roll back with their dependent rows."""

import pytest
from sqlalchemy import event, inspect
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import IncidentType
from app.models.incident import Incident
from app.models.incident_event import IncidentEvent
from app.models.room import Room
from app.models.team import Team
from app.services.combat.incident_service import incident_service
from app.tests.factory.rooms import create_overseers_office


async def _incident_with_dependents(db_session: AsyncSession, vault) -> tuple[Incident, IncidentEvent, Team]:
    room = Room(**create_overseers_office(tier=1), vault_id=vault.id)
    db_session.add(room)
    await db_session.flush()
    incident = Incident(vault_id=vault.id, room_id=room.id, type=IncidentType.FIRE, difficulty=1)
    db_session.add(incident)
    await db_session.flush()
    event_row = IncidentEvent(incident_id=incident.id, kind="started", message="Fire started")
    team = Team(vault_id=vault.id, incident_id=incident.id)
    db_session.add_all([event_row, team])
    await db_session.commit()
    return incident, event_row, team


async def test_single_incident_delete_rolls_back_with_its_events(async_session: AsyncSession, vault) -> None:
    incident, event_row, team = await _incident_with_dependents(async_session, vault)

    def fail_commit(_session):
        assert inspect(incident).deleted
        assert inspect(team).deleted
        raise RuntimeError("incident delete failed")

    event.listen(async_session.sync_session, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="incident delete failed"):
            await incident_service.remove_incident(async_session, incident.id)
    finally:
        event.remove(async_session.sync_session, "before_commit", fail_commit)
        await async_session.rollback()

    await async_session.refresh(incident)
    await async_session.refresh(event_row)
    await async_session.refresh(team)
    assert event_row.incident_id == incident.id
    assert team.incident_id == incident.id


async def test_bulk_incident_delete_rolls_back_with_its_events(async_session: AsyncSession, vault) -> None:
    first, first_event, first_team = await _incident_with_dependents(async_session, vault)
    second, second_event, second_team = await _incident_with_dependents(async_session, vault)

    def fail_commit(_session):
        assert inspect(first).deleted
        assert inspect(second).deleted
        assert inspect(first_team).deleted
        assert inspect(second_team).deleted
        raise RuntimeError("incident bulk delete failed")

    event.listen(async_session.sync_session, "before_commit", fail_commit)
    try:
        with pytest.raises(RuntimeError, match="incident bulk delete failed"):
            await incident_service.remove_vault_incidents(async_session, vault.id)
    finally:
        event.remove(async_session.sync_session, "before_commit", fail_commit)
        await async_session.rollback()

    for incident, event_row, team in (
        (first, first_event, first_team),
        (second, second_event, second_team),
    ):
        await async_session.refresh(incident)
        await async_session.refresh(event_row)
        await async_session.refresh(team)
        assert event_row.incident_id == incident.id
        assert team.incident_id == incident.id
