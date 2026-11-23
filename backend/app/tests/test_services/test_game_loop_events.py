from contextlib import contextmanager
from datetime import timedelta
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


async def _create_dwellers(async_session, vault, count: int = 3) -> list[Dweller]:
    dwellers = []
    for _ in range(count):
        data = create_fake_dweller() | {"vault_id": vault.id}
        dwellers.append(await crud.dweller.create(async_session, DwellerCreate(**data)))
    return dwellers


@contextmanager
def _forced_event(kind: str, caps: int = 0):
    """Force a successful spawn roll that always picks ``kind``."""
    with (
        patch("app.services.game_loop_service.random") as rng,
        patch("app.services.notification_service.notification_service") as notify,
    ):
        rng.random.return_value = 0.0
        rng.choices.return_value = [kind]
        rng.randint.return_value = caps
        notify.create_and_send = AsyncMock()
        yield notify


@pytest.mark.parametrize("offline", [True, False], ids=["offline_vault", "spawn_chance_miss"])
async def test_process_events_returns_empty(async_session, vault, offline):
    if offline:
        game_state = GameState(vault_id=vault.id, last_activity_time=utcnow() - timedelta(minutes=11))
        result = await game_loop_service._process_events(async_session, vault.id, 3600, game_state)
    else:
        await _create_dwellers(async_session, vault, count=3)
        with patch("app.services.game_loop_service.random") as mock_random:
            mock_random.random.return_value = 0.99
            result = await game_loop_service._process_events(async_session, vault.id, 3600)
    assert result == {"triggered": 0, "events": []}


async def test_process_events_wanderer_awards_caps_and_notifies(async_session, vault):
    await _create_dwellers(async_session, vault, count=3)
    initial_caps = vault.bottle_caps

    with _forced_event("wanderer", 25) as notify:
        result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result["triggered"] == 1
    assert result["events"] == [{"type": "wanderer", "caps": 25}]
    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 25
    notify.create_and_send.assert_awaited_once()


async def test_process_events_cache_award_locks_vault_before_deposit(async_session, db_connection, vault):
    # deposit_caps writes an absolute balance, so an unlocked read could clobber a
    # concurrent revival deduction. SQLite renders no FOR UPDATE text, so assert the
    # lock clause structurally and the persisted balance.
    await _create_dwellers(async_session, vault, count=3)
    initial_caps = vault.bottle_caps
    statements: list[tuple[str, bool]] = []

    def record(_conn, _cursor, statement, _params, context, _many):
        compiled = getattr(getattr(context, "compiled", None), "statement", None)
        statements.append((statement, getattr(compiled, "_for_update_arg", None) is not None))

    event.listen(db_connection.sync_connection, "before_cursor_execute", record)
    try:
        with _forced_event("resource_cache", 50):
            result = await game_loop_service._process_events(async_session, vault.id, 3600)
    finally:
        event.remove(db_connection.sync_connection, "before_cursor_execute", record)

    assert result["triggered"] == 1
    assert result["events"] == [{"type": "resource_cache", "caps": 50}]
    locked_reads = [i for i, (sql, locked) in enumerate(statements) if locked and sql.startswith("SELECT vault.")]
    vault_updates = [i for i, (sql, _) in enumerate(statements) if sql.startswith("UPDATE vault ")]
    assert locked_reads, "the award must read the vault row FOR UPDATE"
    assert vault_updates, "the award must write the new balance"
    assert locked_reads[0] < vault_updates[0], "the locked read must precede the caps write"

    await async_session.refresh(vault)
    assert vault.bottle_caps == initial_caps + 50


async def test_process_events_raider_scout_spawns_incident(async_session, vault):
    await _create_dwellers(async_session, vault, count=3)
    incident_id = uuid4()

    with (
        patch("app.services.game_loop_service.random") as rng,
        patch("app.services.combat.incident_service.incident_service") as incident_service,
    ):
        rng.random.return_value = 0.0
        rng.choices.return_value = ["raider_scout"]
        incident_service.spawn_incident = AsyncMock(return_value=MagicMock(id=incident_id))
        result = await game_loop_service._process_events(async_session, vault.id, 3600)

    assert result["triggered"] == 1
    assert result["events"] == [{"type": "raider_scout", "incident_id": str(incident_id)}]
    incident_service.spawn_incident.assert_awaited_once_with(async_session, vault.id, IncidentType.RADSCORPION_ATTACK)
