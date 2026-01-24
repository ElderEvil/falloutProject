"""Game balance configuration using Pydantic Settings.

This module provides type-safe, validated configuration for all game balance constants.
Values can be overridden via environment variables (e.g., INCIDENT_SPAWN_CHANCE=0.10).

Usage:
    from app.core.game_config import game_config

    # Access nested configs
    spawn_rate = game_config.incident.spawn_chance_per_hour
    training_time = game_config.training.base_duration_seconds
"""

import logging

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.models.incident import IncidentType

logger = logging.getLogger(__name__)


class GameLoopConfig(BaseSettings):
    """Game loop timing configuration."""

    model_config = SettingsConfigDict(env_prefix="GAME_LOOP_")

    tick_interval: int = Field(
        default=60,
        description="Seconds between game ticks",
        ge=1,
        le=300,
    )
    max_offline_catchup: int = Field(
        default=3600,
        description="Maximum seconds to catch up after offline (1 hour)",
        ge=0,
        le=86400,
    )


class IncidentConfig(BaseSettings):
    """Incident spawn and progression configuration."""

    model_config = SettingsConfigDict(env_prefix="INCIDENT_")

    spawn_chance_per_hour: float = Field(
        default=0.05,
        description="5% chance per hour for incident to spawn",
        ge=0.0,
        le=1.0,
    )
    min_vault_population: int = Field(
        default=5,
        description="Minimum dwellers required for incidents",
        ge=0,
    )
    spread_duration: int = Field(
        default=60,
        description="Seconds before incident spreads to adjacent rooms",
        ge=10,
    )
    max_spread_count: int = Field(
        default=3,
        description="Maximum number of times an incident can spread",
        ge=0,
        le=10,
    )
    max_active_incidents: int = Field(
        default=5,
        description="Maximum number of active incidents per vault",
        ge=1,
        le=20,
    )
    spawn_cooldown_seconds: int = Field(
        default=120,
        description="Minimum seconds between incident spawns",
        ge=0,
        le=600,
    )

    # Difficulty ranges by type
    difficulty_fire: tuple[int, int] = (2, 4)
    difficulty_radroach: tuple[int, int] = (1, 3)
    difficulty_mole_rat: tuple[int, int] = (2, 5)
    difficulty_raider: tuple[int, int] = (4, 7)
    difficulty_feral_ghoul: tuple[int, int] = (5, 8)
    difficulty_deathclaw: tuple[int, int] = (8, 10)

    # Spawn weights (higher = more common)
    weight_fire: int = 20
    weight_radroach: int = 30
    weight_mole_rat: int = 25
    weight_raider: int = 10
    weight_feral_ghoul: int = 5
    weight_deathclaw: int = 2

    def get_difficulty_range(self, incident_type: IncidentType) -> tuple[int, int]:
        """Get difficulty range for incident type."""
        difficulty_map = {
            IncidentType.FIRE: self.difficulty_fire,
            IncidentType.RADROACH_INFESTATION: self.difficulty_radroach,
            IncidentType.MOLE_RAT_ATTACK: self.difficulty_mole_rat,
            IncidentType.RAIDER_ATTACK: self.difficulty_raider,
            IncidentType.FERAL_GHOUL_ATTACK: self.difficulty_feral_ghoul,
            IncidentType.DEATHCLAW_ATTACK: self.difficulty_deathclaw,
        }
        return difficulty_map.get(incident_type, (1, 5))

    def get_spawn_weights(self) -> dict[IncidentType, int]:
        """Get spawn weights for all incident types."""
        return {
            IncidentType.FIRE: self.weight_fire,
            IncidentType.RADROACH_INFESTATION: self.weight_radroach,
            IncidentType.MOLE_RAT_ATTACK: self.weight_mole_rat,
            IncidentType.RAIDER_ATTACK: self.weight_raider,
            IncidentType.FERAL_GHOUL_ATTACK: self.weight_feral_ghoul,
            IncidentType.DEATHCLAW_ATTACK: self.weight_deathclaw,
        }

    @property
    def vault_door_incidents(self) -> set[str]:
        """Incidents that spawn at vault door (0,0) - external threats."""
        return {
            IncidentType.RAIDER_ATTACK.value,
            IncidentType.DEATHCLAW_ATTACK.value,
            IncidentType.FERAL_GHOUL_ATTACK.value,
        }


