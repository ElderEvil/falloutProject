"""Tests for the deterministic resource-economy simulator."""

import pytest

from app.cli.simulate_resources import ResourceEconomyConfig, simulate


@pytest.mark.parametrize("field", ["population", "workers_per_room"])
def test_simulate_rejects_negative_population_and_worker_counts(field: str) -> None:
    with pytest.raises(ValueError, match="non-negative"):
        simulate(ResourceEconomyConfig(**{field: -1}))
