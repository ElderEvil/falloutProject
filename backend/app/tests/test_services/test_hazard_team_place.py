import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.schemas.dweller import DwellerCreate
from app.services.hazard_team_service import TEAM_SIZE, hazard_team_service
from app.tests.test_services._hazard_team_helpers import ensure_station, make_member
from app.utils.exceptions import ResourceConflictException, ResourceNotFoundException


async def _dwellers_for_team(async_session, room_with_dwellers, dweller_data, count):
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) < count:
        dwellers.append(
            await crud.dweller.create(
                async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id)
            )
        )
    return dwellers


async def _place(session, room, dwellers, status):
    for dweller in dwellers:
        await make_member(session, room.vault_id, dweller.id, HazardTeam.FIRE, status)


def _fire(roster):
    return next(entry for entry in roster.teams if entry.team == HazardTeam.FIRE)


def _ids(places):
    return {place.dweller_id for place in places}


async def _set_place(session, room, dweller, *, active):
    return await hazard_team_service.set_place(session, room.vault_id, HazardTeam.FIRE, dweller.id, active=active)


async def _slot(dweller_id, room, session):
    place = await crud.team_crud.get_hazard_member(session, room.vault_id, HazardTeam.FIRE, dweller_id)
    return place.status, place.slot_number


@pytest.mark.parametrize(("active_count", "full"), [(2, False), (TEAM_SIZE, True)])
async def test_activating_a_reserve_member(async_session, room_with_dwellers, dweller_data, active_count, full):
    room = room_with_dwellers["room"]
    dwellers = await _dwellers_for_team(async_session, room_with_dwellers, dweller_data, TEAM_SIZE + 1)
    await ensure_station(async_session, room.vault_id)
    await _place(async_session, room, dwellers[:active_count], ACTIVE_STATUS)
    await _place(async_session, room, dwellers[active_count : active_count + 1], RESERVE_STATUS)
    reserve = dwellers[active_count]

    if full:
        with pytest.raises(ResourceConflictException):
            await _set_place(async_session, room, reserve, active=True)
        return

    fire = _fire(await _set_place(async_session, room, reserve, active=True))

    assert _ids(fire.active) == {dwellers[0].id, dwellers[1].id, reserve.id}
    assert reserve.id not in _ids(fire.reserve)
    active_by_id = {place.dweller_id: place for place in fire.active}
    assert active_by_id[reserve.id].name == reserve.display_name
    assert active_by_id[reserve.id].level == reserve.level
    assert await _slot(reserve.id, room, async_session) == (ACTIVE_STATUS, 3)

    await async_session.refresh(reserve)
    service_entries = [entry for entry in reserve.bio_entries if entry["source"] == "hazard"]
    assert any("Took an active place on the vault's fire team" in entry["text"] for entry in service_entries)


async def test_bench_active_member_leaves_slot_open(async_session, room_with_dwellers, dweller_data):
    room = room_with_dwellers["room"]
    dwellers = await _dwellers_for_team(async_session, room_with_dwellers, dweller_data, TEAM_SIZE + 1)
    await _place(async_session, room, dwellers[:TEAM_SIZE], ACTIVE_STATUS)
    await _place(async_session, room, dwellers[TEAM_SIZE:], RESERVE_STATUS)

    fire = _fire(await _set_place(async_session, room, dwellers[0], active=False))

    assert dwellers[0].id not in _ids(fire.active)
    assert dwellers[0].id in _ids(fire.reserve)
    # The bench member is NOT auto-promoted into the freed slot.
    assert dwellers[TEAM_SIZE].id not in _ids(fire.active)
    assert await _slot(dwellers[0].id, room, async_session) == (RESERVE_STATUS, None)


@pytest.mark.parametrize(("status", "active"), [(ACTIVE_STATUS, True), (RESERVE_STATUS, False)])
async def test_placing_an_already_placed_member_is_idempotent(async_session, room_with_dwellers, status, active):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, status)

    fire = _fire(await _set_place(async_session, room, dweller, active=active))

    expected = fire.active if active else fire.reserve
    assert [place.dweller_id for place in expected] == [dweller.id]
    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place.status == status
    if not active:
        assert place.slot_number is None


async def test_set_place_without_a_place_raises_not_found(async_session, room_with_dwellers):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]

    with pytest.raises(ResourceNotFoundException):
        await _set_place(async_session, room, dweller, active=True)
