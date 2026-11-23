from unittest.mock import patch
from uuid import UUID

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import DwellerStatusEnum, HazardTeam, IncidentType, RoomTypeEnum, SPECIALEnum
from app.models.game_state import GameState
from app.models.team import ACTIVE_STATUS, DISPATCHED_STATUS, RESERVE_STATUS, TeamMember
from app.schemas.dweller import DwellerCreate
from app.schemas.room import RoomCreate
from app.schemas.vault import VaultUpdate
from app.services.combat.incident_service import MAX_INCIDENT_RESPONDERS, incident_service
from app.services.dweller_service import dweller_service
from app.services.hazard_team_service import hazard_team_service
from app.services.room_assignment_policy import get_highest_special
from app.services.room_service import room_service
from app.tests.test_services._hazard_team_helpers import make_member

# Production room with capacity, so auto-assign can land a dweller there.
_PRODUCTION = {
    "category": RoomTypeEnum.PRODUCTION,
    "base_cost": 100,
    "incremental_cost": 50,
    "t2_upgrade_cost": 500,
    "t3_upgrade_cost": 1500,
    "size_min": 3,
    "size_max": 6,
}
# The unique Response Station catalog payload (null incremental cost, 3..9 footprint).
_STATION = {
    "category": RoomTypeEnum.RESPONSE,
    "ability": SPECIALEnum.ENDURANCE,
    "base_cost": 600,
    "size_min": 3,
    "size_max": 9,
    "incremental_cost": None,
    "t2_upgrade_cost": None,
    "t3_upgrade_cost": None,
}


def _work_room(vault_id, name, ability, x, y, size=3):
    return RoomCreate(
        **_PRODUCTION, name=name, ability=ability, size=size, coordinate_x=x, coordinate_y=y, vault_id=vault_id
    )


def _response_station(vault_id, *, x=20, size=3):
    return RoomCreate(**_STATION, name="Response Station", size=size, coordinate_x=x, coordinate_y=1, vault_id=vault_id)


async def _posted_team(session, vault, dwellers, *, post_to=None, prefix="Work Room", activate=True):
    """Create one work room per dweller, post and activate them (or post all to `post_to`)."""
    rooms = [
        await crud.room.create(session, _work_room(vault.id, f"{prefix} {i}", get_highest_special(d), i + 1, 9))
        for i, d in enumerate(dwellers)
    ]
    for index, dweller in enumerate(dwellers):
        await dweller_service.move_to_room(session, dweller.id, (post_to or rooms[index]).id)
        if activate:
            await make_member(session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
    await session.commit()
    return rooms


async def _fire_incident(session, vault, room):
    return await crud.incident_crud.create(
        session, vault_id=vault.id, room_id=room.id, incident_type=IncidentType.FIRE, difficulty=2
    )


async def _team_ids(session, incident, vault):
    return [member.dweller_id for member in await crud.team_crud.get_incident_team(session, incident.id, vault.id)]


async def _finish(session, incident, *, success=True):
    await crud.incident_crud.resolve(session, incident.id, success=success)
    return await hazard_team_service.return_dispatched_responders(session, incident)


async def test_fire_spawn_dispatches_active_team(async_session, room_with_dwellers, dweller_data):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    payload = _work_room(vault.id, "Diner", None, 5, 5)
    # Size 6 (4 worker slots): the setup parks the extra plus both team members here,
    # which a size-3 room could not hold under the manual-assignment worker cap.
    payload.size = 6
    room_b = await crud.room.create(async_session, payload)
    extra = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await dweller_service.move_to_room(async_session, extra.id, room_b.id)
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
    assert sorted(await _team_ids(async_session, incident, vault)) == sorted(d.id for d in dwellers)
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == DISPATCHED_STATUS for member in members)


