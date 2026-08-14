"""Run deterministic resource scenarios with the production ResourceManager.

Usage:
    cd backend
    uv run python scripts/simulate_resource_economy.py
    uv run python scripts/simulate_resource_economy.py --duration-minutes 120 --population 20
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from typing import Annotated

import typer

from app.core.game_config import game_config
from app.crud.room import CRUDRoom
from app.models import Dweller, Room, Vault
from app.schemas.common import RoomTypeEnum
from app.services.resource_manager import ResourceManager
from app.utils.static_data import game_data_store

RESOURCE_NAMES = ("power", "food", "water")


@dataclasses.dataclass(frozen=True)
class ResourceEconomyConfig:
    """Static staffing scenario evaluated with the live resource formulas."""

    duration_minutes: int = 60
    tick_interval: int = 60
    population: int = 10
    workers_per_room: int = 1
    worker_special: int = 1
    starting_power: float = 50
    starting_food: float = 50
    starting_water: float = 50
    resource_max: float = 100
    base_production_rate: float | None = None


@dataclasses.dataclass(frozen=True)
class ResourceEconomyResult:
    """Resource simulation output suitable for reports and balance comparisons."""

    initial_rates_per_minute: dict[str, float]
    final_resources: dict[str, float]
    forecasts_minutes: dict[str, float | None]


def _make_room(name: str) -> Room:
    room_data = next((room for room in game_data_store.rooms if room.name == name), None)
    if room_data is None or room_data.output_formula is None or room_data.ability is None:
        raise ValueError(f"Production room data missing for {name}")

    size = room_data.size_min
    return Room(
        name=room_data.name,
        category=RoomTypeEnum.PRODUCTION,
        ability=room_data.ability,
        output=CRUDRoom.evaluate_output_formula(room_data.output_formula, level=1, size=size),
        size=size,
        tier=1,
    )


def _make_workers(ability: str, count: int, special: int) -> list[Dweller]:
    return [Dweller(**{ability: special}) for _ in range(count)]


def _build_scenario(config: ResourceEconomyConfig) -> tuple[Vault, Sequence[Room], list[tuple[Room, list[Dweller]]]]:
    vault = Vault(
        power=config.starting_power,
        food=config.starting_food,
        water=config.starting_water,
        power_max=config.resource_max,
        food_max=config.resource_max,
        water_max=config.resource_max,
    )
    power_room = _make_room("Power Generator")
    food_room = _make_room("Diner")
    water_room = _make_room("Water Treatment")
    rooms = (power_room, food_room, water_room)
    rooms_with_dwellers = [
        (power_room, _make_workers("strength", config.workers_per_room, config.worker_special)),
        (food_room, _make_workers("agility", config.workers_per_room, config.worker_special)),
        (water_room, _make_workers("perception", config.workers_per_room, config.worker_special)),
    ]
    return vault, rooms, rooms_with_dwellers


def _forecast_minutes(current: float, maximum: float, rate: float) -> float | None:
    if rate < 0 and current > 0:
        return current / -rate
    if rate > 0 and current < maximum:
        return (maximum - current) / rate
    return None


@contextmanager
def _production_rate_override(rate: float | None) -> Iterator[None]:
    if rate is None:
        yield
        return

    original_rate = game_config.resource.base_production_rate
    game_config.resource.base_production_rate = rate
    try:
        yield
    finally:
        game_config.resource.base_production_rate = original_rate


def simulate(config: ResourceEconomyConfig) -> ResourceEconomyResult:
    """Simulate static staffing using ResourceManager's live calculations."""
    if config.duration_minutes <= 0 or config.tick_interval <= 0:
        raise ValueError("duration_minutes and tick_interval must be positive")
    if config.population < 0 or config.workers_per_room < 0:
        raise ValueError("population and workers_per_room must be non-negative")

    manager = ResourceManager()
    vault, rooms, rooms_with_dwellers = _build_scenario(config)
    initial_resources = {resource: float(getattr(vault, resource)) for resource in RESOURCE_NAMES}
    duration_seconds = config.duration_minutes * 60
    if duration_seconds % config.tick_interval:
        raise ValueError("duration_minutes must be an exact multiple of tick_interval")
    ticks = duration_seconds // config.tick_interval

    initial_rates: dict[str, float] = {}
    with _production_rate_override(config.base_production_rate):
        for tick in range(ticks):
            consumption = manager._calculate_consumption(rooms, config.population, config.tick_interval)
            production = manager._calculate_production(rooms_with_dwellers, config.tick_interval, vault.power)
            if tick == 0:
                initial_rates = {
                    resource: (production[resource] - consumption[resource]) / config.tick_interval * 60
                    for resource in RESOURCE_NAMES
                }

            new_resources = manager._apply_resource_changes(vault, consumption, production)
            for resource in RESOURCE_NAMES:
                setattr(vault, resource, round(new_resources[resource]))

    final_resources = {resource: float(getattr(vault, resource)) for resource in RESOURCE_NAMES}
    forecasts = {
        resource: _forecast_minutes(
            initial_resources[resource], getattr(vault, f"{resource}_max"), initial_rates[resource]
        )
        for resource in RESOURCE_NAMES
    }
    return ResourceEconomyResult(initial_rates, final_resources, forecasts)


def _format_forecast(minutes: float | None) -> str:
    if minutes is None:
        return "stable or capped"
    if minutes < 0.1:
        return "<0.1 min"
    return f"{minutes:.1f} min"


app = typer.Typer(help="Simulate static vault resource production and consumption with live formulas.")


@app.command()
def run(
    duration_minutes: Annotated[int, typer.Option(help="Scenario duration in minutes")] = 60,
    population: Annotated[int, typer.Option(help="Dwellers consuming food and water")] = 10,
    workers_per_room: Annotated[int, typer.Option(help="Workers assigned to each production room")] = 1,
    worker_special: Annotated[int, typer.Option(help="Relevant SPECIAL per production worker")] = 1,
    starting_power: Annotated[float, typer.Option()] = 50,
    starting_food: Annotated[float, typer.Option()] = 50,
    starting_water: Annotated[float, typer.Option()] = 50,
    base_production_rate: Annotated[
        float | None, typer.Option(help="Temporary candidate production rate per SPECIAL point per second")
    ] = None,
) -> None:
    """Print net rates, projected final resources, and first-tick forecasts."""
    result = simulate(
        ResourceEconomyConfig(
            duration_minutes=duration_minutes,
            population=population,
            workers_per_room=workers_per_room,
            worker_special=worker_special,
            starting_power=starting_power,
            starting_food=starting_food,
            starting_water=starting_water,
            base_production_rate=base_production_rate,
        )
    )
    typer.echo("Resource economy simulation (live ResourceManager formulas)")
    typer.echo("Resource | Net / min | Final | Forecast")
    typer.echo("---------|-----------|-------|---------")
    for resource in RESOURCE_NAMES:
        typer.echo(
            f"{resource.title():<8} | {result.initial_rates_per_minute[resource]:>+9.1f} | "
            f"{result.final_resources[resource]:>5.0f} | {_format_forecast(result.forecasts_minutes[resource])}"
        )


if __name__ == "__main__":
    app()
