"""Cadence gating for the wall-clock crafting checker."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import pytest

from app.core.config import settings
from app.core.game_config import game_config
from app.services.game_tick import crafting_tick


def test_crafting_advance_due_runs_only_on_cadence_boundaries(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CRAFTING_ADVANCE_EVERY_N_TICKS", 5)
    monkeypatch.setattr(game_config.game_loop, "tick_interval", 60)

    assert not crafting_tick.crafting_advance_due(total_game_time=240, seconds_passed=60)
    assert crafting_tick.crafting_advance_due(total_game_time=300, seconds_passed=60)
    assert crafting_tick.crafting_advance_due(total_game_time=3600, seconds_passed=3000)


def test_crafting_advance_due_runs_every_tick_when_cadence_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CRAFTING_ADVANCE_EVERY_N_TICKS", 1)
    monkeypatch.setattr(game_config.game_loop, "tick_interval", 60)

    assert crafting_tick.crafting_advance_due(total_game_time=60, seconds_passed=60)


@pytest.mark.asyncio
async def test_process_crafting_skips_the_queue_off_cadence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CRAFTING_ADVANCE_EVERY_N_TICKS", 5)
    monkeypatch.setattr(game_config.game_loop, "tick_interval", 60)

    with patch.object(crafting_tick.crafting_service, "advance_orders", new=AsyncMock(return_value=2)) as advance:
        stats = await crafting_tick.process_crafting(AsyncMock(), uuid4(), total_game_time=240, seconds_passed=60)

    assert stats == {"completed": 0}
    advance.assert_not_awaited()


@pytest.mark.asyncio
async def test_process_crafting_runs_the_queue_on_cadence(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "CRAFTING_ADVANCE_EVERY_N_TICKS", 5)
    monkeypatch.setattr(game_config.game_loop, "tick_interval", 60)
    vault_id = uuid4()
    session = AsyncMock()

    with (
        patch.object(crafting_tick.crafting_service, "advance_orders", new=AsyncMock(return_value=2)) as advance,
        patch("app.services.notification_service.notification_service.notify_owner", new=AsyncMock()),
    ):
        stats = await crafting_tick.process_crafting(session, vault_id, total_game_time=300, seconds_passed=60)

    assert stats == {"completed": 2}
    advance.assert_awaited_once_with(session, vault_id)
