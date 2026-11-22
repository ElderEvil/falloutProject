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
REFILL_FRACTION = 0.05


def eligible_ms(counter_ms: int, grace_minutes: int) -> int:
    """Deprived milliseconds that count toward damage, after the grace window."""
    return max(0, counter_ms - grace_minutes * MS_PER_MINUTE)


def cumulative_amount(max_health: int, eligible: int, fraction_per_min: float) -> int:
    """Whole HP (or radiation) owed after this much eligible deprivation."""
    return int(max_health * fraction_per_min * (eligible / MS_PER_MINUTE))


def hp_floor(max_health: int, fraction: float) -> int:
    """Lowest health deprivation alone may reach, never below 1."""
    return max(1, math.ceil(max_health * fraction))


def is_hungry(state: GameState | None) -> bool:
    return state is not None and eligible_ms(state.food_deprived_ms, game_config.health.hunger_grace_minutes) > 0


def is_thirsty(state: GameState | None) -> bool:
    return state is not None and eligible_ms(state.water_deprived_ms, game_config.health.thirst_grace_minutes) > 0


def output_multiplier(state: GameState | None) -> float:
    """Crew output while hungry or thirsty; production reads this before it computes room output."""
    if state is None or not (is_hungry(state) or is_thirsty(state)):
        return 1.0
    return game_config.health.hungry_output_multiplier


@dataclass
class DeprivationResult:
    """What one deprivation pass did, so the caller can warn and report."""

    affected: int = 0
    critical: int = 0
    entered_hunger: bool = False
    entered_thirst: bool = False


async def apply_deprivation(
    db_session: AsyncSession,
    vault: Vault,
    state: GameState,
    dwellers: Sequence[Dweller],
    window_ms: int,
) -> DeprivationResult:
    """Accumulate deprived time, apply its increment, then reset on refill."""
    health = game_config.health
    food_before, water_before = state.food_deprived_ms, state.water_deprived_ms
    food_grace, water_grace = health.hunger_grace_minutes, health.thirst_grace_minutes
    water_enabled = health.dehydration_radiation_per_tick > 0

    if vault.food <= 0:
        state.food_deprived_ms += window_ms
    if water_enabled and vault.water <= 0:
        state.water_deprived_ms += window_ms

    food_after_eligible = eligible_ms(state.food_deprived_ms, food_grace)
    water_after_eligible = eligible_ms(state.water_deprived_ms, water_grace)
    result = DeprivationResult(
        entered_hunger=eligible_ms(food_before, food_grace) == 0 < food_after_eligible,
        entered_thirst=eligible_ms(water_before, water_grace) == 0 < water_after_eligible,
    )

    for dweller in dwellers:
        if dweller.status in (DwellerStatusEnum.EXPLORING, DwellerStatusEnum.QUESTING):
            continue
        floor = hp_floor(dweller.max_health, health.deprivation_hp_floor_fraction)
        food_delta = cumulative_amount(
            dweller.max_health, food_after_eligible, health.food_erosion_fraction_per_min
        ) - cumulative_amount(
            dweller.max_health, eligible_ms(food_before, food_grace), health.food_erosion_fraction_per_min
        )
        water_delta = cumulative_amount(
            dweller.max_health, water_after_eligible, health.water_radiation_fraction_per_min
        ) - cumulative_amount(
            dweller.max_health, eligible_ms(water_before, water_grace), health.water_radiation_fraction_per_min
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
        if dweller.health <= floor:
            result.critical += 1

    if vault.food > vault.food_max * REFILL_FRACTION:
        state.food_deprived_ms = 0
    if water_enabled and vault.water > vault.water_max * REFILL_FRACTION:
        state.water_deprived_ms = 0
    db_session.add(state)
    return result
