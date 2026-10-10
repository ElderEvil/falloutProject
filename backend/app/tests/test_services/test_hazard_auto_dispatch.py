"""Hazard auto-dispatch: standing teams respond to matching incidents and return to work."""

from unittest.mock import patch

import pytest
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.incident import IncidentType
from app.models.team import ACTIVE_STATUS, DISPATCHED_STATUS, RESERVE_STATUS
from app.schemas.common import RoomTypeEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.services.combat.incident_service import MAX_INCIDENT_RESPONDERS, incident_service
from app.services.dweller_service import dweller_service
from app.services.hazard_team_service import hazard_team_service
from app.services.room_assignment_policy import get_highest_special
from app.tests.test_services._hazard_team_helpers import make_member


def _work_room(vault_id: UUID4, name: str, ability, x: int, y: int) -> RoomCreate:
    """A production room with capacity, so auto-assign can land a dweller there."""
    return RoomCreate(
        name=name,
        category=RoomTypeEnum.PRODUCTION,
        ability=ability,
        base_cost=100,
        incremental_cost=50,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        size_min=3,
        size_max=6,
        size=3,
        tier=1,
        coordinate_x=x,
        coordinate_y=y,
        vault_id=vault_id,
    )


@pytest.mark.asyncio
async def test_fire_spawn_dispatches_active_team(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A fire spawn moves the vault's active Fire team into the incident room, marked dispatched."""
    room = room_with_dwellers["room"]
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    # A second occupied room so the spawn target is controllable.
    room_b = await crud.room.create(
        async_session,
        RoomCreate(
            name="Diner",
            category=RoomTypeEnum.PRODUCTION,
            ability=None,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=3,
            size_max=6,
            size=3,
            tier=1,
            coordinate_x=5,
            coordinate_y=5,
            vault_id=vault.id,
        ),
    )
    extra = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await dweller_service.move_to_room(async_session, extra.id, room_b.id)
    # Move the team members away from the incident room.
    for dweller in dwellers:
        await dweller_service.move_to_room(async_session, dweller.id, room_b.id)
    await async_session.commit()
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    with patch("app.services.combat.incident_spawning.random.choice", return_value=room):
        incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident is not None
    assert incident.room_id == room.id

    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == room.id
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert sorted(member.dweller_id for member in members) == sorted(d.id for d in dwellers)
    assert all(member.status == DISPATCHED_STATUS for member in members)


@pytest.mark.asyncio
async def test_non_hazard_incident_does_not_dispatch(async_session: AsyncSession, room_with_dwellers: dict):
    """A raider attack leaves the Fire team untouched and nobody moves."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    for dweller in dwellers:
        await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    original_rooms = {dweller.id: dweller.room_id for dweller in dwellers}

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=room.vault_id,
        room_id=room.id,
        incident_type=IncidentType.RAIDER_ATTACK,
        difficulty=2,
    )
    dispatched = await hazard_team_service.dispatch_to_incident(async_session, incident)

    assert dispatched == []
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is None
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == original_rooms[dweller.id]


@pytest.mark.asyncio
async def test_no_active_team_is_a_noop(async_session: AsyncSession, room_with_dwellers: dict):
    """No team, or a bench-only team, dispatches nobody and writes no roster."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]

    incident = await crud.incident_crud.create(
        async_session, vault_id=room.vault_id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    assert await hazard_team_service.dispatch_to_incident(async_session, incident) == []
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is None

    for dweller in dwellers:
        await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)
    incident = await crud.incident_crud.create(
        async_session, vault_id=room.vault_id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    assert await hazard_team_service.dispatch_to_incident(async_session, incident) == []
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, room.vault_id) is None


@pytest.mark.asyncio
async def test_dispatch_respects_responder_cap(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """An incident roster already at the cap dispatches nothing."""
    room = room_with_dwellers["room"]
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    incident = await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    filler_ids = [
        (await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))).id
        for _ in range(MAX_INCIDENT_RESPONDERS)
    ]
    await crud.team_crud.add_incident_team_members(async_session, incident.id, vault.id, filler_ids)
    await async_session.commit()
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    assert await hazard_team_service.dispatch_to_incident(async_session, incident) == []
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert len(members) == MAX_INCIDENT_RESPONDERS
    assert all(member.status == "assigned" for member in members)


