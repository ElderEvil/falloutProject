from typing import Any

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.incident import IncidentType
from app.models.room import Room
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.room import RoomCreate
from app.services.combat.incident_spawning import spawn_incident


async def _room(async_session: AsyncSession, vault_id: Any, name: str, x: int) -> Room:
    return await crud.room.create(
        async_session,
        RoomCreate(
            vault_id=vault_id,
            name=name,
            category=RoomTypeEnum.PRODUCTION,
            ability=SPECIALEnum.STRENGTH,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            output=10,
            size_min=1,
            size_max=3,
            size=1,
            tier=1,
            coordinate_x=x,
            coordinate_y=1,
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
