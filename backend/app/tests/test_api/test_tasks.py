"""Tests for scheduled background tasks."""

from app.api.tasks import check_quest_completion


def test_quest_completion_is_scheduled_every_minute() -> None:
    """Finished quest timers are settled without a player request."""
    assert "periodic" in check_quest_completion.options
