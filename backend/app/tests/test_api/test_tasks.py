"""Tests for scheduled background tasks."""

from unittest.mock import AsyncMock, patch

import pytest

from app.api.tasks import _check_quest_completion, check_quest_completion


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
