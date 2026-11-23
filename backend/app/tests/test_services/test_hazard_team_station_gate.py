import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam, IncidentType, RoomTypeEnum
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.schemas.dweller import DwellerCreate
from app.services.dweller_service import dweller_service
from app.services.hazard_team_service import QUALIFYING_INCIDENTS, hazard_team_service
from app.tests.test_services._hazard_team_helpers import ensure_station, make_member, raise_incident
from app.utils.exceptions import ValidationException


async def _join_attempt(async_session, room, dweller):
    for _ in range(QUALIFYING_INCIDENTS):
        incident = await raise_incident(async_session, room, IncidentType.FIRE)
        await hazard_team_service.record_participation(async_session, incident, [dweller])
    await async_session.commit()


async def _member(async_session, room, dweller):
    return await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)


async def _promote(async_session, room, dweller):
    return await hazard_team_service.set_place(async_session, room.vault_id, HazardTeam.FIRE, dweller.id, active=True)


@pytest.mark.parametrize("station", [False, True])
async def test_join_gate_requires_a_response_station(async_session, room_with_dwellers, station):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    if station:
        await ensure_station(async_session, room.vault_id)

    await _join_attempt(async_session, room, dweller)

    place = await _member(async_session, room, dweller)
    if not station:
        assert place is None
        assert await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE) == []
    else:
        assert place is not None
        assert place.status == ACTIVE_STATUS
        # Stationing a dweller at the station never joins them to a hazard team.
        other = room_with_dwellers["dwellers"][1]
        station = await crud.room.get_by_category(async_session, room.vault_id, RoomTypeEnum.RESPONSE)
        await dweller_service.move_to_room(async_session, other.id, station[0].id)
        for team in HazardTeam:
            assert await crud.team_crud.get_hazard_member(async_session, room.vault_id, team, other.id) is None


@pytest.mark.parametrize("station", [False, True])
async def test_promotion_gate_requires_a_response_station(async_session, room_with_dwellers, station):
    room, dweller = room_with_dwellers["room"], room_with_dwellers["dwellers"][0]
    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)
    if station:
        await ensure_station(async_session, room.vault_id)

    if not station:
        with pytest.raises(ValidationException):
            await _promote(async_session, room, dweller)
        assert (await _member(async_session, room, dweller)).status == RESERVE_STATUS
        return

    roster = await _promote(async_session, room, dweller)
    fire = next(entry for entry in roster.teams if entry.team == HazardTeam.FIRE)
    assert dweller.id in {place.dweller_id for place in fire.active}
    assert (await _member(async_session, room, dweller)).status == ACTIVE_STATUS


async def test_round_does_not_promote_a_bench_member_without_a_station(async_session, room_with_dwellers, dweller_data):
    # The bench member holds a legacy place, as if the station had been demolished.
    room = room_with_dwellers["room"]
    benched, fighter = room_with_dwellers["dwellers"][:2]
    await make_member(async_session, room.vault_id, benched.id, HazardTeam.FIRE, RESERVE_STATUS)
    await make_member(async_session, room.vault_id, fighter.id, HazardTeam.FIRE, ACTIVE_STATUS)
    newcomer = await crud.dweller.create(
        async_session, obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id)
    )

    incident = await raise_incident(async_session, room, IncidentType.FIRE)
    await hazard_team_service.record_participation(async_session, incident, [newcomer])
    await async_session.commit()

    assert (await _member(async_session, room, benched)).status == RESERVE_STATUS


async def test_demolition_keeps_places_but_blocks_further_promotion(async_session, room_with_dwellers):
    room = room_with_dwellers["room"]
    veteran, benched = room_with_dwellers["dwellers"][:2]
    station = await ensure_station(async_session, room.vault_id)
    await _join_attempt(async_session, room, veteran)
    await make_member(async_session, room.vault_id, benched.id, HazardTeam.FIRE, RESERVE_STATUS)

    await async_session.delete(station)
    await async_session.commit()

    survived = await _member(async_session, room, veteran)
    assert survived is not None
    assert survived.status == ACTIVE_STATUS

    with pytest.raises(ValidationException):
        await _promote(async_session, room, benched)
    assert (await _member(async_session, room, benched)).status == RESERVE_STATUS