async def test_dispatch_ignores_non_hazard_incidents_and_teams_without_active_members(
    async_session, room_with_dwellers
):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    original_rooms = {dweller.id: dweller.room_id for dweller in dwellers}

    incident = await crud.incident_crud.create(
        async_session, vault_id=vault.id, room_id=room.id, incident_type=IncidentType.RAIDER_ATTACK, difficulty=2
    )
    assert await hazard_team_service.dispatch_to_incident(async_session, incident) == []
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, vault.id) is None
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == original_rooms[dweller.id]

    # Reserve-only roster is still a no-op for a hazard incident.
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)
    incident = await _fire_incident(async_session, vault, room)
    assert await hazard_team_service.dispatch_to_incident(async_session, incident) == []
    assert await crud.team_crud.get_incident_team_row(async_session, incident.id, vault.id) is None


async def test_dispatch_respects_responder_cap(async_session, room_with_dwellers, dweller_data):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    incident = await _fire_incident(async_session, vault, room)
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


@pytest.mark.parametrize(("health", "status"), [(0, DwellerStatusEnum.IDLE), (100, DwellerStatusEnum.FIGHTING)])
async def test_unavailable_member_skipped_others_dispatched(
    async_session, room_with_dwellers, dweller_data, health, status
):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    for dweller in dwellers:
        await dweller_service.update_dweller(async_session, dweller.id, {"room_id": None})
    wounded = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    wounded.health = health
    wounded.status = status
    async_session.add(wounded)
    await async_session.commit()
    for dweller in [*dwellers, wounded]:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await _fire_incident(async_session, vault, room)
    dispatched = await hazard_team_service.dispatch_to_incident(async_session, incident)

    assert sorted(dispatched) == sorted(d.id for d in dwellers)
    assert sorted(await _team_ids(async_session, incident, vault)) == sorted(d.id for d in dwellers)
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == DISPATCHED_STATUS for member in members)


async def test_dispatch_skips_responder_committed_to_another_incident(async_session, room_with_dwellers):
    room, vault = room_with_dwellers["room"], room_with_dwellers["vault"]
    dwellers = room_with_dwellers["dwellers"]
    room_b = await crud.room.create(async_session, _work_room(vault.id, "Diner", None, 5, 5))
    for dweller in dwellers:
        await dweller_service.move_to_room(async_session, dweller.id, room_b.id)
    await async_session.commit()
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    # The first incident commits one team member via manual assignment.
    first = await _fire_incident(async_session, vault, room)
    committed = dwellers[0]
    await incident_service.assign_responders(async_session, first, [committed.id])

    room_c = await crud.room.create(async_session, _work_room(vault.id, "Other Incident", SPECIALEnum.STRENGTH, 10, 9))
    second = await _fire_incident(async_session, vault, room_c)
    dispatched = await hazard_team_service.dispatch_to_incident(async_session, second)

    assert committed.id not in dispatched
    assert sorted(dispatched) == sorted(d.id for d in dwellers[1:])
    assert sorted(await _team_ids(async_session, second, vault)) == sorted(d.id for d in dwellers[1:])
    members = await crud.team_crud.get_incident_team(async_session, second.id, vault.id)
    assert all(member.status == DISPATCHED_STATUS for member in members)

    events = await crud.incident_crud.get_recent_events(async_session, second.id)
    dispatch_event = next(event for event in events if event.kind == "responders_dispatched")
    assert dispatch_event.data == {"skipped": [committed.first_name]}


