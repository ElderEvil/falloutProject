"""Hazard auto-dispatch: standing teams respond to matching incidents and return to work."""

from unittest.mock import patch

import pytest
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.incident import IncidentType
from app.models.team import ACTIVE_STATUS, DISPATCHED_STATUS, RESERVE_STATUS, TeamMember
from app.schemas.common import RoomTypeEnum, SPECIALEnum
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultUpdate
from app.services.combat.incident_service import MAX_INCIDENT_RESPONDERS, incident_service
from app.services.dweller_service import dweller_service
from app.services.hazard_team_service import hazard_team_service
from app.services.room_assignment_policy import get_highest_special
from app.services.room_service import room_service
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
            # Size 6 (4 worker slots): the setup parks extra plus both team
            # members here, which a size-3 room could not hold under the
            # manual-assignment worker cap.
            size=6,
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


def _response_station(vault_id: UUID4, *, x: int = 20, size: int = 3) -> RoomCreate:
    """The unique Response Station catalog payload (null incremental cost, 3..9 footprint)."""
    return RoomCreate(
        name="Response Station",
        category=RoomTypeEnum.RESPONSE,
        ability=SPECIALEnum.ENDURANCE,
        base_cost=600,
        incremental_cost=None,
        t2_upgrade_cost=None,
        t3_upgrade_cost=None,
        size_min=3,
        size_max=9,
        size=size,
        tier=1,
        coordinate_x=x,
        coordinate_y=1,
        vault_id=vault_id,
    )


@pytest.mark.asyncio
async def test_stationed_responder_returns_to_station_after_dispatch(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """A responder stationed in the Response Station returns to the station, not to production.

    Reproduction for issue #997 task 6: the return-to-work pass must restore a
    stationed responder's station posting instead of silently auto-assigning them
    to a production room.
    """
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    for index, dweller in enumerate(dwellers):
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Work Room {index}", get_highest_special(dweller), index + 1, 9),
        )
    await async_session.commit()
    for dweller in dwellers:
        await dweller_service.move_to_room(async_session, dweller.id, station.id)
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    dispatched = await hazard_team_service.dispatch_to_incident(async_session, incident)
    assert sorted(dispatched) == sorted(d.id for d in dwellers)
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == incident.room_id

    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    await hazard_team_service.return_dispatched_responders(async_session, incident)

    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == station.id


@pytest.mark.asyncio
async def test_already_returned_responder_closes_the_ledger_idempotently(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """A responder already back at the station closes the ledger instead of staying dispatched.

    Reproduction for the review finding: ``move_to_room`` refuses a dweller who is
    already in the target room, which left the roster row stuck on "dispatched".
    """
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    for index, dweller in enumerate(dwellers):
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Work Room {index}", get_highest_special(dweller), index + 1, 9),
        )
    await async_session.commit()
    for dweller in dwellers:
        await dweller_service.move_to_room(async_session, dweller.id, station.id)
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    await hazard_team_service.dispatch_to_incident(async_session, incident)
    for dweller in dwellers:
        await dweller_service.move_to_room(async_session, dweller.id, station.id)
    await crud.incident_crud.resolve(async_session, incident.id, success=True)

    returned = await hazard_team_service.return_dispatched_responders(async_session, incident)

    assert returned == len(dwellers)
    roster = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert roster
    assert all(member.status == "completed" for member in roster)


def test_origin_room_foreign_key_declares_set_null() -> None:
    """The origin_room_id FK clears itself when the referenced room is demolished.

    This is the schema guarantee behind the behaviour below: a deleted station
    leaves no posting to restore, so the return pass auto-assigns the responder.
    """
    foreign_key = next(iter(TeamMember.__table__.c.origin_room_id.foreign_keys))
    assert foreign_key.ondelete == "SET NULL"
    assert foreign_key.column.table.name == "room"


