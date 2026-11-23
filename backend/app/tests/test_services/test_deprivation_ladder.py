"""Graded deprivation: counters drive erosion, refill clears them, and nothing is lethal."""

import math
from uuid import uuid4

import pytest

from app.core.game_config import game_config
from app.core.game_data import get_static_game_data
from app.crud.room import CRUDRoom
from app.models.game_state import GameState
from app.options.identity_modifiers import identity_modifiers_for
from app.services.game_tick.deprivation import (
    apply_deprivation,
    cumulative_amount,
    eligible_ms,
    hp_floor,
    output_multiplier,
)

# Analytic band model. The parity build is tier-1 size-3 food rooms, and the Diner's catalog capacity formula is
# "25*S*(L+1)"; test_the_band_model_mirrors_the_catalog keeps that pin honest.
FOOD_ROOM_CAPACITY = 25 * 3 * (1 + 1)
DWELLERS_PER_FOOD_ROOM = 8.5
# docs/backend/BALANCE_WAVE_3.md: at the shipped rates one bare worker feeds about twelve dwellers.
DWELLERS_PER_BARE_WORKER = 12


def _food_draw_per_minute(population: int) -> float:
    return population * game_config.resource.food_consumption_per_dweller * 60


def _food_per_bare_worker() -> float:
    return DWELLERS_PER_BARE_WORKER * game_config.resource.food_consumption_per_dweller * 60


def test_eligible_ms_subtracts_the_grace_window() -> None:
    assert eligible_ms(0, 30) == 0
    assert eligible_ms(30 * 60_000, 30) == 0
    assert eligible_ms(31 * 60_000, 30) == 60_000


def test_cumulative_amount_is_whole_hp() -> None:
    assert cumulative_amount(100, 10 * 60_000, 0.0010) == 1
    assert cumulative_amount(100, 20 * 60_000, 0.0010) == 2


def test_hp_floor_never_below_one() -> None:
    assert hp_floor(100, 0.25) == 25
    assert hp_floor(3, 0.25) == 1


async def _state(async_session, vault, *, food_minutes: int = 0, water_minutes: int = 0) -> GameState:
    state = GameState(
        vault_id=vault.id,
        food_deprived_ms=food_minutes * 60_000,
        water_deprived_ms=water_minutes * 60_000,
    )
    async_session.add(state)
    await async_session.commit()
    return state


def _arm(vault, dweller, *, food: int = 0, water: int = 0, health: int = 100, radiation: int = 0) -> None:
    vault.food = food
    vault.water = water
    vault.food_max = max(vault.food_max, 150)
    vault.water_max = max(vault.water_max, 150)
    dweller.max_health = 100
    dweller.health = health
    dweller.radiation = radiation


@pytest.mark.asyncio
async def test_food_deprivation_erodes_health_by_the_increment(async_session, vault, dweller) -> None:
    _arm(vault, dweller, food=0)
    state = await _state(async_session, vault, food_minutes=70)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    result = await apply_deprivation(async_session, vault, state, [dweller], 600_000)
    await async_session.commit()
    await async_session.refresh(dweller)

    assert result.affected == 1
    assert dweller.health == 99


@pytest.mark.asyncio
async def test_refill_clears_the_counter_without_healing(async_session, vault, dweller) -> None:
    _arm(vault, dweller, food=150, health=90)
    state = await _state(async_session, vault, food_minutes=200)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    result = await apply_deprivation(async_session, vault, state, [dweller], 60_000)
    await async_session.commit()

    assert result.affected == 0
    assert state.food_deprived_ms == 0
    assert dweller.health == 90


@pytest.mark.asyncio
async def test_deprivation_stops_at_the_floor(async_session, vault, dweller) -> None:
    _arm(vault, dweller, food=0, health=26)
    state = await _state(async_session, vault, food_minutes=5_000)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    await apply_deprivation(async_session, vault, state, [dweller], 600_000)
    await async_session.commit()

    assert dweller.health == 25
    assert dweller.is_dead is False


@pytest.mark.asyncio
async def test_food_and_water_channels_compose(async_session, vault, dweller) -> None:
    _arm(vault, dweller, food=0, water=0)
    state = await _state(async_session, vault, food_minutes=70, water_minutes=40)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    await apply_deprivation(async_session, vault, state, [dweller], 600_000)
    await async_session.commit()
    await async_session.refresh(dweller)

    assert dweller.health < 100
    assert dweller.radiation == 2


@pytest.mark.asyncio
async def test_one_long_window_matches_repeated_short_windows(async_session, vault, dweller) -> None:
    _arm(vault, dweller, food=0)
    state = await _state(async_session, vault, food_minutes=70)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    await apply_deprivation(async_session, vault, state, [dweller], 600_000)
    long_health = dweller.health

    state.food_deprived_ms = 70 * 60_000
    dweller.health = 100
    for _ in range(10):
        await apply_deprivation(async_session, vault, state, [dweller], 60_000)

    assert dweller.health == long_health


