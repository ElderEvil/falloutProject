"""Incident spawn presence gating: spawns need a watching player.

The vault overview must have sent a visibility-gated heartbeat inside the presence window.
"""

from datetime import timedelta
from unittest.mock import AsyncMock

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.game_config import game_config
from app.crud import game_state_crud
from app.crud import room as room_crud
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.combat.incident_service import incident_service
from app.tests.factory.dwellers import create_random_common_dweller
from app.utils.time import utcnow


async def _populated_vault(session: AsyncSession, vault: Vault, *, dwellers: int = 5) -> None:
    """Meet the minimum-population spawn precondition with idle adults."""
    for _ in range(dwellers):
        await crud.dweller.create(session, obj_in=DwellerCreate(**create_random_common_dweller(), vault_id=vault.id))


async def _online_game_state(session: AsyncSession, vault: Vault):
    """A recently active game state; presence set per test."""
    state = await game_state_crud.get_or_create(session, vault.id)
    state.last_activity_time = utcnow()
    return state


@pytest.mark.asyncio
@pytest.mark.parametrize(("minutes_ago", "expected"), [(None, False), (0, True), (10, False)])
async def test_spawn_requires_fresh_presence(async_session: AsyncSession, vault: Vault, minutes_ago, expected) -> None:
    await _populated_vault(async_session, vault)
    state = await _online_game_state(async_session, vault)
    if minutes_ago is None:
        assert state.last_presence_at is None
    else:
        state.last_presence_at = utcnow() - timedelta(minutes=minutes_ago)
    assert await incident_service.should_spawn_incident(async_session, vault.id, 3600, state) is expected


def test_spawn_rate_tiers_scale_with_room_count() -> None:
    rate = game_config.incident.get_spawn_rate
    assert rate(12) == 1.0
    assert rate(15) == 1.0
    assert rate(16) == 2.0
    assert rate(30) == 2.0
    assert rate(31) == 4.0
    assert rate(200) == 4.0


@pytest.mark.asyncio
async def test_developed_vault_spawns_where_a_starter_vault_does_not(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    await _populated_vault(async_session, vault)
    state = await _online_game_state(async_session, vault)
    state.last_presence_at = utcnow()
    monkeypatch.setattr("random.random", lambda: 0.75)
    monkeypatch.setattr(room_crud, "count_by_vault", AsyncMock(return_value=12))
    assert await incident_service.should_spawn_incident(async_session, vault.id, 1800, state) is False
    monkeypatch.setattr(room_crud, "count_by_vault", AsyncMock(return_value=40))
    assert await incident_service.should_spawn_incident(async_session, vault.id, 1800, state) is True


@pytest.mark.asyncio
async def test_dead_and_archived_dwellers_do_not_satisfy_the_population_gate(
    async_session: AsyncSession, vault: Vault, monkeypatch: pytest.MonkeyPatch
) -> None:
    state = await _online_game_state(async_session, vault)
    state.last_presence_at = utcnow()
    monkeypatch.setattr("random.random", lambda: 0.0)
    dwellers = [
        await crud.dweller.create(
            async_session, obj_in=DwellerCreate(**create_random_common_dweller(), vault_id=vault.id)
        )
        for _ in range(8)
    ]
    for dweller in dwellers[4:]:
        dweller.is_dead = True
        async_session.add(dweller)
    await async_session.commit()
    assert await crud.dweller.count_in_vault(async_session, vault.id) == 8
    assert await crud.dweller.count_living_in_vault(async_session, vault.id) == 4
    assert await incident_service.should_spawn_incident(async_session, vault.id, 3600, state) is False
