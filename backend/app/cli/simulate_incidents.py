"""Incident Balance Simulator — focused combat and incident system simulation.

Simulates incident spawning, combat resolution, spread mechanics, deaths,
and resource impact to help balance vault defenses and incident difficulty.
Incident kinds, spawn weights, difficulty ranges and the tuning baseline are
read from ``game_config``, so the check always covers every kind the game can
roll. Combat is resolved by the pure kernel in
``app.services.combat.incident_sim`` — a faithful mirror of the production
round engine — seeded either from synthetic defenders or from a real vault's
healthy adults. Run standalone without the full backend.

Usage:
    cd backend
    uv run fo-cli simulate-incidents
    uv run fo-cli simulate-incidents --days 3 --runs 50
    uv run fo-cli simulate-incidents --sweep spawn_chance_per_hour
    uv run fo-cli simulate-incidents --vault-id <uuid>
"""

from __future__ import annotations

import asyncio
import dataclasses
import random
import statistics
import uuid
from collections.abc import Callable
from functools import partial
from typing import Annotated, Any

import typer

from app.cli.simulate_common import (
    CurvesMixin,
    banner,
    fmt_stats,
    print_hourly_curves,
)
from app.cli.simulate_common import (
    print_sweep_report as shared_print_sweep_report,
)
from app.cli.simulate_common import (
    run_parameter_sweep as shared_run_parameter_sweep,
)
from app.cli.simulate_common import (
    stats as _stats,
)
from app.core.game_config import game_config
from app.models.incident import IncidentType
from app.services.combat.incident_sim import DefenderProfile, SimDefender, resolve_incident
from app.services.combat.incident_sim_roster import synthetic_defenders

DEFAULT_SIMULATION_DAYS = 3
DEFAULT_RUNS = 50

# Simulator-only assumptions with no game_config analogue.
DEFAULT_STARTING_DWELLERS = 20
DEFAULT_STARTING_ADULTS = 18
DEFAULT_AVG_SPECIAL = 4.0
DEFAULT_AVG_WEAPON_DAMAGE = 10.0
DEFAULT_AVG_LEVEL = 5
DEFAULT_RESOURCE_DRAIN_PER_TICK = 0.5
DEFAULT_HAPPINESS_PENALTY_SPREAD = 3.0

# Incident knobs come from game_config, not a second copy, so new kinds and
# tuning changes flow straight into the balance check.
DEFAULT_TICK_INTERVAL = game_config.game_loop.tick_interval
DEFAULT_INCIDENT_DT = game_config.game_loop.incident_tick_seconds
DEFAULT_SPAWN_CHANCE_PER_HOUR = game_config.incident.spawn_chance_per_hour
DEFAULT_MIN_VAULT_POPULATION = game_config.incident.min_vault_population
DEFAULT_MAX_ACTIVE_INCIDENTS = game_config.incident.max_active_incidents
DEFAULT_SPAWN_COOLDOWN_SECONDS = game_config.incident.spawn_cooldown_seconds
DEFAULT_SPREAD_DURATION = game_config.incident.spread_duration
DEFAULT_MAX_SPREAD_COUNT = game_config.incident.max_spread_count

DEFAULT_BASE_RAIDER_POWER = game_config.combat.base_raider_power
DEFAULT_LEVEL_BONUS_MULTIPLIER = game_config.combat.level_bonus_multiplier

DEFAULT_CAPS_REWARD_BASE = game_config.combat.caps_reward_base
DEFAULT_CAPS_REWARD_PER_DIFFICULTY = game_config.combat.caps_reward_per_difficulty

DEFAULT_HAPPINESS_PENALTY_ACTIVE = game_config.happiness.incident_penalty
DEFAULT_HEAL_PER_TICK = game_config.health.regen_per_tick

# Responder-selection knobs (simulator-only).
DEFAULT_DEFENDERS_PER_INCIDENT = 6
DEFAULT_RESPONSE_RATE = 1.0

INCIDENT_TYPES: list[IncidentType] = list(IncidentType)
EXTERNAL_INCIDENTS: set[IncidentType] = {IncidentType(value) for value in game_config.incident.vault_door_incidents}


