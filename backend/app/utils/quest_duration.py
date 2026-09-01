"""Quest duration helpers shared by quest reads and starts."""

from app.core.config import settings


def effective_quest_duration_minutes(duration_minutes: int) -> int:
    """Apply the local test-time multiplier, with a one-minute floor."""
    return min(240, max(1, round(duration_minutes * settings.QUEST_DURATION_MULTIPLIER)))