@pytest.mark.asyncio
async def test_demolished_station_while_dispatched_return_auto_assigns(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """Demolishing the station while its team is dispatched must not strand the return pass.

    The room deletion clears each responder's origin (SET NULL), so the finished
    incident still sends them back to work instead of raising on a vanished room.
    """
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    work_rooms = [
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Work Room {index}", get_highest_special(dweller), index + 1, 9),
        )
        for index, dweller in enumerate(dwellers)
    ]
    await async_session.commit()
    for dweller in dwellers:
        await dweller_service.move_to_room(async_session, dweller.id, station.id)
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    assert sorted(await hazard_team_service.dispatch_to_incident(async_session, incident)) == sorted(
        dweller.id for dweller in dwellers
    )
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.origin_room_id == station.id for member in members)

    # The station comes down while its responders are out on the incident.
    await room_service.destroy_room(async_session, station.id)

    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.origin_room_id is None for member in members)

    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    returned = await hazard_team_service.return_dispatched_responders(async_session, incident)

    assert returned == len(dwellers)
    work_room_ids = {room.id for room in work_rooms}
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id in work_room_ids
        assert dweller.room_id != incident.room_id
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == "completed" for member in members)


@pytest.mark.asyncio
async def test_dispatch_and_return_after_station_rebuilt_targets_rebuilt_station(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """A rebuilt station is a normal posting again: the next dispatch returns to the new room."""
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    for index, dweller in enumerate(dwellers):
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Work Room {index}", get_highest_special(dweller), index + 1, 9),
        )
    await async_session.commit()

    await room_service.destroy_room(async_session, station.id)
    rebuilt = await crud.room.create(async_session, _response_station(vault.id))
    assert rebuilt.id != station.id

    for dweller in dwellers:
        await dweller_service.move_to_room(async_session, dweller.id, rebuilt.id)
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    assert sorted(await hazard_team_service.dispatch_to_incident(async_session, incident)) == sorted(
        dweller.id for dweller in dwellers
    )
    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    returned = await hazard_team_service.return_dispatched_responders(async_session, incident)

    assert returned == len(dwellers)
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == rebuilt.id


