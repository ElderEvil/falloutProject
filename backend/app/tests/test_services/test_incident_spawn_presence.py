"""Incident spawn presence gating (game balance): spawns need a watching player.

Spawns previously required only loose online activity, so background tabs
kept starting incidents nobody would answer. Now the vault overview must have
sent a visibility-gated heartbeat inside the presence window.
"""

from datetime import datetime, timedelta

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.combat.incident_service import incident_service
from app.tests.factory.dwellers import create_random_common_dweller


async def _populated_vault(session: AsyncSession, vault: Vault, *, dwellers: int = 5) -> None:
    """Meet the minimum-population spawn precondition with idle adults."""
    for _ in range(dwellers):
        await crud.dweller.create(
            session, obj_in=DwellerCreate(**create_random_common_dweller(), vault_id=vault.id)
        )


async def _online_game_state(session: AsyncSession, vault: Vault):
    """A recently active game state; presence set per test."""
    from app.crud import game_state_crud

    state = await game_state_crud.get_or_create(session, vault.id)
    state.last_activity_time = datetime.utcnow()
    return state


@pytest.mark.asyncio
async def test_spawn_suppressed_without_presence(async_session: AsyncSession, vault: Vault) -> None:
    """No heartbeat, no incident — even with population, online status, and full chance."""
    await _populated_vault(async_session, vault)
    state = await _online_game_state(async_session, vault)
    assert state.last_presence_at is None

    assert await incident_service.should_spawn_incident(async_session, vault.id, 3600, state) is False


@pytest.mark.asyncio
async def test_spawn_allowed_with_fresh_presence(async_session: AsyncSession, vault: Vault) -> None:
    """A watching player (heartbeat inside the window) keeps the full spawn chance."""
    await _populated_vault(async_session, vault)
    state = await _online_game_state(async_session, vault)
    state.last_presence_at = datetime.utcnow()

    assert await incident_service.should_spawn_incident(async_session, vault.id, 3600, state) is True


@pytest.mark.asyncio
async def test_spawn_suppressed_with_stale_presence(async_session: AsyncSession, vault: Vault) -> None:
    """A tab left open but unseen lapses out of the window and spawns nothing."""
    await _populated_vault(async_session, vault)
    state = await _online_game_state(async_session, vault)
    state.last_presence_at = datetime.utcnow() - timedelta(minutes=10)

    assert await incident_service.should_spawn_incident(async_session, vault.id, 3600, state) is False
