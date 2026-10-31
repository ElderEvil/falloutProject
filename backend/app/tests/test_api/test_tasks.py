"""Tests for scheduled background tasks."""

from unittest.mock import AsyncMock, patch
from uuid import uuid4

import fakeredis.aioredis
import pytest

from app.api.tasks import (
    _acquire_vault_tick_lock,
    _check_quest_completion,
    _dispatch_game_tick,
    _process_vault_tick_async,
    _release_vault_tick_lock,
    check_quest_completion,
)
from app.models.vault import Vault
from app.utils.exceptions import ResourceNotFoundException


def test_quest_completion_is_scheduled_every_minute() -> None:
    """Finished quest timers are settled without a player request."""
    assert "periodic" in check_quest_completion.options


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
async def test_dispatch_game_tick_enqueues_every_active_vault() -> None:
    """The dispatcher fans out one actor message per active vault."""
    vault_ids = [uuid4(), uuid4()]

    with (
        patch("app.api.tasks.task_session", new=lambda: _FakeTaskSession()),
        patch(
            "app.api.tasks.game_loop_service.get_active_vault_ids",
            new=AsyncMock(return_value=vault_ids),
        ),
        patch("app.api.tasks.process_vault_tick.send") as send,
    ):
        stats = await _dispatch_game_tick()

    assert stats == {"vaults_dispatched": 2}
    assert [call.args[0] for call in send.call_args_list] == [str(vault_id) for vault_id in vault_ids]


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
async def test_process_vault_tick_keeps_lease_after_success_to_debounce_duplicates() -> None:
    """A successful tick leaves its lease until the next tick window."""
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
            ),
        ):
            first = await _process_vault_tick_async(vault_id, redis)
            second = await _process_vault_tick_async(vault_id, redis)

        assert first == {"vault_id": vault_id}
        assert second == {"status": "skipped"}
        assert await redis.get(f"fallout:vault-tick:{vault_id}") is not None
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
            await _process_vault_tick_async(vault_id, redis)

        assert await redis.get(f"fallout:vault-tick:{vault_id}") is None
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
