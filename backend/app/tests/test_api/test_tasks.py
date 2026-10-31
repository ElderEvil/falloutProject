"""Tests for scheduled background tasks."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest
from dramatiq.middleware import CurrentMessage

from app.api.tasks import (
    _acquire_vault_tick_lock,
    _check_quest_completion,
    _dispatch_game_tick,
    _process_vault_tick_async,
    _release_vault_tick_lock,
    check_quest_completion,
    game_tick,
)
from app.core.dramatiq import broker
from app.models.pregnancy import Pregnancy
from app.models.vault import Vault
from app.utils.exceptions import ResourceNotFoundException


def test_quest_completion_is_scheduled_every_minute() -> None:
    """Finished quest timers are settled without a player request."""
    assert "periodic" in check_quest_completion.options


def test_current_message_middleware_is_enabled() -> None:
    """The dispatcher needs the current Dramatiq message id for idempotency."""
    assert any(isinstance(middleware, CurrentMessage) for middleware in broker.middleware)


class _FakeTaskSession:
    """Async context manager standing in for ``task_session``."""

    def __init__(self) -> None:
        self.session = AsyncMock()

    async def __aenter__(self) -> AsyncMock:
        return self.session

    async def __aexit__(self, *args) -> None:
        return None


@pytest.mark.asyncio
async def test_check_quest_completion_drives_both_passes() -> None:
    """The cron settles expired quests and finalizes arrived parties in one run."""
    with (
        patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
        patch(
            "app.services.progression.quests.service.quest_service.check_and_complete_quests",
            new=AsyncMock(return_value=2),
        ) as check,
    ):
        count = await _check_quest_completion()

    assert count == 2
    check.assert_awaited_once()


@pytest.mark.asyncio
async def test_dispatch_game_tick_enqueues_every_active_vault_with_one_tick_id() -> None:
    """The dispatcher fans out one actor message per active vault."""
    vault_ids = [uuid4(), uuid4()]
    tick_id = "dispatch-1"

    with (
        patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
        patch(
            "app.api.tasks.game_loop_service.get_active_vault_ids",
            new=AsyncMock(return_value=vault_ids),
        ),
        patch("app.api.tasks.process_vault_tick.send") as send,
    ):
        stats = await _dispatch_game_tick(tick_id)

    assert stats == {"vaults_dispatched": 2}
    assert [(call.args[0], call.args[1]) for call in send.call_args_list] == [
        (str(vault_id), tick_id) for vault_id in vault_ids
    ]


def test_game_tick_uses_the_current_dramatiq_message_id() -> None:
    """A retry of the same game_tick message must reuse its tick id."""
    with (
        patch.object(CurrentMessage, "get_current_message", return_value=SimpleNamespace(message_id="dispatch-1")),
        patch("app.api.tasks._dispatch_game_tick", new=AsyncMock(return_value={"vaults_dispatched": 2})) as dispatch,
    ):
        game_tick.fn()

    dispatch.assert_awaited_once_with("dispatch-1")


@pytest.mark.asyncio
async def test_vault_tick_lock_is_exclusive_and_releasable() -> None:
    """Only one worker can hold a vault's tick lease, and release frees it."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        token = await _acquire_vault_tick_lock(redis, "vault-1")
        assert token is not None
        assert await _acquire_vault_tick_lock(redis, "vault-1") is None

        await _release_vault_tick_lock(redis, "vault-1", token)

        assert await _acquire_vault_tick_lock(redis, "vault-1") is not None
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_process_vault_tick_skips_when_another_worker_holds_the_lock() -> None:
    """A duplicate dispatch must not run the vault tick twice."""
    vault_id = str(uuid4())
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        await _acquire_vault_tick_lock(redis, vault_id)
        with patch("app.api.tasks.game_loop_service.process_vault_tick", new=AsyncMock()) as process:
            result = await _process_vault_tick_async(vault_id, redis)

        assert result == {"status": "skipped"}
        process.assert_not_awaited()
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_process_vault_tick_dedupes_the_same_dispatch_but_allows_the_next() -> None:
    """A successful tick is idempotent per dispatch, not per time window."""
    vault_id = str(uuid4())
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        with (
            patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
            patch("app.services.progression.objectives.evaluators.evaluator_manager.initialize"),
            patch("app.services.progression.objectives.notifications.register_objective_event_handlers"),
            patch(
                "app.api.tasks.game_loop_service.process_vault_tick",
                new=AsyncMock(return_value={"vault_id": vault_id}),
            ) as process,
        ):
            first = await _process_vault_tick_async(vault_id, redis, "dispatch-1")
            duplicate = await _process_vault_tick_async(vault_id, redis, "dispatch-1")
            next_tick = await _process_vault_tick_async(vault_id, redis, "dispatch-2")

        assert first == {"vault_id": vault_id}
        assert duplicate == {"status": "duplicate"}
        assert next_tick == {"vault_id": vault_id}
        assert process.await_count == 2
        assert await redis.get(f"fallout:vault-tick:{vault_id}") is None
        assert await redis.get(f"fallout:vault-tick-done:{vault_id}") == "dispatch-2"
        done_ttl = await redis.ttl(f"fallout:vault-tick-done:{vault_id}")
        assert 0 < done_ttl <= 300
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_process_vault_tick_releases_lease_on_failure_for_retry() -> None:
    """A failed tick must release its lease so the retry can run."""
    vault_id = str(uuid4())
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        with (
            patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
            patch("app.services.progression.objectives.evaluators.evaluator_manager.initialize"),
            patch("app.services.progression.objectives.notifications.register_objective_event_handlers"),
            patch(
                "app.api.tasks.game_loop_service.process_vault_tick",
                new=AsyncMock(side_effect=RuntimeError("boom")),
            ),
            pytest.raises(RuntimeError),
        ):
            await _process_vault_tick_async(vault_id, redis, "dispatch-1")

        assert await redis.get(f"fallout:vault-tick:{vault_id}") is None
        assert await redis.get(f"fallout:vault-tick-done:{vault_id}") is None
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_process_vault_tick_retries_the_same_dispatch_after_failure() -> None:
    """A failed tick leaves no completion marker, so its retry can run."""
    vault_id = str(uuid4())
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    process = AsyncMock(side_effect=[RuntimeError("boom"), {"vault_id": vault_id}])
    try:
        with (
            patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
            patch("app.services.progression.objectives.evaluators.evaluator_manager.initialize"),
            patch("app.services.progression.objectives.notifications.register_objective_event_handlers"),
            patch("app.api.tasks.game_loop_service.process_vault_tick", new=process),
        ):
            with pytest.raises(RuntimeError):
                await _process_vault_tick_async(vault_id, redis, "dispatch-1")

            result = await _process_vault_tick_async(vault_id, redis, "dispatch-1")

        assert result == {"vault_id": vault_id}
        assert process.await_count == 2
        assert await redis.get(f"fallout:vault-tick-done:{vault_id}") == "dispatch-1"
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_process_vault_tick_treats_deleted_vault_as_missing() -> None:
    """A vault deleted after dispatch is skipped without a retry loop."""
    vault_id = str(uuid4())
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        with (
            patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
            patch("app.services.progression.objectives.evaluators.evaluator_manager.initialize"),
            patch("app.services.progression.objectives.notifications.register_objective_event_handlers"),
            patch(
                "app.api.tasks.game_loop_service.process_vault_tick",
                new=AsyncMock(side_effect=ResourceNotFoundException(Vault, vault_id)),
            ),
        ):
            result = await _process_vault_tick_async(vault_id, redis)

        assert result == {"status": "missing"}
        assert await redis.get(f"fallout:vault-tick:{vault_id}") is None
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_process_vault_tick_reraises_missing_non_vault_resources() -> None:
    """A missing pregnancy or parent must retry, not masquerade as a deleted vault."""
    vault_id = str(uuid4())
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    try:
        with (
            patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
            patch("app.services.progression.objectives.evaluators.evaluator_manager.initialize"),
            patch("app.services.progression.objectives.notifications.register_objective_event_handlers"),
            patch(
                "app.api.tasks.game_loop_service.process_vault_tick",
                new=AsyncMock(side_effect=ResourceNotFoundException(Pregnancy, uuid4())),
            ),
            pytest.raises(ResourceNotFoundException),
        ):
            await _process_vault_tick_async(vault_id, redis)

        assert await redis.get(f"fallout:vault-tick:{vault_id}") is None
    finally:
        await redis.aclose()