@pytest.mark.asyncio
async def test_unavailable_member_skipped_others_dispatched(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A wounded active member is skipped; the healthy ones still respond."""
    room = room_with_dwellers["room"]
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    wounded = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    wounded.health = 0
    async_session.add(wounded)
    await async_session.commit()
    for dweller in [*dwellers, wounded]:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    dispatched = await hazard_team_service.dispatch_to_incident(async_session, incident)

    assert sorted(dispatched) == sorted(d.id for d in dwellers)
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert sorted(member.dweller_id for member in members) == sorted(d.id for d in dwellers)
    assert all(member.status == DISPATCHED_STATUS for member in members)


@pytest.mark.asyncio
async def test_dispatch_skips_responder_committed_to_another_incident(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A hazard-team member already rostered on another active incident is skipped and named in the event."""
    room = room_with_dwellers["room"]
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    room_b = await crud.room.create(
        async_session,
        RoomCreate(
            name="Diner",
            category=RoomTypeEnum.PRODUCTION,
            ability=None,
            base_cost=100,
            incremental_cost=50,
            t2_upgrade_cost=500,
            t3_upgrade_cost=1500,
            size_min=3,
            size_max=6,
            size=3,
            tier=1,
            coordinate_x=5,
            coordinate_y=5,
            vault_id=vault.id,
        ),
    )
    for dweller in dwellers:
        await dweller_service.move_to_room(async_session, dweller.id, room_b.id)
    await async_session.commit()
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    # The first incident commits one team member via manual assignment.
    first = await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    committed = dwellers[0]
    await incident_service.assign_responders(async_session, first, [committed.id])

    # Auto-dispatch to a second incident must skip the committed member.
    second = await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=room_b.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    dispatched = await hazard_team_service.dispatch_to_incident(async_session, second)

    assert committed.id not in dispatched
    assert sorted(dispatched) == sorted(d.id for d in dwellers[1:])
    members = await crud.team_crud.get_incident_team(async_session, second.id, vault.id)
    assert sorted(member.dweller_id for member in members) == sorted(d.id for d in dwellers[1:])
    assert all(member.status == DISPATCHED_STATUS for member in members)

    events = await crud.incident_crud.get_recent_events(async_session, second.id)
    dispatch_event = next(event for event in events if event.kind == "responders_dispatched")
    assert dispatch_event.data == {"skipped": [committed.first_name]}


@pytest.mark.asyncio
async def test_return_dispatched_responders_after_resolution(async_session: AsyncSession, room_with_dwellers: dict):
    """Resolving the incident puts dispatched members back to work and marks them completed."""
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    for index, dweller in enumerate(dwellers):
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Work Room {index}", get_highest_special(dweller), index + 1, 9),
        )
    await async_session.commit()
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident is not None
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert len(members) == len(dwellers)
    assert all(member.status == DISPATCHED_STATUS for member in members)

    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    await async_session.refresh(incident)
    assert incident.status.value == "resolved"

    returned = await hazard_team_service.return_dispatched_responders(async_session, incident)
    assert returned == len(dwellers)
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id != incident.room_id
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == "completed" for member in members)


@pytest.mark.asyncio
async def test_return_dispatched_responders_is_idempotent(async_session: AsyncSession, room_with_dwellers: dict):
    """A second return pass finds nobody left to return."""
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    for index, dweller in enumerate(dwellers):
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Work Room {index}", get_highest_special(dweller), index + 1, 9),
        )
    await async_session.commit()
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident is not None
    await crud.incident_crud.resolve(async_session, incident.id, success=True)

    first = await hazard_team_service.return_dispatched_responders(async_session, incident)
    second = await hazard_team_service.return_dispatched_responders(async_session, incident)

    assert first == len(dwellers)
    assert second == 0


@pytest.mark.asyncio
async def test_return_marks_dead_dispatched_completed_without_returning(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """A dispatched responder who died still closes the ledger: completed, not re-assigned."""
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    for index, dweller in enumerate(dwellers):
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Work Room {index}", get_highest_special(dweller), index + 1, 9),
        )
    await async_session.commit()
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident is not None

    fallen = dwellers[0]
    fallen.is_dead = True
    fallen.health = 0
    async_session.add(fallen)
    await async_session.commit()

    await crud.incident_crud.resolve(async_session, incident.id, success=False)
    returned = await hazard_team_service.return_dispatched_responders(async_session, incident)

    assert returned == len(dwellers) - 1
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == "completed" for member in members)


@pytest.mark.parametrize("success", [True, False])
async def test_tick_retries_returns_for_finished_incident(
    async_session: AsyncSession, room_with_dwellers: dict, success: bool
):
    """A capacity conflict must not strand a dispatched responder after the fight ends."""
    from unittest.mock import AsyncMock

    from app.models.game_state import GameState
    from app.utils.exceptions import ResourceConflictException

    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    for index, dweller in enumerate(dwellers):
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Retry Work {index}", get_highest_special(dweller), index + 1, 9),
        )
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident is not None
    await crud.incident_crud.resolve(async_session, incident.id, success=success)
    with patch.object(
        dweller_service, "auto_assign_to_best_room", side_effect=ResourceConflictException("Production rooms full")
    ):
        assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == DISPATCHED_STATUS for member in members)
    with patch.object(incident_service, "should_spawn_incident", new=AsyncMock(return_value=False)):
        await incident_service.process_vault_incidents(
            async_session, vault.id, 5, game_state=GameState(vault_id=vault.id)
        )
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == "completed" for member in members)
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id != incident.room_id
