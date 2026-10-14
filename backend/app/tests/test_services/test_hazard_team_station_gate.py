"""Formation gating: a hazard team needs a Response Station (issue #997, task 23).

The maintainer's locked decision: the station gates team formation — a dweller
cannot join or be promoted into a fire/radiation team until the station exists.
These tests exercise the real membership-mutation paths in ``hazard_team_service``
and assert the resulting membership, not just a raised exception.
"""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.incident import IncidentType
from app.models.team import ACTIVE_STATUS, RESERVE_STATUS
from app.schemas.dweller import DwellerCreate
from app.services.dweller_service import dweller_service
from app.services.hazard_team_service import QUALIFYING_INCIDENTS, hazard_team_service
from app.tests.test_services._hazard_team_helpers import ensure_station, make_member, raise_incident
from app.utils.exceptions import ValidationException


async def _join_attempt(async_session: AsyncSession, room, dweller) -> None:
    """Run the qualifying callouts through the real automatic-join path and persist."""
    for _ in range(QUALIFYING_INCIDENTS):
        incident = await raise_incident(async_session, room, IncidentType.FIRE)
        await hazard_team_service.record_participation(async_session, incident, [dweller])
    await async_session.commit()


@pytest.mark.asyncio
async def test_join_is_refused_without_a_response_station(async_session: AsyncSession, room_with_dwellers: dict):
    """A fully-qualified defender earns no place while the vault has no station."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    await _join_attempt(async_session, room, dweller)

    assert await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id) is None
    assert await crud.team_crud.get_hazard_team(async_session, room.vault_id, HazardTeam.FIRE) == []


@pytest.mark.asyncio
async def test_join_succeeds_once_a_response_station_exists(async_session: AsyncSession, room_with_dwellers: dict):
    """With a station standing, the same qualifying callouts earn the active place."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    await ensure_station(async_session, room.vault_id)

    await _join_attempt(async_session, room, dweller)

    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place is not None
    assert place.status == ACTIVE_STATUS


@pytest.mark.asyncio
async def test_promotion_is_refused_without_a_response_station(async_session: AsyncSession, room_with_dwellers: dict):
    """A bench member cannot be promoted to an active place while no station exists."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)

    with pytest.raises(ValidationException):
        await hazard_team_service.set_place(async_session, room.vault_id, HazardTeam.FIRE, dweller.id, active=True)

    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place.status == RESERVE_STATUS


@pytest.mark.asyncio
async def test_promotion_succeeds_once_a_response_station_exists(async_session: AsyncSession, room_with_dwellers: dict):
    """With a station standing, the bench member steps up to an active place."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    await make_member(async_session, room.vault_id, dweller.id, HazardTeam.FIRE, RESERVE_STATUS)
    await ensure_station(async_session, room.vault_id)

    roster = await hazard_team_service.set_place(async_session, room.vault_id, HazardTeam.FIRE, dweller.id, active=True)

    fire = next(entry for entry in roster.teams if entry.team == HazardTeam.FIRE)
    assert dweller.id in {place.dweller_id for place in fire.active}
    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place.status == ACTIVE_STATUS


@pytest.mark.asyncio
async def test_round_does_not_promote_a_bench_member_without_a_station(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """The automatic round path never promotes a bench member while no station exists.

    The bench member holds a legacy place (as if the station had been demolished);
    a fresh round must leave them on the bench rather than step them up.
    """
    room = room_with_dwellers["room"]
    benched = room_with_dwellers["dwellers"][0]
    fighter = room_with_dwellers["dwellers"][1]
    await make_member(async_session, room.vault_id, benched.id, HazardTeam.FIRE, RESERVE_STATUS)
    await make_member(async_session, room.vault_id, fighter.id, HazardTeam.FIRE, ACTIVE_STATUS)
    newcomer = await crud.dweller.create(
        async_session,
        obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
    )

    incident = await raise_incident(async_session, room, IncidentType.FIRE)
    await hazard_team_service.record_participation(async_session, incident, [newcomer])
    await async_session.commit()

    place = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, benched.id)
    assert place.status == RESERVE_STATUS


@pytest.mark.asyncio
async def test_demolition_keeps_places_but_blocks_further_promotion(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """Demolishing the station leaves earned places standing yet refuses new promotions."""
    room = room_with_dwellers["room"]
    veteran = room_with_dwellers["dwellers"][0]
    benched = room_with_dwellers["dwellers"][1]
    station = await ensure_station(async_session, room.vault_id)
    await _join_attempt(async_session, room, veteran)
    await make_member(async_session, room.vault_id, benched.id, HazardTeam.FIRE, RESERVE_STATUS)

    await async_session.delete(station)
    await async_session.commit()

    survived = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, veteran.id)
    assert survived is not None
    assert survived.status == ACTIVE_STATUS

    with pytest.raises(ValidationException):
        await hazard_team_service.set_place(async_session, room.vault_id, HazardTeam.FIRE, benched.id, active=True)
    still_benched = await crud.team_crud.get_hazard_member(async_session, room.vault_id, HazardTeam.FIRE, benched.id)
    assert still_benched.status == RESERVE_STATUS


@pytest.mark.asyncio
async def test_assignment_to_the_station_grants_no_membership(async_session: AsyncSession, room_with_dwellers: dict):
    """Stationing a dweller at the station never joins them to a hazard team."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]
    station = await ensure_station(async_session, room.vault_id)

    await dweller_service.move_to_room(async_session, dweller.id, station.id)

    for team in HazardTeam:
        assert await crud.team_crud.get_hazard_member(async_session, room.vault_id, team, dweller.id) is None
