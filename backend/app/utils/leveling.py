"""Cumulative XP thresholds shared by seeding, model properties and leveling."""

from app.core.game_config import game_config


def calculate_xp_required(level: int) -> int:
    """Total XP to reach a level: 0 at level 1, else BASE_XP * level**EXPONENT.

    Defaults (base 100, exponent 1.5): levels 2, 3, 10, 50 need 282, 519, 3162, 35355
    cumulative XP.
    """
    if level <= 1:
        return 0
    return int(game_config.leveling.base_xp_requirement * (level**game_config.leveling.xp_curve_exponent))
