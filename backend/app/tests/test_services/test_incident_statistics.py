from datetime import datetime, timedelta

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import IncidentStatus, IncidentType, WorldEventStatus
from app.crud.user_profile import profile_crud
from app.models.world_event import WorldEvent, WorldEventParticipation
from app.services.combat import incident_math, incident_round
from app.services.combat.incident_service import incident_service
from app.tests.test_services._hazard_team_helpers import empty_room, full_health, raise_incident
from app.utils.time import utcnow


async def _profile(session: AsyncSession, vault):
    """Ensure the vault owner's profile row exists (created at registration in prod)."""
    profile = await profile_crud.get_by_user_id(session, vault.user_id)
    if profile is None:
        profile = await profile_crud.create_for_user(session, vault.user_id)
    return profile


@pytest.mark.asyncio
async def test_spawn_counts_a_happened_incident(async_session: AsyncSession, room_with_dwellers: dict) -> None:
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
    room = await empty_room(async_session, vault.id)
    await _profile(async_session, vault)
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    incident.start_time = utcnow() - timedelta(hours=1)

    await incident_service.process_incident(async_session, incident, 2)

    assert incident.status.value == "failed"
    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    assert profile.total_incidents_lost == 1
    assert profile.total_incidents_won == 0


@pytest.mark.asyncio
async def test_spread_counts_a_happened_incident(
    async_session: AsyncSession, vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core.game_config import game_config

    monkeypatch.setattr(game_config.incident, "max_spread_count", 1)
    source = await empty_room(async_session, vault.id, name="Source", x=7)
    neighbor = await empty_room(async_session, vault.id, name="Neighbor", x=9)
    await _profile(async_session, vault)
    incident = await raise_incident(async_session, source, IncidentType.RADROACH_INFESTATION)
    incident.start_time = utcnow() - timedelta(hours=1)

    await incident_service.process_incident(async_session, incident, 2)

    rows = await crud.incident_crud.get_active_by_vault(async_session, vault.id)
    assert {row.room_id for row in rows} == {source.id, neighbor.id}
    profile = await profile_crud.get_by_user_id(async_session, vault.user_id)
    assert profile.total_incidents == 1


async def _create_world_event(async_session: AsyncSession) -> WorldEvent:
    now = utcnow()
    event = WorldEvent(
        kind="migration",
        title="Migration surge",
        description="Creatures are on the move.",
        target_amount=100,
        personal_min=0,
        reward=[],
        starts_at=now - timedelta(hours=1),
        ends_at=now + timedelta(hours=1),
        status=WorldEventStatus.ACTIVE,
    )
    async_session.add(event)
    await async_session.commit()
    await async_session.refresh(event)
    return event


async def _world_event_totals(async_session: AsyncSession, event_id, vault_id) -> tuple[int, int]:
    """(shared event progress, this vault's contribution)."""
    event = await async_session.get(WorldEvent, event_id)
    rows = (
        (
            await async_session.execute(
                select(WorldEventParticipation).where(
                    WorldEventParticipation.world_event_id == event_id,
                    WorldEventParticipation.vault_id == vault_id,
                )
            )
        )
        .scalars()
        .all()
    )
    return event.progress_amount, sum(row.contribution for row in rows)


async def _won_fight(async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch):
    """One round to victory: responders' return fire is made overwhelming."""
    room = room_with_dwellers["room"]
    await full_health(async_session, room_with_dwellers["dwellers"])
    await _profile(async_session, room_with_dwellers["vault"])
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    monkeypatch.setattr(incident_math, "damage_to_raiders", lambda _power, _seconds: 10_000.0)
    await incident_service.process_incident(async_session, incident, 2)
    return incident


@pytest.mark.asyncio
async def test_won_incident_credits_active_world_event_once(
    async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_id = room_with_dwellers["vault"].id
    event = await _create_world_event(async_session)

    incident = await _won_fight(async_session, room_with_dwellers, monkeypatch)

    assert incident.status == IncidentStatus.RESOLVED
    totals = await _world_event_totals(async_session, event.id, vault_id)
    assert totals == (1, 1)

    await incident_service.process_incident(async_session, incident, 2)

    assert await _world_event_totals(async_session, event.id, vault_id) == totals


@pytest.mark.asyncio
async def test_undecided_incident_round_credits_nothing(
    async_session: AsyncSession, room_with_dwellers: dict, monkeypatch: pytest.MonkeyPatch
) -> None:
    vault_id = room_with_dwellers["vault"].id
    event = await _create_world_event(async_session)
    room = room_with_dwellers["room"]
    await full_health(async_session, room_with_dwellers["dwellers"])
    await _profile(async_session, room_with_dwellers["vault"])
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    monkeypatch.setattr(incident_math, "damage_to_raiders", lambda _power, _seconds: 0.0)

    await incident_service.process_incident(async_session, incident, 2)

    assert incident.status == IncidentStatus.ACTIVE
    assert await _world_event_totals(async_session, event.id, vault_id) == (0, 0)


@pytest.mark.asyncio
async def test_failed_incident_credits_nothing(async_session: AsyncSession, vault) -> None:
    event = await _create_world_event(async_session)
    room = await empty_room(async_session, vault.id)
    await _profile(async_session, vault)
    incident = await raise_incident(async_session, room, IncidentType.RAIDER_ATTACK)
    incident.start_time = utcnow() - timedelta(hours=1)

    await incident_service.process_incident(async_session, incident, 2)

    assert incident.status == IncidentStatus.FAILED
    assert await _world_event_totals(async_session, event.id, vault.id) == (0, 0)
    rows = (
        (
            await async_session.execute(
                select(WorldEventParticipation).where(WorldEventParticipation.vault_id == vault.id)
            )
        )
        .scalars()
        .all()
    )
    assert rows == []
