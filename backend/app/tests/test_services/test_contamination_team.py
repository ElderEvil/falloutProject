"""Tests for earned hazard teams: participation, qualification, and the bench."""

from unittest.mock import patch

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import HazardTeam
from app.models.hazard_team import ACTIVE_STATUS, RESERVE_STATUS
from app.models.incident import IncidentType
from app.schemas.dweller import DwellerCreate
from app.services.combat.incident_service import incident_service
from app.services.contamination_team_service import (
    QUALIFYING_INCIDENTS,
    TEAM_SIZE,
    contamination_team_service,
)


async def _raise_incident(session: AsyncSession, room, incident_type: IncidentType):
    return await crud.incident_crud.create(
        session, vault_id=room.vault_id, room_id=room.id, incident_type=incident_type, difficulty=2
    )


async def _fight(session: AsyncSession, room, incident_type: IncidentType, dwellers: list):
    """Give each dweller one callout against the given hazard and persist it."""
    incident = await _raise_incident(session, room, incident_type)
    await contamination_team_service.record_participation(session, incident, dwellers)
    await session.commit()
    return incident


@pytest.mark.asyncio
async def test_participation_is_recorded_once_per_incident(async_session: AsyncSession, room_with_dwellers: dict):
    """A long incident credits a defender once, however many rounds they fight."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    incident = await _raise_incident(async_session, room, IncidentType.FIRE)
    dweller_ids = [dweller.id for dweller in dwellers]

    first = await crud.incident_participant_crud.record(async_session, incident.id, dweller_ids)
    second = await crud.incident_participant_crud.record(async_session, incident.id, dweller_ids)
    await async_session.commit()

    assert sorted(first) == sorted(dweller_ids)
    assert second == []
    credited = await crud.incident_participant_crud.get_credited_dweller_ids(async_session, incident.id)
    assert credited == set(dweller_ids)


@pytest.mark.asyncio
async def test_third_callout_earns_an_active_place_and_a_bio_entry(
    async_session: AsyncSession, room_with_dwellers: dict
):
    """Qualification lands on the third contamination incident, and is written into the bio."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    for _ in range(QUALIFYING_INCIDENTS - 1):
        await _fight(async_session, room, IncidentType.FIRE, [dweller])

    assert await crud.hazard_team_crud.get_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id) is None

    await _fight(async_session, room, IncidentType.FIRE, [dweller])

    place = await crud.hazard_team_crud.get_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    assert place is not None
    assert place.status == ACTIVE_STATUS

    await async_session.refresh(dweller)
    service_entries = [entry for entry in dweller.bio_entries if entry["source"] == "hazard"]
    assert len(service_entries) == 1
    assert "fire team" in service_entries[0]["text"]
    assert service_entries[0]["ref"]["team"] == HazardTeam.FIRE.value


