"""Tests for game loop vault events (Phase 5)."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncConnection
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.core.enums import IncidentType
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.vault import Vault
from app.schemas.dweller import DwellerCreate
from app.services.game_loop_service import game_loop_service
from app.tests.factory.dwellers import create_fake_dweller
from app.utils.time import utcnow


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
    game_state = GameState(vault_id=vault.id, last_activity_time=utcnow() - timedelta(minutes=11))

    result = await game_loop_service._process_events(async_session, vault.id, 3600, game_state)

    assert result == {"triggered": 0, "events": []}


@pytest.mark.asyncio
async def test_process_events_spawn_chance_miss_returns_empty(async_session: AsyncSession, vault: Vault):
    """Events must not trigger when the spawn chance roll fails."""
    await _create_dwellers(async_session, vault, count=3)

    with patch("app.services.game_loop_service.random") as mock_random:
        mock_random.random.return_value = 0.99
        result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result == {"triggered": 0, "events": []}


@pytest.mark.asyncio
async def test_process_events_resource_cache_awards_caps_and_notifies(async_session: AsyncSession, vault: Vault):
    """Resource cache events deposit caps and send a notification."""
    await _create_dwellers(async_session, vault, count=3)
    initial_caps = vault.bottle_caps

    with (
        patch("app.services.game_loop_service.random") as mock_random,
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
async def test_process_events_award_locks_vault_before_deposit(
    async_session: AsyncSession, db_connection: AsyncConnection, vault: Vault
):
    """The caps award must read the vault under the row lock revivals use.

    deposit_caps writes an absolute balance; an unlocked read could overwrite a
    concurrent revival deduction. SQLite renders no FOR UPDATE text, so observe
    the ORM statement's lock clause structurally and assert the persisted balance.
    """
    await _create_dwellers(async_session, vault, count=3)
    initial_caps = vault.bottle_caps

    statements: list[tuple[str, bool]] = []

    def record(_connection, _cursor, statement, _parameters, context, _executemany):
        original = getattr(getattr(context, "compiled", None), "statement", None)
        locked = getattr(original, "_for_update_arg", None) is not None
        statements.append((statement, locked))

    event.listen(db_connection.sync_connection, "before_cursor_execute", record)
    try:
        with (
            patch("app.services.game_loop_service.random") as mock_random,
            patch("app.services.notification_service.notification_service") as mock_notification_service,
        ):
            mock_random.random.return_value = 0.0
            mock_random.choices.return_value = ["resource_cache"]
            mock_random.randint.return_value = 50
            mock_notification_service.create_and_send = AsyncMock()

            result = await game_loop_service._process_events(async_session, vault.id, 3600)
    finally:
        event.remove(db_connection.sync_connection, "before_cursor_execute", record)

    assert result["triggered"] == 1
    locked_vault_reads = [i for i, (sql, locked) in enumerate(statements) if locked and sql.startswith("SELECT vault.")]
    vault_updates = [i for i, (sql, _) in enumerate(statements) if sql.startswith("UPDATE vault ")]
    assert locked_vault_reads, "the award must read the vault row FOR UPDATE"
    assert vault_updates, "the award must write the new balance"
    assert locked_vault_reads[0] < vault_updates[0], "the locked read must precede the caps write"

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 50


@pytest.mark.asyncio
async def test_process_events_wanderer_awards_caps_and_notifies(async_session: AsyncSession, vault: Vault):
    """Wanderer events deposit caps and send a notification."""
    await _create_dwellers(async_session, vault, count=3)
    initial_caps = vault.bottle_caps

    with (
        patch("app.services.game_loop_service.random") as mock_random,
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
        patch("app.services.game_loop_service.random") as mock_random,
        patch("app.services.combat.incident_service.incident_service") as mock_incident_service,
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