@dataclasses.dataclass(frozen=True)
class IncidentConfig:
    tick_interval: int = DEFAULT_TICK_INTERVAL
    incident_dt: int = DEFAULT_INCIDENT_DT
    spawn_chance_per_hour: float = DEFAULT_SPAWN_CHANCE_PER_HOUR
    min_vault_population: int = DEFAULT_MIN_VAULT_POPULATION
    max_active_incidents: int = DEFAULT_MAX_ACTIVE_INCIDENTS
    spawn_cooldown_seconds: int = DEFAULT_SPAWN_COOLDOWN_SECONDS
    spread_duration: int = DEFAULT_SPREAD_DURATION
    max_spread_count: int = DEFAULT_MAX_SPREAD_COUNT

    base_raider_power: int = DEFAULT_BASE_RAIDER_POWER
    level_bonus_multiplier: int = DEFAULT_LEVEL_BONUS_MULTIPLIER
    avg_special: float = DEFAULT_AVG_SPECIAL
    avg_weapon_damage: float = DEFAULT_AVG_WEAPON_DAMAGE
    avg_level: int = DEFAULT_AVG_LEVEL

    caps_reward_base: int = DEFAULT_CAPS_REWARD_BASE
    caps_reward_per_difficulty: int = DEFAULT_CAPS_REWARD_PER_DIFFICULTY

    resource_drain_per_tick: float = DEFAULT_RESOURCE_DRAIN_PER_TICK
    happiness_penalty_active: float = DEFAULT_HAPPINESS_PENALTY_ACTIVE
    happiness_penalty_spread: float = DEFAULT_HAPPINESS_PENALTY_SPREAD

    starting_dwellers: int = DEFAULT_STARTING_DWELLERS
    starting_adults: int = DEFAULT_STARTING_ADULTS

    defenders_per_incident: int = DEFAULT_DEFENDERS_PER_INCIDENT
    response_rate: float = DEFAULT_RESPONSE_RATE
    heal_per_tick: int = DEFAULT_HEAL_PER_TICK

    power_max: float = 100.0
    food_max: float = 100.0
    water_max: float = 100.0

    def roll_difficulty(self, incident_type: IncidentType, rng: random.Random) -> int:
        low, high = game_config.incident.get_difficulty_range(incident_type)
        return rng.randint(low, high)


@dataclasses.dataclass
class Incident:
    start_time: int
    incident_type: IncidentType
    difficulty: int
    spread_count: int = 0
    resolved: bool = False
    deaths: int = 0
    caps_rewarded: int = 0

    def elapsed(self, now: int) -> int:
        return now - self.start_time

    def is_external(self) -> bool:
        return self.incident_type in EXTERNAL_INCIDENTS


@dataclasses.dataclass
class VaultState:
    population: int = DEFAULT_STARTING_DWELLERS
    adults: int = DEFAULT_STARTING_ADULTS
    children: int = DEFAULT_STARTING_DWELLERS - DEFAULT_STARTING_ADULTS
    roster: list[SimDefender] = dataclasses.field(default_factory=list)
    power: float = 100.0
    food: float = 100.0
    water: float = 100.0
    happiness: float = 75.0
    caps: int = 500
    incidents: list[Incident] = dataclasses.field(default_factory=list)
    total_deaths: int = 0
    deaths_by_type: dict[IncidentType, int] = dataclasses.field(
        default_factory=lambda: dict.fromkeys(INCIDENT_TYPES, 0)
    )
    incidents_by_type: dict[IncidentType, int] = dataclasses.field(
        default_factory=lambda: dict.fromkeys(INCIDENT_TYPES, 0)
    )
    incidents_resolved: int = 0
    incidents_failed: int = 0
    total_caps_from_incidents: int = 0


@dataclasses.dataclass
class SimulationResult:
    config: IncidentConfig
    total_ticks: int
    total_incidents: int
    incidents_resolved: int
    incidents_failed: int
    total_deaths: int
    total_caps_rewarded: int

    deaths_by_type: dict[IncidentType, int]
    incidents_by_type: dict[IncidentType, int]

    population_by_hour: list[int]
    deaths_by_hour: list[int]
    incidents_by_hour: list[int]
    power_by_hour: list[float]
    food_by_hour: list[float]
    water_by_hour: list[float]
    happiness_by_hour: list[float]

    survival_rate: float
    avg_resolution_time_ticks: float
    max_concurrent_incidents: int


