"""Event generation for wasteland exploration."""

import random
from datetime import datetime

from app.core.game_config import game_config
from app.models.exploration import Exploration
from app.schemas.exploration_event import (
    CombatEventSchema,
    DangerEventSchema,
    ExplorationEvent,
    LootEventSchema,
    LootSchema,
    RestEventSchema,
)
from app.services.exploration import data_loader
from app.services.exploration.combat_calculator import combat_calculator
from app.services.exploration.loot_calculator import loot_calculator


class EventGenerator:
    """Generates exploration events."""

    def can_generate_event(self, exploration: Exploration) -> bool:
        """
        Check if enough time has passed to generate a new event.

        Args:
            exploration: Active exploration

        Returns:
            True if event should be generated
        """
        if not exploration.is_active():
            return False

        cfg = game_config.exploration

        # Check if enough time has passed for a new event
        last_event_time = None
        if exploration.events:
            last_event = exploration.events[-1]
            last_event_time = datetime.fromisoformat(last_event["timestamp"])

        if not last_event_time:
            # First event - check if initial delay has passed
            return exploration.elapsed_time_seconds() >= cfg.first_event_delay_seconds

        # Check if interval has passed since last event
        now = datetime.utcnow()
        time_since_last_event = (now - last_event_time).total_seconds()
        return time_since_last_event >= cfg.event_interval_seconds

    def generate_event(self, exploration: Exploration) -> ExplorationEvent | None:
        """
        Generate a random wasteland event.

        Args:
            exploration: Active exploration

        Returns:
            Event schema or None if no event should be generated
        """
        if not self.can_generate_event(exploration):
            return None

        # Determine event type with weighted probabilities
        cfg = game_config.exploration
        event_weights = {
            "combat": cfg.event_weight_combat,
            "loot": cfg.event_weight_loot,
            "danger": cfg.event_weight_danger,
            "rest": cfg.event_weight_rest,
        }

        event_type = random.choices(
            list(event_weights.keys()),
            weights=list(event_weights.values()),
            k=1,
        )[0]

        # Generate event based on type
        if event_type == "combat":
            return self._generate_combat_event(exploration)
        if event_type == "loot":
            return self._generate_loot_event(exploration)
        if event_type == "danger":
            return self._generate_danger_event(exploration)
        return self._generate_rest_event(exploration)

    def _generate_combat_event(self, exploration: Exploration) -> CombatEventSchema:
        """Generate combat event."""
        progress = exploration.progress_percentage()
        enemy = combat_calculator.select_enemy(progress)
        outcome = combat_calculator.calculate_combat_outcome(exploration, enemy)

        return CombatEventSchema(
            description=outcome.description,
            health_loss=outcome.health_loss,
            enemy=enemy.name,
            victory=outcome.victory,
        )

    def _generate_loot_event(self, exploration: Exploration) -> LootEventSchema:
        """Generate loot discovery event."""
        luck = exploration.dweller_luck
        perception = exploration.dweller_perception

        # Select loot item
        loot_item, item_type = loot_calculator.select_random_loot(luck)
        caps_found = loot_calculator.calculate_caps_found(perception, luck)

        templates = data_loader.load_event_templates()
        template = random.choice(templates["loot"])
        description = template.format(item=loot_item.name, caps=caps_found)

        return LootEventSchema(
            description=description,
            loot=LootSchema(item=loot_item, item_type=item_type, caps=caps_found),
        )

    def _generate_danger_event(self, exploration: Exploration) -> DangerEventSchema:
        """Generate danger/hazard event."""
        endurance = exploration.dweller_endurance
        damage = max(1, 10 - endurance)

        templates = data_loader.load_event_templates()
        template = random.choice(templates["danger"])
        description = template.format(damage=damage)

        return DangerEventSchema(description=description, health_loss=damage)

    def _generate_rest_event(self, exploration: Exploration) -> RestEventSchema:
        """Generate rest/recovery event."""
        cfg = game_config.exploration
        health_restored = random.randint(cfg.rest_health_min, cfg.rest_health_max)

        # Intelligence provides small bonus
        intelligence_bonus = exploration.dweller_intelligence // 3
        health_restored += intelligence_bonus

        templates = data_loader.load_event_templates()
        template = random.choice(templates["rest"])
        description = template.format(health=health_restored)

        return RestEventSchema(description=description, health_restored=health_restored)


# Singleton instance
event_generator = EventGenerator()
