from datetime import datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.incident import IncidentType
from app.models.room import Room
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.combat import incident_publishing
from app.services.combat.incident_service import incident_service
from app.services.combat.incident_spawning import spawn_incident
from app.tests.factory.dwellers import create_rush_dweller_payload
from app.tests.factory.rooms import create_rush_room_payload
from app.utils.exceptions import ValidationException


async def _room(async_session: AsyncSession, vault_id: Any, name: str, x: int) -> Room:
    return await crud.room.create(
        async_session,
        RoomCreate(
            vault_id=vault_id,
            **create_rush_room_payload(name=name, output=10, coordinate_x=x, coordinate_y=1),
        ),
    )


@pytest_asyncio.fixture
async def rooms(async_session: AsyncSession, user_with_vault: tuple) -> dict[str, Any]:
    _, vault = user_with_vault
    target = await _room(async_session, vault.id, "Power Generator", 1)
    other = await _room(async_session, vault.id, "Diner", 2)
    elevator = await _room(async_session, vault.id, "Elevator", 3)
    return {"vault": vault, "target": target, "other": other, "elevator": elevator}


@pytest.mark.asyncio
async def test_spawn_incident_uses_target_room_and_difficulty_bonus(
    async_session: AsyncSession, rooms: dict[str, Any]
) -> None:
    incident = await spawn_incident(
        async_session,
        rooms["vault"].id,
        IncidentType.FIRE,
        target_room_id=rooms["target"].id,
        difficulty_bonus=4,
    )

    assert incident is not None
    assert incident.room_id == rooms["target"].id
    assert incident.difficulty <= 10
    assert incident.difficulty >= 5


@pytest.mark.asyncio
async def test_spawn_incident_rejects_target_elevator(async_session: AsyncSession, rooms: dict[str, Any]) -> None:
    incident = await spawn_incident(
        async_session,
        rooms["vault"].id,
        IncidentType.FIRE,
        target_room_id=rooms["elevator"].id,
    )

    assert incident is None


@pytest.mark.asyncio
async def test_spawn_incident_rejects_target_with_active_incident(
    async_session: AsyncSession, rooms: dict[str, Any]
) -> None:
    first = await spawn_incident(
        async_session,
        rooms["vault"].id,
        IncidentType.FIRE,
        target_room_id=rooms["target"].id,
    )
    assert first is not None

    second = await spawn_incident(
        async_session,
        rooms["vault"].id,
        IncidentType.FIRE,
        target_room_id=rooms["target"].id,
    )

    assert second is None


@pytest.mark.asyncio
async def test_delayed_incident_activates_after_a_newer_event(
    async_session: AsyncSession, rooms: dict[str, Any]
) -> None:
    vault = rooms["vault"]
    incident = await spawn_incident(
        async_session,
        vault.id,
        IncidentType.FIRE,
        target_room_id=rooms["target"].id,
        start_delay_seconds=5,
    )
    assert incident is not None
    incident_publishing.record_event(async_session, incident, "responders_assigned", "Responders assigned.")
    await async_session.commit()

    incident.start_time = datetime.utcnow() - timedelta(seconds=1)
    async_session.add(incident)
    await async_session.commit()

    await incident_service.process_vault_incidents(async_session, vault.id, 2)

    visible = await incident_service.get_active_incident_list(async_session, vault.id)
    assert visible.incident_count == 1
    events = await crud.incident_crud.get_recent_events(async_session, incident.id)
    assert all(event.kind != "pending" for event in events)


@pytest.mark.asyncio
async def test_assign_responders_rejects_incident_before_its_start(
    async_session: AsyncSession, rooms: dict[str, Any]
) -> None:
    vault = rooms["vault"]
    incident = await spawn_incident(
        async_session,
        vault.id,
        IncidentType.FIRE,
        target_room_id=rooms["target"].id,
        start_delay_seconds=5,
    )
    assert incident is not None
    dweller = await crud.dweller.create(
        async_session,
        DwellerCreate(vault_id=vault.id, **create_rush_dweller_payload()),
    )

    with pytest.raises(ValidationException):
        await incident_service.assign_responders(async_session, incident, [dweller.id])
