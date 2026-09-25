"""Combat calculations for wasteland exploration."""

import random
from operator import itemgetter

from app.core.game_config import game_config
from app.models.exploration import Exploration
from app.schemas.exploration_event import CombatOutcomeSchema, EnemySchema
from app.services.exploration import data_loader
from app.utils.combat import ExpeditionCombatProfile


class CombatCalculator:
    """Handles combat outcome calculations."""

    def select_enemy(self, progress: float) -> EnemySchema:
        """Select enemy based on exploration progress.

        Args:
            progress: Progress percentage (0-100)

        Returns:
            EnemySchema with name, difficulty, min_damage, max_damage
        """
        enemies = data_loader.load_enemies()
        if not enemies:
            return EnemySchema(name="Wasteland Creature", difficulty=1, min_damage=5, max_damage=15)

        # Difficulty scales with progress (1-5)
        max_difficulty = 1 + int(progress / 25)  # 0-24%=1, 25-49%=2, etc.
        available_enemies = [e for e in enemies if e["difficulty"] <= max_difficulty]

        if not available_enemies:
            available_enemies = enemies

        return EnemySchema(**random.choice(available_enemies))

    def select_enemy_by_difficulty(self, difficulty: int) -> EnemySchema:
        """One enemy at the requested difficulty, or the nearest at-or-below.

        The single entry point for "enemy of tier N" so targeted dispatch (and any
        future caller) shares the enemy-table shaping instead of re-deriving it.
        """
        enemies = data_loader.load_enemies()
        if not enemies:
            return EnemySchema(name="Wasteland Creature", difficulty=1, min_damage=5, max_damage=15)
        at_or_below = [enemy for enemy in enemies if enemy["difficulty"] <= difficulty]
        if not at_or_below:
            at_or_below = [min(enemies, key=itemgetter("difficulty"))]
        return EnemySchema(**max(at_or_below, key=itemgetter("difficulty")))

    def calculate_combat_outcome(
        self,
        exploration: Exploration,
        enemy: EnemySchema,
        profile: ExpeditionCombatProfile | None = None,
    ) -> CombatOutcomeSchema:
        """Calculate combat outcome based on dweller stats.

        Args:
            exploration: Active exploration
            enemy: Enemy schema with combat stats
            profile: Live combat inputs (effective SPECIAL + equipped weapon damage);
                None falls back to the exploration's departure snapshot.

        Returns:
            CombatOutcomeSchema with victory, health_loss, and description
        """
        if profile is not None:
            strength, agility, endurance = profile.strength, profile.agility, profile.endurance
        else:
            strength, agility, endurance = (
                exploration.dweller_strength,
                exploration.dweller_agility,
                exploration.dweller_endurance,
            )

        # Combat power = Strength + (Agility / 2) + equipped weapon damage bonus
        cfg = game_config.exploration
        weapon_bonus = profile.weapon_damage * cfg.combat_weapon_damage_multiplier if profile else 0
        combat_power = strength + (agility // 2) + weapon_bonus

        # Success chance based on combat power
        success_chance = min(
            cfg.combat_success_max,
            cfg.combat_success_base + (combat_power * cfg.combat_stat_multiplier),
        )

        success = random.random() < success_chance

        if success:
            # Victory - minimal damage (enemy min damage - endurance bonus)
            damage = max(1, enemy.min_damage - (endurance * 2))
            description = f"Defeated {enemy.name}! Took {damage} damage."
            return CombatOutcomeSchema(victory=True, health_loss=damage, description=description)

        # Defeat - significant damage (random in range - endurance bonus)
        damage = random.randint(enemy.min_damage, enemy.max_damage) - endurance
        damage = max(damage // 2, 1)  # At least some damage
        description = f"Barely survived {enemy.name}. Took {damage} damage."
        return CombatOutcomeSchema(victory=False, health_loss=damage, description=description)


# Singleton instance
combat_calculator = CombatCalculator()
