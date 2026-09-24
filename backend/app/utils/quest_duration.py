"""Quest duration helpers shared by quest reads and starts."""

from app.core.config import settings

# The trip home takes half the effective quest duration, capped so a long quest
# never adds more than 30 minutes of dead time.
QUEST_RETURN_LEG_FRACTION = 0.5
QUEST_RETURN_LEG_MAX_MINUTES = 30


def effective_quest_duration_minutes(duration_minutes: int) -> int:
    """Apply the local test-time multiplier, with a one-minute floor."""
    return min(240, max(1, round(duration_minutes * settings.QUEST_DURATION_MULTIPLIER)))


def quest_return_leg_minutes(duration_minutes: int) -> int:
    """Minutes a finished quest party spends travelling home.

    Half the effective quest duration, capped at 30 minutes with a one-minute
    floor. The input is expected to already be effective (multiplier-aware).
    """
    return min(QUEST_RETURN_LEG_MAX_MINUTES, max(1, round(duration_minutes * QUEST_RETURN_LEG_FRACTION)))