class IncidentSimulator:
    def __init__(self, config: IncidentConfig) -> None:
        self.cfg = config
        if config.tick_interval % config.incident_dt != 0:
            raise ValueError("tick_interval must be a multiple of incident_dt")

    def _build_synthetic_roster(self) -> list[DefenderProfile]:
        return synthetic_defenders(
            self.cfg.starting_adults,
            avg_special=self.cfg.avg_special,
            avg_weapon_damage=self.cfg.avg_weapon_damage,
            avg_level=self.cfg.avg_level,
        )

    def run(
        self,
        simulation_hours: int,
        seed: int | None = None,
        base_roster: list[DefenderProfile] | None = None,
    ) -> SimulationResult:
        rng = random.Random(seed)

        duration_seconds = simulation_hours * 3600
        ticks = duration_seconds // self.cfg.tick_interval + 1

        roster = [
            SimDefender(profile=profile, health=profile.max_health)
            for profile in (base_roster if base_roster is not None else self._build_synthetic_roster())
        ]
        population = len(roster) if base_roster is not None else max(self.cfg.starting_dwellers, len(roster))
        vault = VaultState(population=population, adults=len(roster), children=population - len(roster), roster=roster)
        last_spawn_time = -self.cfg.spawn_cooldown_seconds
        max_concurrent = 0
        resolution_times: list[int] = []

        pop_curve = [0] * simulation_hours
        deaths_curve = [0] * simulation_hours
        incidents_curve = [0] * simulation_hours
        power_curve = [0.0] * simulation_hours
        food_curve = [0.0] * simulation_hours
        water_curve = [0.0] * simulation_hours
        happy_curve = [0.0] * simulation_hours

        for tick in range(ticks):
            now = tick * self.cfg.tick_interval
            hour_idx = min(now // 3600, simulation_hours - 1)

            self._resolve_incidents(vault, resolution_times, rng)
            spawned = self._spawn_incidents(vault, now, last_spawn_time, rng)
            active_after = len([i for i in vault.incidents if not i.resolved])
            max_concurrent = max(max_concurrent, active_after)

            if active_after > 0:
                self._apply_incident_pressure(vault)

            if spawned:
                last_spawn_time = now
                incidents_curve[hour_idx] += 1

            self._regen_defenders(vault)

            pop_curve[hour_idx] = vault.population
            deaths_curve[hour_idx] = vault.total_deaths
            power_curve[hour_idx] = vault.power
            food_curve[hour_idx] = vault.food
            water_curve[hour_idx] = vault.water
            happy_curve[hour_idx] = vault.happiness

        resolved = vault.incidents_resolved
        failed = vault.incidents_failed
        total = resolved + failed
        survival = resolved / total if total > 0 else 1.0
        avg_time = statistics.mean(resolution_times) if resolution_times else 0.0

        return SimulationResult(
            config=self.cfg,
            total_ticks=ticks,
            total_incidents=total,
            incidents_resolved=resolved,
            incidents_failed=failed,
            total_deaths=vault.total_deaths,
            total_caps_rewarded=vault.total_caps_from_incidents,
            deaths_by_type=vault.deaths_by_type,
            incidents_by_type=vault.incidents_by_type,
            population_by_hour=pop_curve,
            deaths_by_hour=deaths_curve,
            incidents_by_hour=incidents_curve,
            power_by_hour=power_curve,
            food_by_hour=food_curve,
            water_by_hour=water_curve,
            happiness_by_hour=happy_curve,
            survival_rate=survival,
            avg_resolution_time_ticks=avg_time,
            max_concurrent_incidents=max_concurrent,
        )

    def _resolve_incidents(self, vault: VaultState, resolution_times: list[int], rng: random.Random) -> None:
        for incident in vault.incidents:
            if incident.resolved:
                continue

            living = [defender for defender in vault.roster if defender.health > 0]
            if rng.random() < self.cfg.response_rate:
                k = min(self.cfg.defenders_per_incident, len(living))
                responders = rng.sample(living, k) if k > 0 else []
            else:
                responders = []

            outcome = resolve_incident(
                incident.incident_type,
                incident.difficulty,
                responders,
                dt=self.cfg.incident_dt,
                duration=self.cfg.spread_duration,
                max_spread_count=self.cfg.max_spread_count,
            )

            incident.deaths += outcome.deaths
            vault.total_deaths += outcome.deaths
            vault.deaths_by_type[incident.incident_type] += outcome.deaths
            vault.adults = max(0, vault.adults - outcome.deaths)
            vault.population = max(0, vault.population - outcome.deaths)

            if outcome.resolved:
                incident.resolved = True
                vault.incidents_resolved += 1
                reward = self.cfg.caps_reward_base + incident.difficulty * self.cfg.caps_reward_per_difficulty
                incident.caps_rewarded = reward
                vault.caps += reward
                vault.total_caps_from_incidents += reward
                resolution_times.append(outcome.ticks)
            elif outcome.failed:
                incident.resolved = True
                vault.incidents_failed += 1
                resolution_times.append(outcome.ticks)

    def _spawn_incidents(self, vault: VaultState, now: int, last_spawn_time: int, rng: random.Random) -> bool:
        if vault.population < self.cfg.min_vault_population:
            return False

        active = len([i for i in vault.incidents if not i.resolved])
        if active >= self.cfg.max_active_incidents:
            return False

        seconds_since_last = now - last_spawn_time
        if seconds_since_last < self.cfg.spawn_cooldown_seconds:
            return False

        hours_passed = min(self.cfg.tick_interval / 3600, 2.0)
        spawn_chance = self.cfg.spawn_chance_per_hour * hours_passed
        if rng.random() >= spawn_chance:
            return False

        weights = game_config.incident.get_spawn_weights()
        incident_type = rng.choices(list(weights), weights=list(weights.values()), k=1)[0]
        difficulty = self.cfg.roll_difficulty(incident_type, rng)

        incident = Incident(
            start_time=now,
            incident_type=incident_type,
            difficulty=difficulty,
        )
        vault.incidents.append(incident)
        vault.incidents_by_type[incident_type] += 1
        vault.happiness -= self.cfg.happiness_penalty_active
        return True

    def _regen_defenders(self, vault: VaultState) -> None:
        if self.cfg.heal_per_tick <= 0:
            return
        for defender in vault.roster:
            if defender.health <= 0:
                continue
            defender.health = min(defender.profile.max_health, defender.health + self.cfg.heal_per_tick)

    def _apply_incident_pressure(self, vault: VaultState) -> None:
        active_count = len([i for i in vault.incidents if not i.resolved])
        drain = active_count * self.cfg.resource_drain_per_tick
        vault.power = max(0, vault.power - drain)
        vault.food = max(0, vault.food - drain)
        vault.water = max(0, vault.water - drain)
        vault.happiness = max(0, vault.happiness - self.cfg.happiness_penalty_active)


BatchResult = dict[str, Any]


@dataclasses.dataclass
class _Aggregates:
    total_incidents: list[int] = dataclasses.field(default_factory=list)
    incidents_resolved: list[int] = dataclasses.field(default_factory=list)
    incidents_failed: list[int] = dataclasses.field(default_factory=list)
    total_deaths: list[int] = dataclasses.field(default_factory=list)
    total_caps: list[int] = dataclasses.field(default_factory=list)
    survival_rate: list[float] = dataclasses.field(default_factory=list)
    avg_resolution_time: list[float] = dataclasses.field(default_factory=list)
    max_concurrent: list[int] = dataclasses.field(default_factory=list)
    final_pop: list[int] = dataclasses.field(default_factory=list)
    final_power: list[float] = dataclasses.field(default_factory=list)
    final_food: list[float] = dataclasses.field(default_factory=list)
    final_water: list[float] = dataclasses.field(default_factory=list)
    final_happiness: list[float] = dataclasses.field(default_factory=list)

    def collect(self, result: SimulationResult) -> None:
        self.total_incidents.append(result.total_incidents)
        self.incidents_resolved.append(result.incidents_resolved)
        self.incidents_failed.append(result.incidents_failed)
        self.total_deaths.append(result.total_deaths)
        self.total_caps.append(result.total_caps_rewarded)
        self.survival_rate.append(result.survival_rate)
        self.avg_resolution_time.append(result.avg_resolution_time_ticks)
        self.max_concurrent.append(result.max_concurrent_incidents)
        self.final_pop.append(result.population_by_hour[-1] if result.population_by_hour else 0)
        self.final_power.append(result.power_by_hour[-1] if result.power_by_hour else 0)
        self.final_food.append(result.food_by_hour[-1] if result.food_by_hour else 0)
        self.final_water.append(result.water_by_hour[-1] if result.water_by_hour else 0)
        self.final_happiness.append(result.happiness_by_hour[-1] if result.happiness_by_hour else 0)


@dataclasses.dataclass
class _Curves(CurvesMixin):
    pop: list[float] = dataclasses.field(default_factory=list)
    deaths: list[float] = dataclasses.field(default_factory=list)
    incidents: list[float] = dataclasses.field(default_factory=list)
    power: list[float] = dataclasses.field(default_factory=list)
    food: list[float] = dataclasses.field(default_factory=list)
    water: list[float] = dataclasses.field(default_factory=list)
    happiness: list[float] = dataclasses.field(default_factory=list)

    def add_result(self, result: SimulationResult, hours: int) -> None:
        for h in range(hours):
            self.pop[h] += result.population_by_hour[h]
            self.deaths[h] += result.deaths_by_hour[h]
            self.incidents[h] += result.incidents_by_hour[h]
            self.power[h] += result.power_by_hour[h]
            self.food[h] += result.food_by_hour[h]
            self.water[h] += result.water_by_hour[h]
            self.happiness[h] += result.happiness_by_hour[h]


def run_monte_carlo(
    config: IncidentConfig,
    simulation_hours: int,
    runs: int,
    seed: int | None = None,
    base_roster: list[DefenderProfile] | None = None,
    roster_loader: Callable[[], list[DefenderProfile]] | None = None,
) -> BatchResult:
    sim = IncidentSimulator(config)
    ag = _Aggregates()
    curves = _Curves.zeroed(simulation_hours)
    deaths_by_type: dict[IncidentType, list[int]] = {t: [] for t in INCIDENT_TYPES}
    incidents_by_type: dict[IncidentType, list[int]] = {t: [] for t in INCIDENT_TYPES}

    for i in range(runs):
        run_seed = seed + i if seed is not None else None
        roster = roster_loader() if roster_loader is not None else base_roster
        result = sim.run(simulation_hours, seed=run_seed, base_roster=roster)
        ag.collect(result)
        curves.add_result(result, simulation_hours)
        for t in INCIDENT_TYPES:
            deaths_by_type[t].append(result.deaths_by_type[t])
            incidents_by_type[t].append(result.incidents_by_type[t])

    curves.divide(runs)

    return {
        "config": config,
        "runs": runs,
        "simulation_hours": simulation_hours,
        "total_incidents": _stats(ag.total_incidents),
        "incidents_resolved": _stats(ag.incidents_resolved),
        "incidents_failed": _stats(ag.incidents_failed),
        "total_deaths": _stats(ag.total_deaths),
        "total_caps": _stats(ag.total_caps),
        "survival_rate": _stats(ag.survival_rate),
        "avg_resolution_time": _stats(ag.avg_resolution_time),
        "max_concurrent": _stats(ag.max_concurrent),
        "population": _stats(ag.final_pop),
        "final_power": _stats(ag.final_power),
        "final_food": _stats(ag.final_food),
        "final_water": _stats(ag.final_water),
        "final_happiness": _stats(ag.final_happiness),
        "deaths_by_type": {t: _stats(deaths_by_type[t]) for t in INCIDENT_TYPES},
        "incidents_by_type": {t: _stats(incidents_by_type[t]) for t in INCIDENT_TYPES},
        "pop_curve": curves.pop,
        "deaths_curve": curves.deaths,
        "incidents_curve": curves.incidents,
        "power_curve": curves.power,
        "food_curve": curves.food,
        "water_curve": curves.water,
        "happiness_curve": curves.happiness,
    }


SWEEP_RANGES: dict[str, list[Any]] = {
    "spawn_chance_per_hour": [0.0, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20],
    "max_active_incidents": [1, 2, 3, 5, 8, 10],
    "spread_duration": [30, 60, 90, 120, 180],
    "max_spread_count": [0, 1, 2, 3, 5],
    "base_raider_power": [5, 10, 15, 20, 25],
    "starting_dwellers": [5, 10, 20, 30, 50],
    "avg_special": [2.0, 3.0, 4.0, 5.0, 6.0],
    "avg_weapon_damage": [5.0, 10.0, 15.0, 20.0],
    "defenders_per_incident": [1, 2, 4, 6, 10],
    "response_rate": [0.0, 0.25, 0.5, 0.75, 1.0],
    "resource_drain_per_tick": [0.0, 0.5, 1.0, 2.0, 3.0],
    "happiness_penalty_active": [1.0, 3.0, 5.0, 8.0, 10.0],
}


def run_parameter_sweep(
    param_name: str,
    baseline: IncidentConfig,
    simulation_hours: int,
    runs: int,
    base_roster: list[DefenderProfile] | None = None,
    roster_loader: Callable[[], list[DefenderProfile]] | None = None,
    seed: int | None = None,
) -> list[BatchResult]:
    def run_batch(config: IncidentConfig, hours: int, count: int) -> BatchResult:
        if param_name == "starting_dwellers" and base_roster is None and roster_loader is None:
            ratio = baseline.starting_adults / max(1, baseline.starting_dwellers)
            config = dataclasses.replace(config, starting_adults=int(config.starting_dwellers * ratio))
        return run_monte_carlo(config, hours, count, seed=seed, base_roster=base_roster, roster_loader=roster_loader)

    return shared_run_parameter_sweep(
        param_name,
        baseline,
        simulation_hours,
        runs,
        sweep_ranges=SWEEP_RANGES,
        run_monte_carlo=run_batch,
    )


def _print_params(cfg: IncidentConfig) -> None:
    print("Parameters:")
    print(f"  tick_interval       = {cfg.tick_interval}s")
    print(f"  incident_dt         = {cfg.incident_dt}s")
    print(f"  spawn_chance        = {cfg.spawn_chance_per_hour:.2%}/hour")
    print(f"  max_active          = {cfg.max_active_incidents}")
    print(f"  spread_duration     = {cfg.spread_duration}s")
    print(f"  max_spread          = {cfg.max_spread_count}")
    print(f"  raider_power        = {cfg.base_raider_power}")
    print(f"  starting_dwellers   = {cfg.starting_dwellers}")
    print(f"  avg_special         = {cfg.avg_special:.1f}")
    print(f"  avg_weapon_damage   = {cfg.avg_weapon_damage:.1f}")
    print(f"  avg_level           = {cfg.avg_level}")
    print(f"  defenders/incident  = {cfg.defenders_per_incident}")
    print(f"  response_rate       = {cfg.response_rate:.0%}")
    print(f"  heal_per_tick       = {cfg.heal_per_tick}")
    print(f"  resource_drain      = {cfg.resource_drain_per_tick:.1f}/tick")
    print(f"  happiness_penalty   = {cfg.happiness_penalty_active:.1f}/tick")
    print()


def _print_combat_stats(batch: BatchResult) -> None:
    print("Combat results:")
    print(f"  total incidents     : {fmt_stats(batch['total_incidents'])}")
    print(f"  resolved            : {fmt_stats(batch['incidents_resolved'])}")
    print(f"  failed (timed out)  : {fmt_stats(batch['incidents_failed'])}")
    print(f"  survival rate       : {fmt_stats(batch['survival_rate'])}")
    print(f"  avg resolution time : {fmt_stats(batch['avg_resolution_time'])} ticks")
    print(f"  max concurrent      : {fmt_stats(batch['max_concurrent'])}")
    print()


def _print_casualties(batch: BatchResult) -> None:
    print("Casualties by type:")
    for t in INCIDENT_TYPES:
        d = batch["deaths_by_type"][t]
        i = batch["incidents_by_type"][t]
        if i["mean"] > 0:
            death_rate = d["mean"] / i["mean"] if i["mean"] > 0 else 0
            print(
                f"  {t.value:20} : {d['mean']:.1f} deaths from {i['mean']:.1f} incidents (death_rate={death_rate:.2f})"
            )
    print(f"  total deaths        : {fmt_stats(batch['total_deaths'])}")
    print()


def _print_resources(batch: BatchResult) -> None:
    print("Final resource state:")
    print(f"  population  : {fmt_stats(batch['population'])}")
    print(f"  power       : {fmt_stats(batch['final_power'])}")
    print(f"  food        : {fmt_stats(batch['final_food'])}")
    print(f"  water       : {fmt_stats(batch['final_water'])}")
    print(f"  happiness   : {fmt_stats(batch['final_happiness'])}")
    print(f"  caps earned : {fmt_stats(batch['total_caps'])}")
    print()


def _print_hourly_curves(batch: BatchResult, hours: int) -> None:
    print_hourly_curves(batch, hours, deaths_key="deaths_curve", incidents_key="incidents_curve")


def _print_balance(batch: BatchResult, hours: int) -> None:
    mean_deaths = batch["total_deaths"]["mean"]
    mean_survival = batch["survival_rate"]["mean"]
    mean_incidents = batch["total_incidents"]["mean"]
    mean_pop = batch["population"]["mean"]
    starting_pop = batch["pop_curve"][0] if batch["pop_curve"] else 0

    print("Balance assessment:")
    if mean_survival < 0.5:
        print("  Survival rate below 50% — incidents too deadly for current defenses.")
    elif mean_survival < 0.8:
        print("  Survival rate 50-80% — challenging but manageable.")
    else:
        print("  Survival rate above 80% — incidents are too easy.")
    if mean_incidents > 0:
        print(f"  Deaths per incident={mean_deaths / mean_incidents:.2f} over {hours}h")
    else:
        print(f"  Deaths per incident=n/a (no incidents spawned) over {hours}h")
    print(f"  Population survived={mean_pop:.0f} from {starting_pop:.0f}")
    print()


def print_report(batch: BatchResult, detailed: bool = False) -> None:
    cfg: IncidentConfig = batch["config"]
    hours = batch["simulation_hours"]
    runs = batch["runs"]

    print()
    print(banner(f"Incident Simulation: {hours}h x {runs} runs"))
    print()
    _print_params(cfg)
    _print_combat_stats(batch)
    _print_casualties(batch)
    _print_resources(batch)
    if detailed:
        _print_hourly_curves(batch, hours)
    _print_balance(batch, hours)


def print_sweep_report(results: list[BatchResult], param_name: str) -> None:
    shared_print_sweep_report(
        results,
        param_name,
        header=(
            f"{'Value':>12} | {'Inc':>5} | {'Res':>5} | {'Fail':>5} | {'Death':>5} | "
            f"{'Surv%':>5} | {'Pop':>5} | {'Power':>5} | {'Food':>5} | {'Water':>5} | Verdict"
        ),
        render_row=_render_sweep_row,
    )


def _render_sweep_row(value: str, r: BatchResult) -> str:
    inc = r["total_incidents"]["mean"]
    res = r["incidents_resolved"]["mean"]
    fail = r["incidents_failed"]["mean"]
    deaths = r["total_deaths"]["mean"]
    surv = r["survival_rate"]["mean"] * 100
    pop = r["population"]["mean"]
    power = r["final_power"]["mean"]
    food = r["final_food"]["mean"]
    water = r["final_water"]["mean"]

    if surv < 50:
        verdict = "deadly"
    elif surv < 80:
        verdict = "challenging"
    else:
        verdict = "easy"

    line = f"{value:>12} | {inc:>5.1f} | {res:>5.1f} | {fail:>5.1f} | {deaths:>5.1f}"
    line += f" | {surv:>5.1f} | {pop:>5.0f} | {power:>5.0f} | {food:>5.0f} | {water:>5.0f} | {verdict}"
    return line


def _load_roster(vault_id: uuid.UUID) -> list[DefenderProfile]:
    """Load a vault's healthy adults as the simulator's base roster."""
    from app.db.session import async_session_maker
    from app.services.combat.incident_sim_roster import snapshot_vault_defenders

    async def _load() -> list[DefenderProfile]:
        async with async_session_maker() as session:
            return await snapshot_vault_defenders(session, vault_id)

    return asyncio.run(_load())


app = typer.Typer(help="Simulate incident balance for the Fallout Shelter game.")


@app.command()
def simulate(
    days: Annotated[int, typer.Option(help="Simulation length in days")] = DEFAULT_SIMULATION_DAYS,
    runs: Annotated[int, typer.Option(help="Monte Carlo runs (higher = smoother)")] = DEFAULT_RUNS,
    sweep: Annotated[str | None, typer.Option(help="Parameter to sweep")] = None,
    tick_interval: Annotated[int, typer.Option()] = DEFAULT_TICK_INTERVAL,
    incident_dt: Annotated[int, typer.Option()] = DEFAULT_INCIDENT_DT,
    spawn_chance: Annotated[float, typer.Option()] = DEFAULT_SPAWN_CHANCE_PER_HOUR,
    max_active: Annotated[int, typer.Option()] = DEFAULT_MAX_ACTIVE_INCIDENTS,
    spread_duration: Annotated[int, typer.Option()] = DEFAULT_SPREAD_DURATION,
    max_spread: Annotated[int, typer.Option()] = DEFAULT_MAX_SPREAD_COUNT,
    raider_power: Annotated[int, typer.Option()] = DEFAULT_BASE_RAIDER_POWER,
    starting_dwellers: Annotated[int, typer.Option()] = DEFAULT_STARTING_DWELLERS,
    avg_special: Annotated[float, typer.Option()] = DEFAULT_AVG_SPECIAL,
    avg_weapon_damage: Annotated[float, typer.Option()] = DEFAULT_AVG_WEAPON_DAMAGE,
    avg_level: Annotated[int, typer.Option()] = DEFAULT_AVG_LEVEL,
    defenders_per_incident: Annotated[int, typer.Option()] = DEFAULT_DEFENDERS_PER_INCIDENT,
    response_rate: Annotated[float, typer.Option()] = DEFAULT_RESPONSE_RATE,
    heal_per_tick: Annotated[int, typer.Option()] = DEFAULT_HEAL_PER_TICK,
    resource_drain: Annotated[float, typer.Option()] = DEFAULT_RESOURCE_DRAIN_PER_TICK,
    happiness_penalty: Annotated[float, typer.Option()] = DEFAULT_HAPPINESS_PENALTY_ACTIVE,
    vault_id: Annotated[
        uuid.UUID | None, typer.Option(help="Seed the roster from a real vault's healthy adults")
    ] = None,
    resample: Annotated[
        bool, typer.Option("--resample/--no-resample", help="Re-load the vault roster each run")
    ] = False,
    detailed: Annotated[bool, typer.Option(help="Show hourly cumulative curves")] = False,
    seed: Annotated[int | None, typer.Option(help="Fix random seed for reproducibility")] = None,
) -> None:
    hours = days * 24

    baseline = IncidentConfig(
        tick_interval=tick_interval,
        incident_dt=incident_dt,
        spawn_chance_per_hour=spawn_chance,
        max_active_incidents=max_active,
        spread_duration=spread_duration,
        max_spread_count=max_spread,
        base_raider_power=raider_power,
        starting_dwellers=starting_dwellers,
        starting_adults=max(1, int(starting_dwellers * 0.9)),
        avg_special=avg_special,
        avg_weapon_damage=avg_weapon_damage,
        avg_level=avg_level,
        defenders_per_incident=defenders_per_incident,
        response_rate=response_rate,
        heal_per_tick=heal_per_tick,
        resource_drain_per_tick=resource_drain,
        happiness_penalty_active=happiness_penalty,
    )

    base_roster: list[DefenderProfile] | None = None
    roster_loader: Callable[[], list[DefenderProfile]] | None = None
    if vault_id is not None:
        if resample:
            roster_loader = partial(_load_roster, vault_id)
        else:
            base_roster = _load_roster(vault_id)

    if sweep:
        if sweep not in SWEEP_RANGES:
            typer.echo(f"Unknown parameter '{sweep}'. Available: {list(SWEEP_RANGES.keys())}", err=True)
            raise typer.Exit(code=1)
        results = run_parameter_sweep(
            sweep, baseline, hours, runs, base_roster=base_roster, roster_loader=roster_loader, seed=seed
        )
        for r in results:
            print_report(r, detailed=detailed)
        print_sweep_report(results, sweep)
    else:
        result = run_monte_carlo(baseline, hours, runs, seed=seed, base_roster=base_roster, roster_loader=roster_loader)
        print_report(result, detailed=detailed)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