@pytest.mark.asyncio
async def test_radiation_immune_dwellers_ignore_the_water_channel(async_session, vault, dweller) -> None:
    dweller.visual_attributes = {"race": "ghoul"}
    assert identity_modifiers_for(dweller).radiation_immune is True
    _arm(vault, dweller, water=0)
    state = await _state(async_session, vault, water_minutes=40)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    await apply_deprivation(async_session, vault, state, [dweller], 600_000)
    await async_session.commit()

    assert dweller.radiation == 0


@pytest.mark.asyncio
async def test_deprivation_stages_inside_the_caller_transaction(async_session, vault, dweller) -> None:
    """Staged, then rolled back: nothing deprivation wrote may survive without the caller's commit."""
    _arm(vault, dweller, food=0, water=150, health=90)
    state = await _state(async_session, vault, food_minutes=70)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    await apply_deprivation(async_session, vault, state, [dweller], 600_000)
    assert dweller.health < 90
    await async_session.rollback()
    await async_session.refresh(dweller)
    await async_session.refresh(state)

    assert dweller.health == 90
    assert state.food_deprived_ms == 70 * 60_000


@pytest.mark.asyncio
async def test_any_refill_clears_the_ladder(async_session, vault, dweller) -> None:
    """A vault holding food must not keep eroding: a 5 % threshold left a band that starved while fed."""
    _arm(vault, dweller, food=1, health=90)
    state = await _state(async_session, vault, food_minutes=200)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    result = await apply_deprivation(async_session, vault, state, [dweller], 60_000)
    await async_session.commit()

    assert result.affected == 0
    assert state.food_deprived_ms == 0
    assert dweller.health == 90


@pytest.mark.asyncio
async def test_critical_is_a_transition_not_a_state(async_session, vault, dweller) -> None:
    """A dweller crossing into the floor reports once; parked there, it must not re-report on every pass."""
    _arm(vault, dweller, food=0, health=26)
    state = await _state(async_session, vault, food_minutes=5_000)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    first = await apply_deprivation(async_session, vault, state, [dweller], 600_000)
    second = await apply_deprivation(async_session, vault, state, [dweller], 600_000)

    assert dweller.health == 25
    assert first.became_critical == 1
    assert second.became_critical == 0


@pytest.mark.asyncio
async def test_a_wounded_dweller_is_not_a_deprivation_crisis(async_session, vault, dweller) -> None:
    """Low health with full stores is a medbay problem; the deprivation warning must not claim it."""
    _arm(vault, dweller, food=150, water=150, health=20)
    state = await _state(async_session, vault)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    result = await apply_deprivation(async_session, vault, state, [dweller], 60_000)

    assert result.became_critical == 0
    assert result.affected == 0
    assert dweller.health == 20


def test_the_water_switch_drops_the_thirst_penalty(monkeypatch) -> None:
    """Turning the water branch off must release the crew penalty a latched counter would otherwise keep."""
    state = GameState(vault_id=uuid4(), water_deprived_ms=40 * 60_000)
    assert output_multiplier(state) == game_config.health.hungry_output_multiplier

    monkeypatch.setattr(game_config.health, "water_deprivation_enabled", False)

    assert output_multiplier(state) == 1.0


def test_parity_build_buffer_stays_between_two_and_four_hours() -> None:
    for population in (9, 20, 35, 50):
        rooms = math.ceil(population / DWELLERS_PER_FOOD_ROOM)
        draw_per_minute = _food_draw_per_minute(population)
        buffer_minutes = rooms * FOOD_ROOM_CAPACITY / draw_per_minute
        assert 120 <= buffer_minutes <= 240, (population, buffer_minutes)


def test_a_missed_cook_is_survivable_and_a_lost_crew_is_not() -> None:
    population = 20
    rooms = math.ceil(population / DWELLERS_PER_FOOD_ROOM)
    stock = rooms * FOOD_ROOM_CAPACITY
    draw = _food_draw_per_minute(population)

    one_short = stock / (draw - _food_per_bare_worker())
    crew_gone = stock / draw

    assert one_short >= 6 * 60
    assert crew_gone <= 3 * 60


@pytest.mark.asyncio
async def test_the_band_model_mirrors_the_catalog() -> None:
    """The bands above are analytic, so their inputs must still be the catalog's: a Diner holds 25*S*(L+1)."""
    game_data = await get_static_game_data()
    diner = next(room for room in game_data.rooms if room.name == "Diner")
    formula = diner.capacity_formula
    assert formula is not None
    assert CRUDRoom.evaluate_output_formula(formula, level=1, size=3) == FOOD_ROOM_CAPACITY
