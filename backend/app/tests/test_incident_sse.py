"""TDD tests for SSE publishing in incident_service."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.incident import IncidentStatus, IncidentType
from app.schemas.incident_sse import IncidentSseEvent
from app.services.incident_service import incident_service


@pytest.mark.asyncio
async def test_spawn_incident_publishes_sse(async_session: AsyncSession, room_with_dwellers: dict):
    """Verify spawn_incident publishes SSE after creating the incident."""
    room = room_with_dwellers["room"]

    with patch("app.services.incident_service.sse_manager.publish", new_callable=AsyncMock) as mock_publish:
        incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)

    assert incident is not None
    # Filter for "incidents" topic calls only — other services may publish on different topics
    incident_calls = [c for c in mock_publish.call_args_list if c[0][1] == "incidents"]
    assert len(incident_calls) == 1
    call_args = incident_calls[0]
    assert call_args[0][0] == incident.vault_id
    assert call_args[0][1] == "incidents"
    payload = call_args[0][2]
    assert payload["type"] == "incident_spawned"
    assert payload["incident_id"] == str(incident.id)
    assert payload["vault_id"] == str(incident.vault_id)
    assert payload["incident_type"] == IncidentType.FIRE
    assert payload["room_id"] == str(room.id)
    assert payload["room_name"] == room.name
    assert payload["status"] == IncidentStatus.ACTIVE
    assert "difficulty" in payload


@pytest.mark.asyncio
async def test_process_incident_publishes_only_on_transition(async_session: AsyncSession, vault: "Vault"):  # noqa: F821
    """Verify process_incident publishes SSE only on state transitions, not on damage-only ticks."""
    from app.schemas.dweller import DwellerCreate
    from app.schemas.room import RoomCreate

    # Create two rooms in the vault
    room1_in = RoomCreate(
        name="Power Generator",
        category="Production",
        ability=None,
        base_cost=100,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=1,
        size_max=3,
        vault_id=vault.id,
    )
    room1 = await crud.room.create(db_session=async_session, obj_in=room1_in)

    room2_in = RoomCreate(
        name="Water Treatment",
        category="Production",
        ability=None,
        base_cost=100,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=1,
        size_max=3,
        coordinate_x=2,
        coordinate_y=1,
        vault_id=vault.id,
    )
    room2 = await crud.room.create(db_session=async_session, obj_in=room2_in)

    # --- Part A: No transition (dwellers present, short tick) ---
    from app.schemas.common import GenderEnum, RarityEnum

    dweller_in = DwellerCreate(
        first_name="Test",
        last_name="Dweller",
        vault_id=vault.id,
        room_id=room1.id,
        gender=GenderEnum.MALE,
        rarity=RarityEnum.COMMON,
        strength=5,
        perception=5,
        endurance=5,
        charisma=5,
        intelligence=5,
        agility=5,
        luck=5,
        level=5,
        max_health=100,
        health=100,
    )
    dweller = await crud.dweller.create(db_session=async_session, obj_in=dweller_in)
    await crud.dweller.move_to_room(async_session, dweller.id, room1.id)
    await async_session.commit()

    incident_no_transition = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room1.id,
        incident_type=IncidentType.FIRE,
        difficulty=10,  # High difficulty so it won't resolve quickly
    )

    with patch("app.services.incident_service.sse_manager.publish", new_callable=AsyncMock) as mock_publish:
        result = await incident_service.process_incident(async_session, incident_no_transition, 1)
        assert result.get("skipped") is not True
        mock_publish.assert_not_awaited()

    # --- Part B: Transition via auto-resolve (high enemies_defeated) ---
    incident_resolve = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room1.id,
        incident_type=IncidentType.RADROACH_INFESTATION,
        difficulty=1,
    )
    incident_resolve.enemies_defeated = 100
    async_session.add(incident_resolve)
    await async_session.commit()
    await async_session.refresh(incident_resolve)

    with patch("app.services.incident_service.sse_manager.publish", new_callable=AsyncMock) as mock_publish:
        result = await incident_service.process_incident(async_session, incident_resolve, 60)
        assert result.get("skipped") is not True
        mock_publish.assert_awaited_once()
        call_args = mock_publish.call_args
        assert call_args[0][1] == "incidents"
        payload = call_args[0][2]
        assert payload["type"] == "incident_resolved"
        assert payload["success"] is True
        assert payload["incident_id"] == str(incident_resolve.id)

    # --- Part C: Transition via spreading (no dwellers, elapsed >= duration) ---
    # Move dweller out of room1 to room2 so room1 has no dwellers
    await crud.dweller.move_to_room(async_session, dweller.id, room2.id)
    await async_session.commit()

    incident_spread = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room1.id,
        incident_type=IncidentType.FIRE,
        difficulty=5,
    )
    # Make elapsed time exceed duration
    incident_spread.start_time = datetime.utcnow() - timedelta(hours=2)
    incident_spread.duration = 60  # 60 seconds
    async_session.add(incident_spread)
    await async_session.commit()
    await async_session.refresh(incident_spread)

    with patch("app.services.incident_service.sse_manager.publish", new_callable=AsyncMock) as mock_publish:
        result = await incident_service.process_incident(async_session, incident_spread, 60)
        assert result.get("no_defenders") is True
        mock_publish.assert_awaited_once()
        call_args = mock_publish.call_args
        assert call_args[0][1] == "incidents"
        payload = call_args[0][2]
        assert payload["type"] == "incident_spreading"
        assert payload["incident_id"] == str(incident_spread.id)


@pytest.mark.asyncio
async def test_resolve_incident_manually_publishes_sse(async_session: AsyncSession, room_with_dwellers: dict):
    """Verify resolve_incident_manually publishes SSE with correct success field."""
    room = room_with_dwellers["room"]
    incident = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    await async_session.commit()
    await async_session.refresh(incident)

    # Success case
    with patch("app.services.incident_service.sse_manager.publish", new_callable=AsyncMock) as mock_publish:
        result = await incident_service.resolve_incident_manually(async_session, incident.id, success=True)
        assert result["message"] == "Incident resolved successfully"
        mock_publish.assert_awaited_once()
        call_args = mock_publish.call_args
        assert call_args[0][1] == "incidents"
        payload = call_args[0][2]
        assert payload["type"] == "incident_resolved"
        assert payload["success"] is True
        assert payload["incident_id"] == str(incident.id)

    # Failure case - need a new incident
    incident2 = await incident_service.spawn_incident(async_session, room.vault_id, IncidentType.FIRE)
    await async_session.commit()
    await async_session.refresh(incident2)

    with patch("app.services.incident_service.sse_manager.publish", new_callable=AsyncMock) as mock_publish:
        result = await incident_service.resolve_incident_manually(async_session, incident2.id, success=False)
        assert result["message"] == "Incident failed"
        mock_publish.assert_awaited_once()
        call_args = mock_publish.call_args
        assert call_args[0][1] == "incidents"
        payload = call_args[0][2]
        assert payload["type"] == "incident_resolved"
        assert payload["success"] is False
        assert payload["incident_id"] == str(incident2.id)
