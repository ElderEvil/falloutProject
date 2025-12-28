"""Game balance configuration and constants."""

from app.models.incident import IncidentType

# ===== GAME LOOP CONFIGURATION =====
TICK_INTERVAL = 60  # Seconds between game ticks
MAX_OFFLINE_CATCHUP = 3600  # Maximum seconds to catch up (1 hour)

# ===== INCIDENT SPAWN RATES =====
# Base chance per tick (0.3% = 0.003)
INCIDENT_BASE_CHANCE = 0.003  # Rare by default

# Modifiers that increase spawn chance
INCIDENT_POPULATION_MODIFIER = 0.0001  # +0.01% per dweller
INCIDENT_LOW_RESOURCE_MODIFIER = 0.002  # +0.2% if any resource below 20%
INCIDENT_CRITICAL_RESOURCE_MODIFIER = 0.005  # +0.5% if any resource below 5%

# Maximum spawn chance (cap at 5%)
INCIDENT_MAX_CHANCE = 0.05

# ===== INCIDENT DIFFICULTIES =====
# Difficulty range (min, max) for each incident type
INCIDENT_DIFFICULTY = {
    IncidentType.RADROACH_INFESTATION: (1, 3),
    IncidentType.MOLE_RAT_ATTACK: (2, 5),
    IncidentType.RAIDER_ATTACK: (4, 7),
    IncidentType.FERAL_GHOUL_ATTACK: (5, 8),
    IncidentType.DEATHCLAW_ATTACK: (8, 10),
    IncidentType.FIRE: (2, 4),
    IncidentType.RADIATION_LEAK: (2, 5),
    IncidentType.ELECTRICAL_FAILURE: (1, 3),
    IncidentType.WATER_CONTAMINATION: (2, 4),
}

# Incident spawn weights (higher = more likely)
INCIDENT_WEIGHTS = {
    IncidentType.RADROACH_INFESTATION: 30,  # Most common
    IncidentType.MOLE_RAT_ATTACK: 25,
    IncidentType.FIRE: 20,
    IncidentType.RAIDER_ATTACK: 10,
    IncidentType.RADIATION_LEAK: 8,
    IncidentType.ELECTRICAL_FAILURE: 15,
    IncidentType.WATER_CONTAMINATION: 12,
    IncidentType.FERAL_GHOUL_ATTACK: 5,
    IncidentType.DEATHCLAW_ATTACK: 2,  # Rarest
}

# Incident duration before auto-spread (seconds)
INCIDENT_SPREAD_DURATION = 120  # 2 minutes

# ===== COMBAT BALANCE =====
DWELLER_BASE_DAMAGE = 5
STRENGTH_DAMAGE_MULTIPLIER = 0.5
PERCEPTION_HIT_CHANCE_BONUS = 0.02  # +2% per point
DEFENSE_REDUCTION_MULTIPLIER = 0.3

# Enemy damage per difficulty level
ENEMY_DAMAGE_PER_DIFFICULTY = 3

# ===== HEALTH & NEEDS =====
HEALTH_REGEN_PER_TICK = 5  # HP per 60s (when not in combat, resources available)
RADIATION_DECAY_PER_TICK = 2  # RAD per 60s (when in safe room)
HAPPINESS_DECAY_PER_TICK = 1  # Happiness loss per tick if resources low

# Resource thresholds for dweller effects
STARVATION_THRESHOLD = 0.0  # No food = no health regen
DEHYDRATION_THRESHOLD = 0.0  # No water = no health regen

# ===== LOOT SYSTEM =====
# Caps reward range by incident difficulty
CAPS_REWARD_BASE = 50
CAPS_REWARD_PER_DIFFICULTY = 20

# Chance to drop items (0.0 - 1.0)
WEAPON_DROP_CHANCE = 0.15  # 15%
OUTFIT_DROP_CHANCE = 0.10  # 10%
JUNK_DROP_CHANCE = 0.30  # 30%

# ===== RESOURCE BALANCE =====
# Production rates (from resource_manager.py)
BASE_PRODUCTION_RATE = 0.1  # Per SPECIAL point per second
TIER_MULTIPLIER = {1: 1.0, 2: 1.5, 3: 2.0}

# Consumption rates (from resource_manager.py)
POWER_CONSUMPTION_RATE = 0.5 / 60  # Per room size per tier per second
FOOD_CONSUMPTION_PER_DWELLER = 0.36 / 60  # Per dweller per second
WATER_CONSUMPTION_PER_DWELLER = 0.36 / 60  # Per dweller per second

# Resource warning thresholds
LOW_RESOURCE_THRESHOLD = 0.2  # 20% of max
CRITICAL_RESOURCE_THRESHOLD = 0.05  # 5% of max


# ===== DIFFICULTY SCALING =====
def calculate_incident_difficulty(vault_population: int, avg_dweller_level: float) -> int:
    """
    Calculate incident difficulty based on vault state.

    Args:
        vault_population: Number of dwellers in vault
        avg_dweller_level: Average level of all dwellers

    Returns:
        Difficulty level (1-10)
    """
    # Base difficulty increases with population
    population_factor = min(vault_population / 20, 1.0)  # Max at 20 dwellers

    # Level factor
    level_factor = min(avg_dweller_level / 50, 1.0)  # Max at level 50

    # Combined difficulty (1-10 scale)
    difficulty = 1 + int((population_factor + level_factor) / 2 * 9)

    return max(1, min(difficulty, 10))


def get_incident_spawn_chance(
    vault_population: int,
    has_low_resources: bool,  # noqa: FBT001
    has_critical_resources: bool,  # noqa: FBT001
) -> float:
    """
    Calculate incident spawn chance for this tick.

    Args:
        vault_population: Number of dwellers
        has_low_resources: Any resource below 20%
        has_critical_resources: Any resource below 5%

    Returns:
        Spawn chance (0.0 - 1.0)
    """
    chance = INCIDENT_BASE_CHANCE

    # Population modifier
    chance += vault_population * INCIDENT_POPULATION_MODIFIER

    # Resource modifiers
    if has_critical_resources:
        chance += INCIDENT_CRITICAL_RESOURCE_MODIFIER
    elif has_low_resources:
        chance += INCIDENT_LOW_RESOURCE_MODIFIER

    # Cap at maximum
    return min(chance, INCIDENT_MAX_CHANCE)