class CombatConfig(BaseSettings):
    """Combat and loot configuration."""

    model_config = SettingsConfigDict(env_prefix="COMBAT_")

    base_raider_power: int = Field(default=10, description="Power per difficulty level", ge=1)
    dweller_strength_weight: float = Field(default=0.4, ge=0.0, le=1.0)
    dweller_endurance_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    dweller_agility_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    level_bonus_multiplier: int = Field(default=2, ge=0)

    # Loot
    loot_caps_min: int = Field(default=50, ge=0)
    loot_caps_max_per_difficulty: int = Field(default=100, ge=0)
    caps_reward_base: int = Field(default=50, ge=0)
    caps_reward_per_difficulty: int = Field(default=20, ge=0)

    # Item drop chances
    weapon_drop_chance: float = Field(default=0.15, ge=0.0, le=1.0)
    outfit_drop_chance: float = Field(default=0.10, ge=0.0, le=1.0)
    junk_drop_chance: float = Field(default=0.30, ge=0.0, le=1.0)

    # XP rewards
    xp_per_difficulty: int = Field(default=30, description="Base XP per difficulty level", ge=0)
    perfect_bonus_multiplier: float = Field(default=1.5, description="50% bonus for no damage", ge=1.0)


class HealthConfig(BaseSettings):
    """Health and needs configuration."""

    model_config = SettingsConfigDict(env_prefix="HEALTH_")

    regen_per_tick: int = Field(default=5, description="HP per 60s when safe and fed", ge=0)
    radiation_decay_per_tick: int = Field(default=2, description="RAD per 60s in safe room", ge=0)
    starvation_threshold: float = Field(default=0.0, description="Food % below which no regen", ge=0.0, le=1.0)
    dehydration_threshold: float = Field(default=0.0, description="Water % below which no regen", ge=0.0, le=1.0)


class HappinessConfig(BaseSettings):
    """Happiness system configuration."""

    model_config = SettingsConfigDict(env_prefix="HAPPINESS_")

    # Decay rates (per 60s tick)
    base_decay: float = Field(default=0.5, description="Natural happiness decay", ge=0.0)
    resource_shortage_decay: float = Field(default=2.0, description="Extra decay when resources <20%", ge=0.0)
    critical_resource_decay: float = Field(default=5.0, description="Extra decay when resources <5%", ge=0.0)
    incident_penalty: float = Field(default=3.0, description="Penalty per active incident", ge=0.0)
    idle_decay: float = Field(default=1.0, description="Extra decay for idle dwellers", ge=0.0)

    # Gain rates (per 60s tick)
    working_gain: float = Field(default=1.0, description="Gain when working", ge=0.0)
    high_health_bonus: float = Field(default=0.5, description="Bonus when health >80%", ge=0.0)
    partner_nearby_bonus: float = Field(default=1.0, description="Bonus when partner in same room", ge=0.0)

    # Room-specific bonuses
    living_quarters_bonus: float = Field(default=1.5, ge=0.0)
    training_room_bonus: float = Field(default=0.5, ge=0.0)
    radio_room_bonus: float = Field(default=1.0, ge=0.0)

    # Status modifiers
    combat_penalty: float = Field(default=2.0, description="Fighting is stressful", ge=0.0)
    training_gain: float = Field(default=0.5, description="Learning is fulfilling", ge=0.0)

    # Vault-wide bonuses
    high_vault_resources_bonus: float = Field(default=0.5, description="Bonus when all resources >80%", ge=0.0)
    no_incidents_bonus: float = Field(default=0.3, description="Bonus when no active incidents", ge=0.0)

    # Thresholds
    high_health_threshold: float = Field(default=0.8, ge=0.0, le=1.0)
    critical_resource_threshold: float = Field(default=0.05, ge=0.0, le=1.0)


class TrainingConfig(BaseSettings):
    """Training system configuration."""

    model_config = SettingsConfigDict(env_prefix="TRAINING_")

    base_duration_seconds: int = Field(default=7200, description="2 hours base", ge=60)
    per_level_increase_seconds: int = Field(default=1800, description="30 min per stat level", ge=0)

    # Tier speed multipliers (lower = faster)
    tier_1_multiplier: float = Field(default=1.0, ge=0.1, le=2.0)
    tier_2_multiplier: float = Field(default=0.75, ge=0.1, le=2.0)
    tier_3_multiplier: float = Field(default=0.6, ge=0.1, le=2.0)

    # SPECIAL limits
    special_stat_min: int = Field(default=1, ge=1)
    special_stat_max: int = Field(default=10, ge=1)

    def get_tier_multiplier(self, tier: int) -> float:
        """Get training speed multiplier for room tier."""
        multipliers = {
            1: self.tier_1_multiplier,
            2: self.tier_2_multiplier,
            3: self.tier_3_multiplier,
        }
        return multipliers.get(tier, 1.0)


