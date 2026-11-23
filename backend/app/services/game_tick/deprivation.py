"""Graded, non-lethal deprivation: accumulated active time, increments, and the health floor.

Health is integer-backed, so each tick applies the difference between the cumulative amount at the persisted
counter and the amount at the previous value. The reset on refill happens after that difference is applied, so a
refill can never make the increment negative and heal the dweller.
"""

import math
from collections.abc import Sequence
from dataclasses import dataclass

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DwellerStatusEnum
from app.core.game_config import game_config
from app.models.dweller import Dweller
from app.models.game_state import GameState
from app.models.vault import Vault
from app.options.identity_modifiers import identity_modifiers_for

MS_PER_MINUTE = 60_000
# Away dwellers eat and drink from their own packs, so the vault ladder skips them.
AWAY_STATUSES = (DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING)


def eligible_ms(counter_ms: int, grace_minutes: int) -> int:
    """Deprived milliseconds that count toward damage, after the grace window."""
    return max(0, counter_ms - grace_minutes * MS_PER_MINUTE)


def cumulative_amount(max_health: int, eligible: int, fraction_per_min: float) -> int:
    """Whole HP (or radiation) owed after this much eligible deprivation."""
    return int(max_health * fraction_per_min * (eligible / MS_PER_MINUTE))


def hp_floor(max_health: int, fraction: float) -> int:
    """Lowest health deprivation alone may reach, never below 1."""
    return max(1, math.ceil(max_health * fraction))


def _increment(max_health: int, before_ms: int, after_ms: int, grace_minutes: int, fraction_per_min: float) -> int:
    """Damage this pass owes: the cumulative amount gained, never negative however the counter moved."""
    return cumulative_amount(max_health, eligible_ms(after_ms, grace_minutes), fraction_per_min) - cumulative_amount(
        max_health, eligible_ms(before_ms, grace_minutes), fraction_per_min
    )


def output_multiplier(state: GameState | None) -> float:
    """Crew output while hungry or thirsty; production reads this before it computes room output."""
    if state is None:
        return 1.0
    health = game_config.health
    hungry = eligible_ms(state.food_deprived_ms, health.hunger_grace_minutes) > 0
    # The switch disables the water branch outright, so a latched counter must not keep penalising the crew.
    thirsty = health.water_deprivation_enabled and eligible_ms(state.water_deprived_ms, health.thirst_grace_minutes) > 0
    return health.hungry_output_multiplier if hungry or thirsty else 1.0


@dataclass
class DeprivationResult:
    """What one deprivation pass did, so the caller can warn and report.

    ``became_critical`` counts dwellers that crossed into the floor *on this pass*, not dwellers sitting at it:
    the critical warning is an event, so a vault parked at the floor must not re-warn every tick.
    """

    affected: int = 0
    became_critical: int = 0
    entered_hunger: bool = False
    entered_thirst: bool = False


async def apply_deprivation(
    db_session: AsyncSession,
    vault: Vault,
    state: GameState,
    dwellers: Sequence[Dweller],
    window_ms: int,
    *,
    dry_ms: dict[str, int] | None = None,
) -> DeprivationResult:
    """Accumulate deprived time, apply its increment, then reset on refill.

    ``dry_ms`` carries the milliseconds each resource actually spent empty inside the window, so a window that
    only ran dry for part of its length charges only that part. Without it the whole window counts, which is the
    right answer for a direct caller that only knows the elapsed time.
    """
    health = game_config.health
    food_before, water_before = state.food_deprived_ms, state.water_deprived_ms
    food_grace, water_grace = health.hunger_grace_minutes, health.thirst_grace_minutes
    water_enabled = health.water_deprivation_enabled
    food_ms = window_ms if dry_ms is None else dry_ms.get("food", 0)
    water_ms = window_ms if dry_ms is None else dry_ms.get("water", 0)

    if vault.food <= 0 and food_ms:
        state.food_deprived_ms += food_ms
    if water_enabled and vault.water <= 0 and water_ms:
        state.water_deprived_ms += water_ms

    food_before_eligible = eligible_ms(food_before, food_grace)
    food_after_eligible = eligible_ms(state.food_deprived_ms, food_grace)
    water_before_eligible = eligible_ms(water_before, water_grace)
    water_after_eligible = eligible_ms(state.water_deprived_ms, water_grace)
    result = DeprivationResult(
        entered_hunger=food_before_eligible == 0 and food_after_eligible > 0,
        entered_thirst=water_before_eligible == 0 and water_after_eligible > 0,
    )

    for dweller in dwellers:
        if dweller.status in AWAY_STATUSES:
            continue
        floor = hp_floor(dweller.max_health, health.deprivation_hp_floor_fraction)
        was_at_floor = dweller.health <= floor
        food_delta = _increment(
            dweller.max_health, food_before, state.food_deprived_ms, food_grace, health.food_erosion_fraction_per_min
        )
        water_delta = _increment(
            dweller.max_health,
            water_before,
            state.water_deprived_ms,
            water_grace,
            health.water_radiation_fraction_per_min,
        )

        eroded = False
        if food_delta > 0 and dweller.health > floor:
            dweller.health = max(floor, dweller.health - food_delta)
            eroded = True
        if water_delta > 0 and not identity_modifiers_for(dweller).radiation_immune:
            radiation_cap = max(dweller.radiation, dweller.max_health - floor)
            raised = min(dweller.radiation + water_delta, radiation_cap)
            if raised > dweller.radiation:
                dweller.radiation = raised
                dweller.health = min(dweller.health, max(floor, dweller.max_health - dweller.radiation))
                eroded = True
        if eroded:
            db_session.add(dweller)
            result.affected += 1
        if not was_at_floor and dweller.health <= floor:
            result.became_critical += 1

    # Any stock clears the ladder. A threshold above zero leaves a band where the vault holds food yet keeps
    # eroding health and keeps the crew penalty; if it runs dry again the grace window simply restarts.
    if vault.food > 0:
        state.food_deprived_ms = 0
    if water_enabled and vault.water > 0:
        state.water_deprived_ms = 0
    db_session.add(state)
    return result