@pytest.mark.asyncio
async def test_fourth_qualifier_waits_on_the_bench(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """The team holds three places; anyone who qualifies after that is benched."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )

    for _ in range(QUALIFYING_INCIDENTS):
        await _fight(async_session, room, IncidentType.FIRE, dwellers)

    roster = await crud.hazard_team_crud.get_team(async_session, room.vault_id, HazardTeam.FIRE)
    assert len(roster) == TEAM_SIZE + 1
    assert sum(1 for place in roster if place.status == ACTIVE_STATUS) == TEAM_SIZE
    assert sum(1 for place in roster if place.status == RESERVE_STATUS) == 1


@pytest.mark.asyncio
async def test_fallen_member_frees_a_place_for_the_bench(
    async_session: AsyncSession, room_with_dwellers: dict, dweller_data: dict
):
    """A dead member stops holding a place, and the most senior bench member steps up."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    while len(dwellers) <= TEAM_SIZE:
        dwellers.append(
            await crud.dweller.create(
                async_session,
                obj_in=DwellerCreate(**dweller_data, vault_id=room.vault_id, room_id=room.id),
            )
        )

    for _ in range(QUALIFYING_INCIDENTS):
        await _fight(async_session, room, IncidentType.FIRE, dwellers)

    roster = await crud.hazard_team_crud.get_team(async_session, room.vault_id, HazardTeam.FIRE)
    active_place = next(place for place in roster if place.status == ACTIVE_STATUS)
    benched = next(place for place in roster if place.status == RESERVE_STATUS)

    fallen = await crud.dweller.get(async_session, active_place.dweller_id)
    fallen.is_dead = True
    async_session.add(fallen)
    await async_session.commit()

    await _fight(async_session, room, IncidentType.FIRE, [dwellers[0]])

    stepped_up = await crud.hazard_team_crud.get_member(
        async_session, room.vault_id, HazardTeam.FIRE, benched.dweller_id
    )
    assert stepped_up.status == ACTIVE_STATUS
    assert await crud.hazard_team_crud.count_active(async_session, room.vault_id, HazardTeam.FIRE) == TEAM_SIZE
    roster = await crud.hazard_team_crud.get_team(async_session, room.vault_id, HazardTeam.FIRE)
    assert active_place.dweller_id not in {place.dweller_id for place in roster}


@pytest.mark.asyncio
async def test_intruder_incidents_earn_no_team_place(async_session: AsyncSession, room_with_dwellers: dict):
    """Participation is always recorded, but only contamination hazards build a team."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    for _ in range(QUALIFYING_INCIDENTS + 1):
        await _fight(async_session, room, IncidentType.RAIDER_ATTACK, [dweller])

    for team in HazardTeam:
        assert await crud.hazard_team_crud.get_member(async_session, room.vault_id, team, dweller.id) is None
    fought = await crud.incident_participant_crud.count_incidents(
        async_session, dweller.id, frozenset({IncidentType.RAIDER_ATTACK})
    )
    assert fought == QUALIFYING_INCIDENTS + 1


@pytest.mark.asyncio
async def test_hazard_teams_are_tracked_separately(async_session: AsyncSession, room_with_dwellers: dict):
    """Fire and radiation callouts are counted apart, so a dweller can hold both places."""
    room = room_with_dwellers["room"]
    dweller = room_with_dwellers["dwellers"][0]

    for _ in range(QUALIFYING_INCIDENTS):
        await _fight(async_session, room, IncidentType.FIRE, [dweller])
    for _ in range(QUALIFYING_INCIDENTS):
        await _fight(async_session, room, IncidentType.RADSCORPION_ATTACK, [dweller])

    fire = await crud.hazard_team_crud.get_member(async_session, room.vault_id, HazardTeam.FIRE, dweller.id)
    radiation = await crud.hazard_team_crud.get_member(async_session, room.vault_id, HazardTeam.RADIATION, dweller.id)
    assert fire is not None
    assert radiation is not None


@pytest.mark.asyncio
async def test_incident_round_credits_its_defenders(async_session: AsyncSession, room_with_dwellers: dict):
    """A real combat round writes the participation that the rule reads."""
    room = room_with_dwellers["room"]
    dwellers = room_with_dwellers["dwellers"]
    incident = await _raise_incident(async_session, room, IncidentType.FIRE)

    await incident_service.process_incident(async_session, incident, 2)

    credited = await crud.incident_participant_crud.get_credited_dweller_ids(async_session, incident.id)
    assert credited == {dweller.id for dweller in dwellers}


@pytest.mark.asyncio
async def test_qualifying_round_still_commits_exactly_once(async_session: AsyncSession, room_with_dwellers: dict):
    """Earning a place during a round must not add a commit to that round."""
    room = room_with_dwellers["room"]
    dwellers = list(room_with_dwellers["dwellers"])
    for _ in range(QUALIFYING_INCIDENTS - 1):
        await _fight(async_session, room, IncidentType.FIRE, dwellers)

    incident = await _raise_incident(async_session, room, IncidentType.FIRE)
    await async_session.commit()

    with (
        patch.object(async_session, "commit", wraps=async_session.commit) as commit_spy,
        patch("app.services.combat.incident_math.damage_to_dwellers", return_value=0.0),
        patch("app.services.combat.incident_math.fire_suppression", return_value=0.0),
    ):
        await incident_service.process_incident(async_session, incident, 2)

    assert commit_spy.await_count == 1
    place = await crud.hazard_team_crud.get_member(async_session, room.vault_id, HazardTeam.FIRE, dwellers[0].id)
    assert place is not None
    assert place.status == ACTIVE_STATUS


@pytest.mark.asyncio
async def test_roster_reports_both_teams(async_session: AsyncSession, room_with_dwellers: dict):
    """The roster reads every team, even the ones nobody has qualified for yet."""
    room = room_with_dwellers["room"]

    roster = await contamination_team_service.get_roster(async_session, room.vault_id)

    assert {entry.team for entry in roster.teams} == set(HazardTeam)
    assert all(entry.active == [] and entry.reserve == [] for entry in roster.teams)
