"""Graded deprivation: counters drive erosion, refill clears them, and nothing is lethal."""

import math

import pytest

from app.core.game_config import game_config
from app.models.game_state import GameState
from app.options.identity_modifiers import identity_modifiers_for
from app.services.game_tick.deprivation import apply_deprivation, cumulative_amount, eligible_ms, hp_floor


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
async def test_deprivation_never_commits_on_its_own(async_session, vault, dweller) -> None:
    from unittest.mock import AsyncMock, patch

    _arm(vault, dweller, food=0, water=150)
    state = await _state(async_session, vault, food_minutes=70)
    async_session.add_all([vault, dweller])
    await async_session.commit()

    with patch.object(async_session, "commit", new_callable=AsyncMock) as commit:
        await apply_deprivation(async_session, vault, state, [dweller], 600_000)
        commit.assert_not_awaited()

    assert dweller.health == 99
    assert state.food_deprived_ms == 80 * 60_000


def test_parity_build_buffer_stays_between_two_and_four_hours() -> None:
    room_capacity = 25 * 3 * (1 + 1)
    for population in (9, 20, 35, 50):
        rooms = math.ceil(population / 8.5)
        draw_per_minute = population * game_config.resource.food_consumption_per_dweller * 60
        buffer_minutes = rooms * room_capacity / draw_per_minute
        assert 120 <= buffer_minutes <= 240, (population, buffer_minutes)


def test_a_missed_cook_is_survivable_and_a_lost_crew_is_not() -> None:
    room_capacity = 25 * 3 * (1 + 1)
    population = 20
    rooms = math.ceil(population / 8.5)
    stock = rooms * room_capacity
    draw = population * game_config.resource.food_consumption_per_dweller * 60
    per_cook = 28 * 5 * game_config.resource.base_production_rate * 60

    one_short = stock / (draw - per_cook)
    crew_gone = stock / draw

    assert one_short >= 6 * 60
    assert crew_gone <= 3 * 60
