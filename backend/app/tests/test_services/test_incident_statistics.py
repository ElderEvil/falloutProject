"""User-profile incident counters (incident balance batch): happened, won, lost."""

from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.crud.user_profile import profile_crud
from app.models.incident import IncidentType
from app.services.combat import incident_round
from app.services.combat.incident_service import incident_service
from app.tests.test_services._hazard_team_helpers import empty_room, raise_incident


async def _profile(session: AsyncSession, vault):
    """Ensure the vault owner's profile row exists (created at registration in prod)."""
    profile = await profile_crud.get_by_user_id(session, vault.user_id)
    if profile is None:
        profile = await profile_crud.create_for_user(session, vault.user_id)
    return profile


@pytest.mark.asyncio
async def test_spawn_counts_a_happened_incident(async_session: AsyncSession, room_with_dwellers: dict) -> None:
    """Spawning an incident bumps the owner's lifetime happened counter once."""
    room = room_with_dwellers["room"]
    vault = room_with_dwellers["vault"]
    await _profile(async_session, vault)

    incident = await incident_service.spawn_incident(
        async_session, vault.id, incident_type=IncidentType.RADROACH_INFESTATION
    )
    assert incident is not None
    assert incident.room_id == room.id

    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    assert profile.total_incidents == 1
    assert profile.total_incidents_won == 0
    assert profile.total_incidents_lost == 0


@pytest.mark.asyncio
async def test_victory_counts_a_won_incident(async_session: AsyncSession, room_with_dwellers: dict) -> None:
    """Resolving an incident successfully bumps the won counter, not the lost one."""
    room = room_with_dwellers["room"]
    vault_id = room_with_dwellers["vault"].id
    dwellers = room_with_dwellers["dwellers"]
    vault = await crud.vault.get(async_session, vault_id)
    await _profile(async_session, vault)
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)

    await incident_round.resolve_victory(async_session, incident, dwellers)

    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    assert profile.total_incidents_won == 1
    assert profile.total_incidents_lost == 0


@pytest.mark.asyncio
async def test_undefended_failure_counts_a_lost_incident(async_session: AsyncSession, vault) -> None:
    """An incident that fails with nobody responding bumps the lost counter."""
    room = await empty_room(async_session, vault.id)
    await _profile(async_session, vault)
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    incident.start_time = datetime.utcnow() - timedelta(hours=1)

    await incident_service.process_incident(async_session, incident, 2)

    assert incident.status.value == "failed"
    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    assert profile.total_incidents_lost == 1
    assert profile.total_incidents_won == 0


@pytest.mark.asyncio
async def test_spread_counts_a_happened_incident(
    async_session: AsyncSession, vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A spread-created incident row counts toward happened, keeping won/lost consistent."""
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.incident, "max_spread_count", 1)
    source = await empty_room(async_session, vault.id, name="Source", x=7)
    neighbor = await empty_room(async_session, vault.id, name="Neighbor", x=9)
    await _profile(async_session, vault)
    incident = await raise_incident(async_session, source, IncidentType.RADROACH_INFESTATION)
    incident.start_time = datetime.utcnow() - timedelta(hours=1)

    await incident_service.process_incident(async_session, incident, 2)

    rows = await crud.incident_crud.get_active_by_vault(async_session, vault.id)
    assert {row.room_id for row in rows} == {source.id, neighbor.id}
    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    assert profile.total_incidents == 1