@pytest.mark.parametrize("mode", ["return", "already_back", "dead"])
async def test_stationed_responder_returns_to_station_after_dispatch(async_session, room_with_dwellers, mode):
    # A stationed responder returns to the station, not to production; already-returned and
    # dead dwellers still close the ledger instead of staying "dispatched".
    vault, dwellers = room_with_dwellers["vault"], room_with_dwellers["dwellers"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    await _posted_team(async_session, vault, dwellers, post_to=station)

    incident = await _fire_incident(async_session, vault, room_with_dwellers["room"])
    assert sorted(await hazard_team_service.dispatch_to_incident(async_session, incident)) == sorted(
        d.id for d in dwellers
    )
    if mode == "dead":
        fallen = dwellers[0]
        fallen.is_dead = True
        fallen.health = 0
        async_session.add(fallen)
        await async_session.commit()
        assert await _finish(async_session, incident, success=False) == len(dwellers) - 1
        members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
        assert all(member.status == "completed" for member in members)
        return
    if mode == "already_back":
        for dweller in dwellers:
            await dweller_service.move_to_room(async_session, dweller.id, station.id)
        await crud.incident_crud.resolve(async_session, incident.id, success=True)
        assert await hazard_team_service.return_dispatched_responders(async_session, incident) == len(dwellers)
        roster = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
        assert roster
        assert all(member.status == "completed" for member in roster)
        return

    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == incident.room_id
    await _finish(async_session, incident)
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == station.id


def test_origin_room_foreign_key_declares_set_null():
    # A deleted station leaves no posting to restore (SET NULL on the origin FK).
    foreign_key = next(iter(TeamMember.__table__.c.origin_room_id.foreign_keys))
    assert foreign_key.ondelete == "SET NULL"
    assert foreign_key.column.table.name == "room"


@pytest.mark.parametrize("rebuild", [False, True])
async def test_station_demolition_and_rebuild_handles_dispatch_returns(async_session, room_with_dwellers, rebuild):
    vault, dwellers = room_with_dwellers["vault"], room_with_dwellers["dwellers"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    if rebuild:
        work_rooms = await _posted_team(async_session, vault, dwellers, activate=False)
        await room_service.destroy_room(async_session, station.id)
        rebuilt = await crud.room.create(async_session, _response_station(vault.id))
        assert rebuilt.id != station.id
        for dweller in dwellers:
            await dweller_service.move_to_room(async_session, dweller.id, rebuilt.id)
            await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)
        expected_origin, expected_room = rebuilt.id, rebuilt.id
    else:
        work_rooms = await _posted_team(async_session, vault, dwellers, post_to=station)
        expected_origin, expected_room = station.id, None

    incident = await _fire_incident(async_session, vault, room_with_dwellers["room"])
    assert sorted(await hazard_team_service.dispatch_to_incident(async_session, incident)) == sorted(
        d.id for d in dwellers
    )
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.origin_room_id == expected_origin for member in members)

    if not rebuild:
        # The station comes down while its responders are out on the incident.
        await room_service.destroy_room(async_session, station.id)
        members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
        assert all(member.origin_room_id is None for member in members)

    assert await _finish(async_session, incident) == len(dwellers)
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == expected_room
        if not rebuild:
            assert work_rooms
            assert dweller.room_id != incident.room_id
    if not rebuild:
        members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
        assert all(member.status == "completed" for member in members)


async def test_responder_posted_elsewhere_keeps_production_return(async_session, room_with_dwellers):
    # The responder's own posting decides the destination even when a station exists;
    # a second return pass is a no-op.
    vault, dwellers = room_with_dwellers["vault"], room_with_dwellers["dwellers"]
    station = await crud.room.create(async_session, _response_station(vault.id))
    await _posted_team(async_session, vault, dwellers)

    incident = await _fire_incident(async_session, vault, room_with_dwellers["room"])
    await hazard_team_service.dispatch_to_incident(async_session, incident)
    assert await _finish(async_session, incident) == len(dwellers)
    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0

    for dweller in dwellers:
        await async_session.refresh(dweller)
        room = await crud.room.get(async_session, dweller.room_id)
        assert room is not None
        assert room.category == RoomTypeEnum.PRODUCTION
        assert dweller.room_id != station.id
        assert dweller.room_id != incident.room_id