class ResourceConfig(BaseSettings):
    """Resource production and consumption configuration."""

    model_config = SettingsConfigDict(env_prefix="RESOURCE_")

    # Production
    base_production_rate: float = Field(default=0.1, description="Per SPECIAL point per second", ge=0.0)
    tier_1_multiplier: float = Field(default=1.0, ge=0.0)
    tier_2_multiplier: float = Field(default=1.5, ge=0.0)
    tier_3_multiplier: float = Field(default=2.0, ge=0.0)

    # Consumption
    power_consumption_rate: float = Field(default=0.5 / 60, description="Per room per tier per second", ge=0.0)
    food_consumption_per_dweller: float = Field(default=0.36 / 60, description="Per dweller per second", ge=0.0)
    water_consumption_per_dweller: float = Field(default=0.36 / 60, description="Per dweller per second", ge=0.0)

    # Thresholds
    low_threshold: float = Field(default=0.2, description="20% of max", ge=0.0, le=1.0)
    critical_threshold: float = Field(default=0.05, description="5% of max", ge=0.0, le=1.0)

    def get_tier_multiplier(self, tier: int) -> float:
        """Get production multiplier for room tier."""
        multipliers = {
            1: self.tier_1_multiplier,
            2: self.tier_2_multiplier,
            3: self.tier_3_multiplier,
        }
        return multipliers.get(tier, 1.0)


class RelationshipConfig(BaseSettings):
    """Relationship and compatibility configuration."""

    model_config = SettingsConfigDict(env_prefix="RELATIONSHIP_")

    affinity_increase_per_tick: int = Field(default=2, description="Affinity gain when in same room", ge=0)
    romance_threshold: int = Field(default=70, description="Affinity required for romance", ge=0, le=100)
    partner_happiness_bonus: int = Field(default=10, description="Happiness bonus from having partner", ge=0)

    # Compatibility weights (must sum to 1.0)
    compatibility_special_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    compatibility_happiness_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    compatibility_level_weight: float = Field(default=0.2, ge=0.0, le=1.0)
    compatibility_proximity_weight: float = Field(default=0.3, ge=0.0, le=1.0)

    @field_validator("compatibility_proximity_weight")
    @classmethod
    def validate_weights_sum(cls, v: float, info) -> float:
        """Ensure compatibility weights sum to 1.0."""
        weights = [
            info.data.get("compatibility_special_weight", 0.3),
            info.data.get("compatibility_happiness_weight", 0.2),
            info.data.get("compatibility_level_weight", 0.2),
            v,
        ]
        total = sum(weights)
        if not 0.99 <= total <= 1.01:  # Allow small floating point error
            raise ValueError(f"Compatibility weights must sum to 1.0, got {total}")  # noqa: EM102, TRY003
        return v


class BreedingConfig(BaseSettings):
    """Breeding and pregnancy configuration."""

    model_config = SettingsConfigDict(env_prefix="BREEDING_")

    conception_chance_per_tick: float = Field(
        default=0.02,
        description="2% chance per tick for partners in living quarters",
        ge=0.0,
        le=1.0,
    )
    pregnancy_duration_hours: int = Field(default=3, description="Real-time hours", ge=1)
    trait_inheritance_variance: int = Field(default=2, description="± SPECIAL variance from parents", ge=0)
    rarity_upgrade_chance: float = Field(
        default=0.15,
        description="15% chance for higher rarity",
        ge=0.0,
        le=1.0,
    )

    # Child growth
    child_growth_duration_hours: int = Field(default=3, description="Hours to grow to adult", ge=1)
    child_special_multiplier: float = Field(default=0.5, description="Children have 50% of adult stats", ge=0.0, le=1.0)
    child_consumption_multiplier: float = Field(
        default=0.7,
        description="Children consume 70% of adult resources",
        ge=0.0,
        le=1.0,
    )


