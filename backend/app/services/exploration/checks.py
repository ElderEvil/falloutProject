"""Dice and SPECIAL checks shared by expedition resolution and views."""

import random

from app.core.enums import SPECIAL_STATS
from app.models.exploration import Exploration

STAT_SNAPSHOT_FIELDS = {stat: f"dweller_{stat}" for stat in SPECIAL_STATS}


def success_odds(stat_value: int, difficulty: int) -> float:
    """Display odds for d20 + stat*2 >= 10 + difficulty*2, clamped to 5%-95%."""
    need = _check_threshold(stat_value, difficulty)
    return min(0.95, max(0.05, (21 - need) / 20))


def roll_check(stat_value: int, difficulty: int) -> bool:
    """Roll d20 + stat*2 against 10 + difficulty*2."""
    return random.randint(1, 20) >= _check_threshold(stat_value, difficulty)


def _check_threshold(stat_value: int, difficulty: int) -> int:
    return 10 + 2 * (difficulty - stat_value)


def stat_value(exploration: Exploration, stat: str) -> int:
    return int(getattr(exploration, STAT_SNAPSHOT_FIELDS[stat]))