async def test_roomless_responder_returns_to_unassigned(async_session, room_with_dwellers, dweller_data):
    vault = room_with_dwellers["vault"]
    await crud.room.create(async_session, _response_station(vault.id))
    nomad = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    await crud.room.create(async_session, _work_room(vault.id, "Diner", get_highest_special(nomad), 1, 9))
    await async_session.commit()
    assert nomad.room_id is None
    await make_member(async_session, vault.id, nomad.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await _fire_incident(async_session, vault, room_with_dwellers["room"])
    assert await hazard_team_service.dispatch_to_incident(async_session, incident) == [nomad.id]
    assert await _finish(async_session, incident) == 1

    await async_session.refresh(nomad)
    assert nomad.room_id is None
    assert nomad.status.value == "idle"


async def test_resident_responders_keep_their_original_room_after_resolution(async_session, room_with_dwellers):
    vault, dwellers = room_with_dwellers["vault"], room_with_dwellers["dwellers"]
    for dweller in dwellers:
        await make_member(async_session, vault.id, dweller.id, HazardTeam.FIRE, ACTIVE_STATUS)

    incident = await incident_service.spawn_incident(async_session, vault.id, IncidentType.FIRE)
    assert incident is not None
    # Residents never consume helper slots or need returns.
    assert await crud.team_crud.get_incident_team(async_session, incident.id, vault.id) == []

    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    await async_session.refresh(incident)
    assert incident.status.value == "resolved"

    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0
    for dweller in dwellers:
        await async_session.refresh(dweller)
        assert dweller.room_id == incident.room_id
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert all(member.status == "completed" for member in members)


@pytest.mark.parametrize("success", [True, False])
async def test_tick_retries_returns_for_finished_incident(async_session, room_with_dwellers, dweller_data, success):
    vault, dwellers = room_with_dwellers["vault"], room_with_dwellers["dwellers"]
    origins = await _posted_team(async_session, vault, dwellers, prefix="Retry Work")
    incident = await _fire_incident(async_session, vault, room_with_dwellers["room"])
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


@pytest.mark.parametrize(("success", "post_origin"), [(True, True), (False, True), (True, False), (False, False)])
async def test_manual_responder_returns_to_original_posting(
    async_session, room_with_dwellers, dweller_data, success, post_origin
):
    vault, target = room_with_dwellers["vault"], room_with_dwellers["room"]
    origin = await crud.room.create(async_session, _work_room(vault.id, "Original Work", SPECIALEnum.STRENGTH, 10, 9))
    if post_origin:
        responder = room_with_dwellers["dwellers"][0]
        await dweller_service.move_to_room(async_session, responder.id, origin.id)
    else:
        responder = await crud.dweller.create(async_session, obj_in=DwellerCreate(**dweller_data, vault_id=vault.id))
    incident = await _fire_incident(async_session, vault, target)
    await incident_service.assign_responders(async_session, incident, [responder.id])
    if post_origin:
        roster = await incident_service.get_incident_team_read(async_session, incident.id, vault.id)
        assert roster[0].origin_room_id == origin.id
        # Re-selecting an existing responder must not overwrite their original posting.
        await incident_service.assign_responders(async_session, incident, [responder.id])
    await _finish(async_session, incident, success=success)
    await async_session.refresh(responder)
    member = (await crud.team_crud.get_incident_team(async_session, incident.id, vault.id))[0]
    assert member.status == "completed"
    if post_origin:
        assert responder.room_id == origin.id
        assert member.origin_room_id == origin.id
    else:
        assert responder.room_id is None
        assert responder.status.value == "idle"
        assert member.origin_room_id is None


@pytest.mark.parametrize("record_origin", [True, False])
async def test_auto_return_does_not_leave_incident_room_over_capacity(
    async_session, room_with_dwellers, dweller_data, record_origin
):
    vault, target = room_with_dwellers["vault"], room_with_dwellers["room"]
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
    incident = await _fire_incident(async_session, vault, target)
    assert len(await hazard_team_service.dispatch_to_incident(async_session, incident)) == 2
    if not record_origin:
        for member in await crud.team_crud.get_incident_team(async_session, incident.id, vault.id):
            member.origin_room_id = None
            async_session.add(member)
        await async_session.commit()
    assert await _finish(async_session, incident) == 2
    assert await crud.dweller.count_in_room(async_session, target.id, include_apprentices=False) == 2
    for responder in responders:
        await async_session.refresh(responder)
        assert responder.room_id == (origin.id if record_origin else None)


@pytest.mark.parametrize("population_full", [False, True])
async def test_full_original_room_leaves_manual_responder_idle_until_retry(
    async_session, room_with_dwellers, dweller_data, population_full
):
    vault, responder = room_with_dwellers["vault"], room_with_dwellers["dwellers"][0]
    origin = await crud.room.create(async_session, _work_room(vault.id, "Original Work", SPECIALEnum.STRENGTH, 10, 9))
    await dweller_service.move_to_room(async_session, responder.id, origin.id)
    incident = await _fire_incident(async_session, vault, room_with_dwellers["room"])
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
        # Under strict total-population capacity the responder is already counted while
        # dispatched; only the origin-room slot matters.
        await crud.vault.update(async_session, vault.id, VaultUpdate(population_max=3))
        await dweller_service.move_to_room(async_session, blockers[0].id, room_with_dwellers["room"].id)
    else:
        await dweller_service.update_dweller(async_session, blockers[0].id, {"room_id": None})
    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 1
    await async_session.refresh(responder)
    assert responder.room_id == origin.id
    assert await crud.incident_crud.get_pending_responder_returns(async_session, vault.id) == []


@pytest.mark.parametrize("new_incident", [False, True])
async def test_finished_return_does_not_override_new_assignment(async_session, room_with_dwellers, new_incident):
    vault, responder = room_with_dwellers["vault"], room_with_dwellers["dwellers"][0]
    origin = await crud.room.create(async_session, _work_room(vault.id, "Original Work", SPECIALEnum.STRENGTH, 10, 9))
    new_room = await crud.room.create(async_session, _work_room(vault.id, "New Posting", SPECIALEnum.STRENGTH, 12, 9))
    await dweller_service.move_to_room(async_session, responder.id, origin.id)
    incident = await _fire_incident(async_session, vault, room_with_dwellers["room"])
    await incident_service.assign_responders(async_session, incident, [responder.id])
    await crud.incident_crud.resolve(async_session, incident.id, success=True)
    if new_incident:
        next_incident = await _fire_incident(async_session, vault, new_room)
        await incident_service.assign_responders(async_session, next_incident, [responder.id])
    else:
        await dweller_service.move_to_room(async_session, responder.id, new_room.id)

    assert await hazard_team_service.return_dispatched_responders(async_session, incident) == 0
    await async_session.refresh(responder)
    assert responder.room_id == new_room.id
    members = await crud.team_crud.get_incident_team(async_session, incident.id, vault.id)
    assert members[0].status == "completed"


async def test_new_incident_in_temporary_room_defers_original_return(async_session, room_with_dwellers):
    vault, target = room_with_dwellers["vault"], room_with_dwellers["room"]
    responder = room_with_dwellers["dwellers"][0]
    origin = await crud.room.create(async_session, _work_room(vault.id, "Original Work", SPECIALEnum.STRENGTH, 10, 9))
    await dweller_service.move_to_room(async_session, responder.id, origin.id)
    first = await _fire_incident(async_session, vault, target)
    await incident_service.assign_responders(async_session, first, [responder.id])
    await crud.incident_crud.resolve(async_session, first.id, success=True)
    second = await _fire_incident(async_session, vault, target)
    assert await hazard_team_service.return_dispatched_responders(async_session, first) == 0
    members = await crud.team_crud.get_incident_team(async_session, first.id, vault.id)
    assert members[0].status == "assigned"
    assert responder.room_id == target.id
    await crud.incident_crud.resolve(async_session, second.id, success=True)
    assert await hazard_team_service.return_dispatched_responders(async_session, first) == 1
    await async_session.refresh(responder)
    assert responder.room_id == origin.id