@pytest.mark.asyncio
async def test_responder_posted_elsewhere_keeps_production_return(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """A responder posted in production still returns there, not to the Response Station.

    The station exists, so a station-preferring return would be possible — the
    responder's own posting is what decides the destination, preserving the
    pre-existing return-to-work behaviour for everyone not stationed.
    """
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    work_rooms = [
        await crud.room.create(
            async_session,
            _work_room(vault.id, f"Work Room {index}", get_highest_special(dweller), index + 1, 9),
        )
        for index, dweller in enumerate(dwellers)
    ]
    await async_session.commit()
    for dweller, work_room in zip(dwellers, work_rooms, strict=True):
        await dweller_service.move_to_room(async_session, dweller.id, work_room.id)
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    await hazard_team_service.dispatch_to_incident(async_session, incident)
    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    returned = await hazard_team_service.return_dispatched_responders(async_session, incident)

    assert returned == len(dwellers)
    for dweller in dwellers:
        await async_session.refresh(dweller)
        room = await crud.room.get(async_session, dweller.room_id)
        assert room is not None
        assert room.category == RoomTypeEnum.PRODUCTION
        assert dweller.room_id != station.id
        assert dweller.room_id != incident.room_id


@pytest.mark.asyncio
async def test_roomless_responder_keeps_default_return(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A responder with no posting is unaffected by the station restore and returns as before."""
    vault = room_with_dwellers["vault"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    nomad = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await crud.room.create(async_session, _work_room(vault.id, "Diner", get_highest_special(nomad), 1, 9))
    await async_session.commit()
    assert nomad.room_id is None
    await make_member(async_session, vault.id, nomad.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    assert await hazard_team_service.dispatch_to_incident(async_session, incident) == [nomad.id]
    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    returned = await hazard_team_service.return_dispatched_responders(async_session, incident)

    assert returned == 1
    await async_session.refresh(nomad)
    room = await crud.room.get(async_session, nomad.room_id)
    assert room is not None
    assert room.category == RoomTypeEnum.PRODUCTION
    assert nomad.room_id != station.id


@pytest.mark.asyncio
async def test_resident_responders_keep_their_original_room_after_resolution(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """Responders originally posted in the incident room stay there and close their ledger."""
    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
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
        assert dweller.room_id == incident.room_id
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
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict, success: bool
):
    """Real full-room conflicts retry on later ticks after capacity becomes available."""
    from app.models.game_state import GameState

    vault = room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    origins = []
    for index, dweller in enumerate(dwellers):
        origin = await crud.room.create(
            async_session, _work_room(vault.id, f"Retry Work {index}", get_highest_special(dweller), index + 1, 9)
        )
        await dweller_service.move_to_room(async_session, dweller.id, origin.id)
        origins.append(origin)
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    await hazard_team_service.dispatch_to_incident(async_session, incident)
    blockers = []
    for origin in origins:
        for _ in range(2):
            blocker = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
            await dweller_service.move_to_room(async_session, blocker.id, origin.id)
            blockers.append(blocker)
    await crud.incident_crud.resolve(async_session, incident.id, success=success)
    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == DISPATCHED_STATUS for member in members)
    for blocker in blockers:
        await dweller_service.update_dweller(async_session, blocker.id, {"room_id": None})
    await incident_service.process_vault_incidents(async_session, vault.id, 5, game_state=GameState(vault_id=vault.id))
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == "completed" for member in members)
    for dweller, origin in zip(dwellers, origins, strict=True):
        await async_session.refresh(dweller)
        assert dweller.room_id == origin.id


@pytest.mark.parametrize("success", [True, False])
async def test_manual_responder_returns_to_original_posting(
    async_session: AsyncSession, room_with_dwellers: dict, success: bool
):
    vault = room_with_dwellers["vault"]
    target = room_with_dwellers["room"]
    responder = room_with_dwellers["dwellers"][0]
    origin = await crud.room.create(async_session, _work_room(vault.id, "Original Work", SPECIALEnum.STRENGTH, 10, 9))
    await dweller_service.move_to_room(async_session, responder.id, origin.id)
    incident = await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=target.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    await incident_service.assign_responders(async_session, incident, [responder.id])
    # Re-selecting an existing responder must not overwrite their original posting.
    await incident_service.assign_responders(async_session, incident, [responder.id])
    await crud.incident_crud.resolve(async_session, incident.id, success=success)
    await hazard_team_service.return_dispatched_responders(async_session, incident)
    await async_session.refresh(responder)
    assert responder.room_id == origin.id
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert members[0].origin_room_id == origin.id
    assert members[0].status == "completed"


@pytest.mark.parametrize("record_origin", [True, False])
async def test_auto_return_does_not_leave_incident_room_over_capacity(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict, record_origin: bool
):
    vault = room_with_dwellers["vault"]
    target = room_with_dwellers["room"]
    target.ability = SPECIALEnum.STRENGTH
    target.size = 3
    async_session.add(target)
    origin = await crud.room.create(async_session, _work_room(vault.id, "Original Work", SPECIALEnum.STRENGTH, 10, 9))
    responders = []
    for index in range(2):
        data = {
            **dweller_data,
            "first_name": f"Responder{index}",
            **dict.fromkeys(("perception", "endurance", "charisma", "intelligence", "agility", "luck"), 1),
            "strength": 10,
        }
        responder = await crud.dweller.create(async_session, obj_in=DwellerCreate(**data, vault_id=vault.id))
        await dweller_service.move_to_room(async_session, responder.id, origin.id)
        await make_member(async_session, vault.id, responder.id, HazardTeam.FIRE, ACTIVE_STATUS)
        responders.append(responder)
    incident = await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=target.id, incident_type=IncidentType.FIRE, difficulty=2
    )
    assert len(await hazard_team_service.dispatch_to_incident(async_session, incident)) == 2
    if not record_origin:
        for member in await crud.team_crud.get_incident_team(async_session, incident.id, vault.id):
            member.origin_room_id = None
            async_session.add(member)
        await async_session.commit()
    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 2
    assert await crud.dweller.count_in_room(async_session, target.id, include_apprentices=False) == 2
    for responder in responders:
        await async_session.refresh(responder)
        assert responder.room_id == origin.id


@pytest.mark.parametrize("population_full", [False, True])
async def test_full_original_room_leaves_manual_responder_idle_until_retry(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict, population_full: bool
):
    vault = room_with_dwellers["vault"]
    responder = room_with_dwellers["dwellers"][0]
    origin = await crud.room.create(async_session, _work_room(vault.id, "Original Work", SPECIALEnum.STRENGTH, 10, 9))
    await dweller_service.move_to_room(async_session, responder.id, origin.id)
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    await incident_service.assign_responders(async_session, incident, [responder.id])
    blockers = []
    for _ in range(2):
        blocker = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
        await dweller_service.move_to_room(async_session, blocker.id, origin.id)
        blockers.append(blocker)
    await crud.incident_crud.resolve(async_session, incident.id, success=True)

    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0
    await async_session.refresh(responder)
    assert responder.room_id is None
    assert responder.status.value == "idle"
    assert [row.id for row in await crud.incident_crud.get_pending_responder_returns(async_session, vault.id)] == [
        incident.id
    ]
    assert await crud.dweller.count_in_room(async_session, origin.id) == 2

    if population_full:
        # Free an original-room slot without freeing a vault population slot.
        await crud.vault.update(async_session, vault.id, VaultUpdate(population_max=3))
        await dweller_service.move_to_room(async_session, blockers[0].id, room_with_dwellers["room"].id)
        assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0
        await async_session.refresh(responder)
        assert responder.room_id is None
        assert [row.id for row in await crud.incident_crud.get_pending_responder_returns(async_session, vault.id)] == [
            incident.id
        ]

    await dweller_service.update_dweller(async_session, blockers[0].id, {"room_id": None})
    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 1
    await async_session.refresh(responder)
    assert responder.room_id == origin.id
    assert await crud.incident_crud.get_pending_responder_returns(async_session, vault.id) == []


@pytest.mark.parametrize("new_incident", [False, True])
async def test_finished_return_does_not_override_new_assignment(
    async_session: AsyncSession, room_with_dwellers: dict, new_incident: bool
):
    vault = room_with_dwellers["vault"]
    responder = room_with_dwellers["dwellers"][0]
    origin = await crud.room.create(async_session, _work_room(vault.id, "Original Work", SPECIALEnum.STRENGTH, 10, 9))
    new_room = await crud.room.create(async_session, _work_room(vault.id, "New Posting", SPECIALEnum.STRENGTH, 12, 9))
    await dweller_service.move_to_room(async_session, responder.id, origin.id)
    incident = await crud.incident_crud.create(
        async_session,
        vault_id=vault.id,
        room_id=room_with_dwellers["room"].id,
        incident_type=IncidentType.FIRE,
        difficulty=2,
    )
    await incident_service.assign_responders(async_session, incident, [responder.id])
    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    if new_incident:
        next_incident = await crud.incident_crud.create(
            async_session, vault_id=vault.id, room_id=new_room.id, incident_type=IncidentType.FIRE, difficulty=2
        )
        await incident_service.assign_responders(async_session, next_incident, [responder.id])
    else:
        await dweller_service.move_to_room(async_session, responder.id, new_room.id)

    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0
    await async_session.refresh(responder)
    assert responder.room_id == new_room.id
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert members[0].status == "completed"