class LevelingConfig(BaseSettings):
    """Leveling and experience configuration."""

    model_config = SettingsConfigDict(env_prefix="LEVELING_")

    # XP curve: BASE * (level ^ EXPONENT)
    base_xp_requirement: int = Field(default=100, ge=1)
    xp_curve_exponent: float = Field(default=1.5, ge=1.0, le=3.0)

    hp_gain_per_level: int = Field(default=5, description="Health gained per level up", ge=1)
    max_level: int = Field(default=50, description="Maximum dweller level", ge=1, le=100)

    # XP sources
    exploration_xp_per_distance: int = Field(default=10, description="Per mile traveled", ge=0)
    exploration_xp_per_enemy: int = Field(default=50, description="Per enemy defeated", ge=0)
    exploration_xp_per_event: int = Field(default=20, description="Per event encountered", ge=0)
    exploration_survival_bonus: float = Field(default=0.2, description="20% bonus if >70% health", ge=0.0)
    exploration_luck_bonus: float = Field(default=0.02, description="2% per luck point", ge=0.0)

    work_xp_per_tick: int = Field(default=2, description="XP per minute working (120/hr)", ge=0)
    work_efficiency_bonus: float = Field(default=1.5, description="50% more XP at 100% efficiency", ge=1.0)


class RadioConfig(BaseSettings):
    """Radio recruitment configuration."""

    model_config = SettingsConfigDict(env_prefix="RADIO_")

    base_recruitment_rate: float = Field(
        default=1.0 / 360.0,
        description="1 recruit per 6 hours in minutes",
        ge=0.0,
    )
    charisma_rate_multiplier: float = Field(default=0.05, description="+5% per charisma point", ge=0.0)
    happiness_rate_multiplier: float = Field(default=0.01, description="+1% per happiness %", ge=0.0)
    manual_recruitment_cost: int = Field(default=500, description="Caps to recruit manually", ge=0)

    # Tier multipliers
    tier_1_multiplier: float = Field(default=1.0, ge=0.0)
    tier_2_multiplier: float = Field(default=1.5, ge=0.0)
    tier_3_multiplier: float = Field(default=2.0, ge=0.0)

    happiness_bonus: int = Field(default=1, description="+1 happiness per dweller per tick", ge=0)

    def get_tier_multiplier(self, tier: int) -> float:
        """Get radio effectiveness multiplier for room tier."""
        multipliers = {
            1: self.tier_1_multiplier,
            2: self.tier_2_multiplier,
            3: self.tier_3_multiplier,
        }
        return multipliers.get(tier, 1.0)


class DeathConfig(BaseSettings):
    """Death and revival system configuration."""

    model_config = SettingsConfigDict(env_prefix="DEATH_")

    # Permanent death timing
    permanent_death_days: int = Field(
        default=7,
        description="Days after death before permanent (cannot revive)",
        ge=1,
        le=30,
    )

    # Tiered revival cost (Option B)
    # Levels 1-5: level x tier_1_multiplier
    # Levels 6-10: level x tier_2_multiplier
    # Levels 11+: level x tier_3_multiplier, capped at max
    revival_cost_tier_1_multiplier: int = Field(default=50, description="Caps per level for levels 1-5", ge=1)
    revival_cost_tier_2_multiplier: int = Field(default=75, description="Caps per level for levels 6-10", ge=1)
    revival_cost_tier_3_multiplier: int = Field(default=100, description="Caps per level for levels 11+", ge=1)
    revival_cost_max: int = Field(default=2000, description="Maximum revival cost cap", ge=100)

    # Health after revival
    revival_health_percent: float = Field(
        default=0.5,
        description="Health restored as percentage of max (50%)",
        ge=0.1,
        le=1.0,
    )

    # Radiation threshold for death
    radiation_death_threshold: int = Field(
        default=1000,
        description="Radiation level that causes death",
        ge=100,
        le=1000,
    )

    def calculate_revival_cost(self, level: int) -> int:
        """
        Calculate revival cost based on dweller level (tiered).

        Levels 1-5: level x 50 (50-250 caps)
        Levels 6-10: level x 75 (450-750 caps)
        Levels 11+: level x 100 (1100-2000 caps, capped)

        :param level: Dweller level to calculate revival cost for.
        :type level: int
        :returns: Revival cost in caps based on tiered levels.
        :rtype: int
        :raises ValueError: if level is less than 1 (invalid level)
        """
        if level <= 5:
            cost = level * self.revival_cost_tier_1_multiplier
        elif level <= 10:
            cost = level * self.revival_cost_tier_2_multiplier
        else:
            cost = level * self.revival_cost_tier_3_multiplier

        return min(cost, self.revival_cost_max)


