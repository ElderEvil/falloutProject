"""Cumulative XP thresholds shared by seeding, model properties and leveling."""

from app.core.game_config import game_config


def calculate_xp_required(level: int) -> int:
    """Total XP to reach a level: 0 at level 1, otherwise BASE_XP * level**EXPONENT.

    With the default base of 100 and exponent of 1.5, levels 2, 3, 10 and 50
    require 282, 519, 3,162 and 35,355 cumulative XP respectively.
    """
    if level <= 1:
        return 0
    return int(game_config.leveling.base_xp_requirement * (level**game_config.leveling.xp_curve_exponent))
