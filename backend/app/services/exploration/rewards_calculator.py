"""Rewards and XP calculations for exploration."""

from app.core.game_config import game_config
from app.models.exploration import Exploration
from app.options.pet_modifiers import MAX_PCT_BONUS, pet_modifiers_for


class RewardsCalculator:
    """Handles XP and rewards calculations."""

    def calculate_exploration_xp(self, exploration: Exploration, dweller) -> int:
        """Calculate total XP from exploration with all bonuses.

        Base XP from distance/enemies/events plus survival bonus (>70% health on return), luck-scaled bonus, and
        additive pet XP percentage capped by MAX_PCT_BONUS.
        """
        cfg = game_config.leveling

        # Base XP sources
        distance_xp = exploration.total_distance * cfg.exploration_xp_per_distance
        combat_xp = exploration.enemies_encountered * cfg.exploration_xp_per_enemy
        # Site events are journey-log noise (one per resolution); site XP comes from enemies_encountered.
        event_xp = sum(1 for e in exploration.events if e.get("type") != "site") * cfg.exploration_xp_per_event

        base_xp = distance_xp + combat_xp + event_xp

        # Survival bonus (returned with >70% health)
        survival_bonus = 0
        if dweller.health / dweller.effective_max_health > 0.7:
            survival_bonus = int(base_xp * cfg.exploration_survival_bonus)

        # Luck bonus (2% per luck point)
        luck_bonus = int(base_xp * (exploration.dweller_luck * cfg.exploration_luck_bonus))

        # Pet XP bonus (additive percentage of base XP, capped)
        pet_bonus = int(base_xp * min(pet_modifiers_for(dweller).xp_pct, MAX_PCT_BONUS))

        total_xp = base_xp + survival_bonus + luck_bonus + pet_bonus

        return int(total_xp)


# Singleton instance
rewards_calculator = RewardsCalculator()