class ExplorationConfig(BaseSettings):
    """Wasteland exploration configuration."""

    model_config = SettingsConfigDict(env_prefix="EXPLORATION_")

    # Event timing
    event_interval_seconds: int = Field(default=600, description="10 minutes between events", ge=60)
    first_event_delay_seconds: int = Field(default=300, description="5 minutes until first event", ge=60)

    # Event type weights (relative probability)
    event_weight_combat: int = Field(default=35, ge=0)
    event_weight_loot: int = Field(default=35, ge=0)
    event_weight_danger: int = Field(default=20, ge=0)
    event_weight_rest: int = Field(default=10, ge=0)

    # Stat calculation formulas
    luck_multiplier_min: float = Field(default=0.5, description="Luck 1 = 0.5x", ge=0.0)
    luck_multiplier_max: float = Field(default=2.0, description="Luck 10 = 2.0x", ge=0.0)

    perception_bonus_min: float = Field(default=0.5, description="Perception 1 = 50% find chance", ge=0.0, le=1.0)
    perception_bonus_max: float = Field(default=0.95, description="Perception 10 = 95% find chance", ge=0.0, le=1.0)

    endurance_stamina_bonus: float = Field(default=0.5, description="Max 50% more events with high endurance", ge=0.0)

    # Combat formulas
    combat_success_base: float = Field(default=0.3, description="30% base success chance", ge=0.0, le=1.0)
    combat_success_max: float = Field(default=0.9, description="90% max success chance", ge=0.0, le=1.0)
    combat_stat_multiplier: float = Field(default=0.06, description="6% per combined combat stat point", ge=0.0)

    # Loot rarity by luck
    rarity_common_base: float = Field(default=70.0, ge=0.0)
    rarity_rare_base: float = Field(default=25.0, ge=0.0)
    rarity_legendary_base: float = Field(default=5.0, ge=0.0)

    # Loot type weights
    loot_type_junk: float = Field(default=60.0, ge=0.0)
    loot_type_weapon: float = Field(default=25.0, ge=0.0)
    loot_type_outfit: float = Field(default=15.0, ge=0.0)

    # Caps rewards
    caps_base_min: int = Field(default=10, ge=0)
    caps_base_max: int = Field(default=30, ge=0)
    caps_perception_multiplier: int = Field(default=2, ge=0)
    caps_luck_multiplier: int = Field(default=3, ge=0)

    # Health changes
    rest_health_min: int = Field(default=3, ge=0)
    rest_health_max: int = Field(default=8, ge=0)


class GameConfig(BaseSettings):
    """Master game configuration."""

    model_config = SettingsConfigDict(env_prefix="GAME_", env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Nested configs
    game_loop: GameLoopConfig = Field(default_factory=GameLoopConfig)
    incident: IncidentConfig = Field(default_factory=IncidentConfig)
    combat: CombatConfig = Field(default_factory=CombatConfig)
    health: HealthConfig = Field(default_factory=HealthConfig)
    happiness: HappinessConfig = Field(default_factory=HappinessConfig)
    training: TrainingConfig = Field(default_factory=TrainingConfig)
    resource: ResourceConfig = Field(default_factory=ResourceConfig)
    relationship: RelationshipConfig = Field(default_factory=RelationshipConfig)
    breeding: BreedingConfig = Field(default_factory=BreedingConfig)
    leveling: LevelingConfig = Field(default_factory=LevelingConfig)
    radio: RadioConfig = Field(default_factory=RadioConfig)
    exploration: ExplorationConfig = Field(default_factory=ExplorationConfig)
    death: DeathConfig = Field(default_factory=DeathConfig)


# Singleton instance
game_config = GameConfig()

# Log configuration on initialization
logger.info("Game configuration loaded successfully")
logger.info(f"Game loop tick interval: {game_config.game_loop.tick_interval}s")
logger.info(f"Incident spawn chance: {game_config.incident.spawn_chance_per_hour:.2%}/hour")
logger.info(f"Training base duration: {game_config.training.base_duration_seconds}s")
logger.info(f"Resource low threshold: {game_config.resource.low_threshold:.0%}")
logger.info(f"Max dweller level: {game_config.leveling.max_level}")
