"""Tests for the deterministic resource-economy simulator."""

import pytest
from scripts.simulate_resource_economy import ResourceEconomyConfig, simulate


def test_simulate_uses_live_resource_production_and_consumption_rates() -> None:
    """The report should be derived from ResourceManager's current formulas."""
    result = simulate(
        ResourceEconomyConfig(
            duration_minutes=1,
            population=10,
            workers_per_room=1,
            worker_special=1,
            starting_power=10,
            starting_food=10,
            starting_water=10,
        )
    )

    assert result.initial_rates_per_minute == pytest.approx({"power": 163.5, "food": 164.4, "water": 164.4})
    assert result.final_resources == {"power": 100.0, "food": 100.0, "water": 100.0}
    assert result.forecasts_minutes == pytest.approx({"power": 90 / 163.5, "food": 90 / 164.4, "water": 90 / 164.4})


def test_simulate_reports_power_outage_stopping_food_and_water_production() -> None:
    """The simulation preserves the live power-outage production rule."""
    result = simulate(
        ResourceEconomyConfig(
            duration_minutes=1,
            population=10,
            workers_per_room=1,
            worker_special=1,
            starting_power=0,
            starting_food=10,
            starting_water=10,
        )
    )

    assert result.initial_rates_per_minute == pytest.approx({"power": 163.5, "food": -3.6, "water": -3.6})


def test_simulate_can_compare_a_candidate_production_rate() -> None:
    """Balance experiments can override only the production rate for one run."""
    result = simulate(
        ResourceEconomyConfig(
            duration_minutes=1,
            population=9,
            workers_per_room=2,
            worker_special=5,
            starting_power=50,
            starting_food=50,
            starting_water=50,
            base_production_rate=0.0004,
        )
    )

    assert result.initial_rates_per_minute == pytest.approx({"power": 2.22, "food": 3.48, "water": 3.48})


@pytest.mark.parametrize("field", ["population", "workers_per_room"])
def test_simulate_rejects_negative_population_and_worker_counts(field: str) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        simulate(ResourceEconomyConfig(**{field: -1}))


def test_simulate_rejects_duration_that_does_not_match_ticks() -> None:
    with pytest.raises(ValueError, match="exact multiple"):
        simulate(ResourceEconomyConfig(duration_minutes=1, tick_interval=45))
