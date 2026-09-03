"""Tests for game loop vault events (Phase 5)."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.incident import IncidentType
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.game_loop import game_loop_service
from app.tests.factory.dwellers import create_fake_dweller


async def _create_dwellers(async_session: AsyncSession, vault: Vault, count: int = 3) -> list[Dweller]:
    """Create the given number of dwellers in the vault."""
    dwellers = []
    for _ in range(count):
        data = create_fake_dweller()
        data["vault_id"] = vault.id
        dwellers.append(await crud.dweller.create(async_session, DwellerCreate(**data)))
    return dwellers


@pytest.mark.asyncio
async def test_process_events_offline_vault_returns_empty(async_session: AsyncSession, vault: Vault):
    """Events must not trigger while the user is away from the vault."""
    game_state = GameState(vault_id=vault.id, last_activity_time=datetime.utcnow() - timedelta(minutes=11))

    result = await game_loop_service._process_events(async_session, vault.id, 3600, game_state)

    assert result == {"triggered": 0, "events": []}


@pytest.mark.asyncio
async def test_process_events_below_min_population_returns_empty(async_session: AsyncSession, vault: Vault):
    """Events must not trigger below the minimum vault population."""
    await _create_dwellers(async_session, vault, count=2)

    result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result == {"triggered": 0, "events": []}


@pytest.mark.asyncio
async def test_process_events_spawn_chance_miss_returns_empty(async_session: AsyncSession, vault: Vault):
    """Events must not trigger when the spawn chance roll fails."""
    await _create_dwellers(async_session, vault, count=3)

    with patch("app.services.game_loop.random") as mock_random:
        mock_random.random.return_value = 0.99
        result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result == {"triggered": 0, "events": []}


@pytest.mark.asyncio
async def test_process_events_resource_cache_awards_caps_and_notifies(async_session: AsyncSession, vault: Vault):
    """Resource cache events deposit caps and send a notification."""
    await _create_dwellers(async_session, vault, count=3)
    initial_caps = vault.bottle_caps

    with (
        patch("app.services.game_loop.random") as mock_random,
        patch("app.services.notification_service.notification_service") as mock_notification_service,
    ):
        mock_random.random.return_value = 0.0
        mock_random.choices.return_value = ["resource_cache"]
        mock_random.randint.return_value = 50
        mock_notification_service.create_and_send = AsyncMock()

        result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result["triggered"] == 1
    assert result["events"] == [{"type": "resource_cache", "caps": 50}]
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 50
    mock_notification_service.create_and_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_events_wanderer_awards_caps_and_notifies(async_session: AsyncSession, vault: Vault):
    """Wanderer events deposit caps and send a notification."""
    await _create_dwellers(async_session, vault, count=3)
    initial_caps = vault.bottle_caps

    with (
        patch("app.services.game_loop.random") as mock_random,
        patch("app.services.notification_service.notification_service") as mock_notification_service,
    ):
        mock_random.random.return_value = 0.0
        mock_random.choices.return_value = ["wanderer"]
        mock_random.randint.return_value = 25
        mock_notification_service.create_and_send = AsyncMock()

        result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result["triggered"] == 1
    assert result["events"] == [{"type": "wanderer", "caps": 25}]
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 25
    mock_notification_service.create_and_send.assert_awaited_once()


@pytest.mark.asyncio
async def test_process_events_raider_scout_spawns_incident(async_session: AsyncSession, vault: Vault):
    """Raider scout events attempt to spawn a radscorpion incident."""
    await _create_dwellers(async_session, vault, count=3)
    incident_id = uuid4()

    with (
        patch("app.services.game_loop.random") as mock_random,
        patch("app.services.incident_service.incident_service") as mock_incident_service,
    ):
        mock_random.random.return_value = 0.0
        mock_random.choices.return_value = ["raider_scout"]
        mock_incident_service.spawn_incident = AsyncMock(return_value=MagicMock(id=incident_id))

        result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result["triggered"] == 1
    assert result["events"] == [{"type": "raider_scout", "incident_id": str(incident_id)}]
    mock_incident_service.spawn_incident.assert_awaited_once_with(
        async_session, vault.id, IncidentType.RADSCORPION_ATTACK
    )


@pytest.mark.asyncio
async def test_process_events_raider_scout_no_room_returns_empty(async_session: AsyncSession, vault: Vault):
    """Raider scout events no-op when no incident can be spawned."""
    await _create_dwellers(async_session, vault, count=3)

    with (
        patch("app.services.game_loop.random") as mock_random,
        patch("app.services.incident_service.incident_service") as mock_incident_service,
    ):
        mock_random.random.return_value = 0.0
        mock_random.choices.return_value = ["raider_scout"]
        mock_incident_service.spawn_incident = AsyncMock(return_value=None)

        result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result == {"triggered": 0, "events": []}