@pytest.mark.asyncio
async def test_vault_tick_heartbeat_keeps_the_lease_alive(monkeypatch: pytest.MonkeyPatch) -> None:
    """A tick longer than the base TTL must not overlap a second worker."""
    vault_id = str(uuid4())
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr("app.api.tasks.VAULT_TICK_LOCK_TTL_SECONDS", 1)
    monkeypatch.setattr("app.api.tasks.VAULT_TICK_LOCK_RENEW_INTERVAL_SECONDS", 0.2)

    async def slow_tick(*_args, **_kwargs):
        await asyncio.sleep(1.5)
        return {"vault_id": vault_id}

    try:
        with (
            patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
            patch("app.services.progression.objectives.evaluators.evaluator_manager.initialize"),
            patch("app.services.progression.objectives.notifications.register_objective_event_handlers"),
            patch("app.api.tasks.game_loop_service.process_vault_tick", new=slow_tick),
        ):
            first = asyncio.create_task(_process_vault_tick_async(vault_id, redis))
            await asyncio.sleep(1.2)
            second = await _process_vault_tick_async(vault_id, redis)
            result = await first

        assert second == {"status": "skipped"}
        assert result == {"vault_id": vault_id}
    finally:
        await redis.delete(f"fallout:vault-tick:{vault_id}")
        await redis.aclose()
