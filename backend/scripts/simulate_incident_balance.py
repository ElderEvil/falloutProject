"""
Incident Balance Simulator — focused combat and incident system simulation.

Simulates incident spawning, combat resolution, spread mechanics, deaths,
and resource impact to help balance vault defenses and incident difficulty.
Run standalone without the full backend.

Usage:
    cd backend
    uv run python scripts/simulate_incident_balance.py
    uv run python scripts/simulate_incident_balance.py --days 3 --runs 50
    uv run python scripts/simulate_incident_balance.py --sweep spawn_chance_per_hour
"""

from __future__ import annotations

import dataclasses
import random
import statistics
from typing import Annotated, Any

import typer

DEFAULT_TICK_INTERVAL = 60
DEFAULT_SIMULATION_DAYS = 3
DEFAULT_RUNS = 50

DEFAULT_STARTING_DWELLERS = 20
DEFAULT_STARTING_ADULTS = 18
DEFAULT_AVG_STRENGTH = 4.0
DEFAULT_AVG_ENDURANCE = 4.0
DEFAULT_AVG_AGILITY = 4.0
DEFAULT_AVG_LEVEL = 5

DEFAULT_SPAWN_CHANCE_PER_HOUR = 0.05
DEFAULT_MIN_VAULT_POPULATION = 5
DEFAULT_MAX_ACTIVE_INCIDENTS = 5
DEFAULT_SPAWN_COOLDOWN_SECONDS = 120
DEFAULT_SPREAD_DURATION = 60
DEFAULT_MAX_SPREAD_COUNT = 3

DEFAULT_BASE_RAIDER_POWER = 10
DEFAULT_DWELLER_STRENGTH_WEIGHT = 0.4
DEFAULT_DWELLER_ENDURANCE_WEIGHT = 0.3
DEFAULT_DWELLER_AGILITY_WEIGHT = 0.3
DEFAULT_LEVEL_BONUS_MULTIPLIER = 2

DEFAULT_CAPS_REWARD_BASE = 50
DEFAULT_CAPS_REWARD_PER_DIFFICULTY = 20

DEFAULT_RESOURCE_DRAIN_PER_TICK = 0.5
DEFAULT_HAPPINESS_PENALTY_ACTIVE = 3.0
DEFAULT_HAPPINESS_PENALTY_SPREAD = 3.0


INCIDENT_TYPES = ["fire", "radroach", "mole_rat", "raider", "feral_ghoul", "deathclaw"]

INCIDENT_WEIGHTS: dict[str, int] = {
    "fire": 20,
    "radroach": 30,
    "mole_rat": 25,
    "raider": 10,
    "feral_ghoul": 5,
    "deathclaw": 2,
}

INCIDENT_DIFFICULTY: dict[str, tuple[int, int]] = {
    "fire": (2, 4),
    "radroach": (1, 3),
    "mole_rat": (2, 5),
    "raider": (4, 7),
    "feral_ghoul": (5, 8),
    "deathclaw": (8, 10),
}

EXTERNAL_INCIDENTS = {"raider", "feral_ghoul", "deathclaw"}


@dataclasses.dataclass(frozen=True)
class IncidentConfig:
    tick_interval: int = DEFAULT_TICK_INTERVAL
    spawn_chance_per_hour: float = DEFAULT_SPAWN_CHANCE_PER_HOUR
    min_vault_population: int = DEFAULT_MIN_VAULT_POPULATION
    max_active_incidents: int = DEFAULT_MAX_ACTIVE_INCIDENTS
    spawn_cooldown_seconds: int = DEFAULT_SPAWN_COOLDOWN_SECONDS
    spread_duration: int = DEFAULT_SPREAD_DURATION
    max_spread_count: int = DEFAULT_MAX_SPREAD_COUNT

    base_raider_power: int = DEFAULT_BASE_RAIDER_POWER
    dweller_strength_weight: float = DEFAULT_DWELLER_STRENGTH_WEIGHT
    dweller_endurance_weight: float = DEFAULT_DWELLER_ENDURANCE_WEIGHT
    dweller_agility_weight: float = DEFAULT_DWELLER_AGILITY_WEIGHT
    level_bonus_multiplier: int = DEFAULT_LEVEL_BONUS_MULTIPLIER

    caps_reward_base: int = DEFAULT_CAPS_REWARD_BASE
    caps_reward_per_difficulty: int = DEFAULT_CAPS_REWARD_PER_DIFFICULTY

    resource_drain_per_tick: float = DEFAULT_RESOURCE_DRAIN_PER_TICK
    happiness_penalty_active: float = DEFAULT_HAPPINESS_PENALTY_ACTIVE
    happiness_penalty_spread: float = DEFAULT_HAPPINESS_PENALTY_SPREAD

    starting_dwellers: int = DEFAULT_STARTING_DWELLERS
    starting_adults: int = DEFAULT_STARTING_ADULTS
    avg_strength: float = DEFAULT_AVG_STRENGTH
    avg_endurance: float = DEFAULT_AVG_ENDURANCE
    avg_agility: float = DEFAULT_AVG_AGILITY
    avg_level: int = DEFAULT_AVG_LEVEL

    power_max: float = 100.0
    food_max: float = 100.0
    water_max: float = 100.0

    def roll_difficulty(self, incident_type: str) -> int:
        low, high = INCIDENT_DIFFICULTY[incident_type]
        return random.randint(low, high)

    def get_spawn_weights(self) -> dict[str, int]:
        return INCIDENT_WEIGHTS.copy()


@dataclasses.dataclass
class Incident:
    start_time: int
    incident_type: str
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
    power: float = 100.0
    food: float = 100.0
    water: float = 100.0
    happiness: float = 75.0
    caps: int = 500
    incidents: list[Incident] = dataclasses.field(default_factory=list)
    total_deaths: int = 0
    deaths_by_type: dict[str, int] = dataclasses.field(default_factory=lambda: dict.fromkeys(INCIDENT_TYPES, 0))
    incidents_by_type: dict[str, int] = dataclasses.field(default_factory=lambda: dict.fromkeys(INCIDENT_TYPES, 0))
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

    deaths_by_type: dict[str, int]
    incidents_by_type: dict[str, int]

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

    def run(self, simulation_hours: int, seed: int | None = None) -> SimulationResult:
        if seed is not None:
            random.seed(seed)

        duration_seconds = simulation_hours * 3600
        ticks = duration_seconds // self.cfg.tick_interval + 1

        vault = VaultState()
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

            active_before = len([i for i in vault.incidents if not i.resolved])
            self._resolve_incidents(vault, now, resolution_times)
            self._spawn_incidents(vault, now, last_spawn_time)
            active_after = len([i for i in vault.incidents if not i.resolved])
            max_concurrent = max(max_concurrent, active_after)

            if active_after > 0:
                self._apply_incident_pressure(vault)

            new_incidents = max(0, active_after - active_before)
            if new_incidents > 0:
                last_spawn_time = now
                incidents_curve[hour_idx] += new_incidents

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

    def _resolve_incidents(self, vault: VaultState, now: int, resolution_times: list[int]) -> None:
        for incident in vault.incidents:
            if incident.resolved:
                continue

            elapsed = incident.elapsed(now)
            if elapsed >= self.cfg.spread_duration:
                if incident.spread_count < self.cfg.max_spread_count:
                    incident.spread_count += 1
                    vault.happiness -= self.cfg.happiness_penalty_spread
                else:
                    incident.resolved = True
                    vault.incidents_failed += 1
                    resolution_times.append(elapsed // self.cfg.tick_interval)
                    continue

            dweller_power = self._calculate_dweller_power(vault)
            raider_power = incident.difficulty * self.cfg.base_raider_power

            if dweller_power > raider_power:
                incident.resolved = True
                vault.incidents_resolved += 1
                reward = self.cfg.caps_reward_base + incident.difficulty * self.cfg.caps_reward_per_difficulty
                incident.caps_rewarded = reward
                vault.caps += reward
                vault.total_caps_from_incidents += reward
                resolution_times.append(elapsed // self.cfg.tick_interval)
                continue

            damage = max(1, int((raider_power - dweller_power) * 0.1))
            death_chance = min(0.3, damage / (vault.population * 10))
            if random.random() < death_chance and vault.adults > 0:
                vault.adults -= 1
                vault.population -= 1
                vault.total_deaths += 1
                incident.deaths += 1
                vault.deaths_by_type[incident.incident_type] += 1

    def _spawn_incidents(self, vault: VaultState, now: int, last_spawn_time: int) -> None:
        if vault.population < self.cfg.min_vault_population:
            return

        active = len([i for i in vault.incidents if not i.resolved])
        if active >= self.cfg.max_active_incidents:
            return

        seconds_since_last = now - last_spawn_time
        if seconds_since_last < self.cfg.spawn_cooldown_seconds:
            return

        hours_passed = min(self.cfg.tick_interval / 3600, 2.0)
        spawn_chance = self.cfg.spawn_chance_per_hour * hours_passed
        if random.random() >= spawn_chance:
            return

        weights = self.cfg.get_spawn_weights()
        incident_type = random.choices(list(weights.keys()), weights=list(weights.values()), k=1)[0]
        difficulty = self.cfg.roll_difficulty(incident_type)

        incident = Incident(
            start_time=now,
            incident_type=incident_type,
            difficulty=difficulty,
        )
        vault.incidents.append(incident)
        vault.incidents_by_type[incident_type] += 1
        vault.happiness -= self.cfg.happiness_penalty_active

    def _calculate_dweller_power(self, vault: VaultState) -> float:
        if vault.adults <= 0:
            return 0.0
        base = (
            self.cfg.avg_strength * self.cfg.dweller_strength_weight
            + self.cfg.avg_endurance * self.cfg.dweller_endurance_weight
            + self.cfg.avg_agility * self.cfg.dweller_agility_weight
        )
        level_bonus = self.cfg.avg_level * self.cfg.level_bonus_multiplier
        return vault.adults * (base + level_bonus)

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
class _Curves:
    pop: list[float] = dataclasses.field(default_factory=list)
    deaths: list[float] = dataclasses.field(default_factory=list)
    incidents: list[float] = dataclasses.field(default_factory=list)
    power: list[float] = dataclasses.field(default_factory=list)
    food: list[float] = dataclasses.field(default_factory=list)
    water: list[float] = dataclasses.field(default_factory=list)
    happiness: list[float] = dataclasses.field(default_factory=list)

    @classmethod
    def zeroed(cls, hours: int) -> "_Curves":
        return cls(**{k: [0.0] * hours for k in dataclasses.asdict(cls())})

    def add_result(self, result: SimulationResult, hours: int) -> None:
        for h in range(hours):
            self.pop[h] += result.population_by_hour[h]
            self.deaths[h] += result.deaths_by_hour[h]
            self.incidents[h] += result.incidents_by_hour[h]
            self.power[h] += result.power_by_hour[h]
            self.food[h] += result.food_by_hour[h]
            self.water[h] += result.water_by_hour[h]
            self.happiness[h] += result.happiness_by_hour[h]

    def divide(self, divisor: int) -> None:
        for k in dataclasses.asdict(self):
            arr = getattr(self, k)
            for i in range(len(arr)):
                arr[i] /= divisor


def _stats(values: list[int] | list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def run_monte_carlo(config: IncidentConfig, simulation_hours: int, runs: int) -> BatchResult:
    sim = IncidentSimulator(config)
    ag = _Aggregates()
    curves = _Curves.zeroed(simulation_hours)
    deaths_by_type: dict[str, list[int]] = {t: [] for t in INCIDENT_TYPES}
    incidents_by_type: dict[str, list[int]] = {t: [] for t in INCIDENT_TYPES}

    for i in range(runs):
        result = sim.run(simulation_hours, seed=i)
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
    "avg_strength": [2.0, 3.0, 4.0, 5.0, 6.0],
    "resource_drain_per_tick": [0.0, 0.5, 1.0, 2.0, 3.0],
    "happiness_penalty_active": [1.0, 3.0, 5.0, 8.0, 10.0],
}


def run_parameter_sweep(
    param_name: str, baseline: IncidentConfig, simulation_hours: int, runs: int
) -> list[BatchResult]:
    results: list[BatchResult] = []
    values = SWEEP_RANGES.get(param_name, [])
    if not values:
        print(f"Unknown parameter '{param_name}'. Available: {list(SWEEP_RANGES.keys())}")
        return results

    for value in values:
        cfg = dataclasses.replace(baseline, **{param_name: value})
        result = run_monte_carlo(cfg, simulation_hours, runs)
        results.append(result)
    return results


TERMINAL_WIDTH = 72


def banner(text: str) -> str:
    pad = (TERMINAL_WIDTH - len(text) - 4) // 2
    return "=" * pad + f"  {text}  " + "=" * pad


def fmt_stats(st: dict[str, float]) -> str:
    return f"mean={st['mean']:.1f}  median={st['median']:.1f}  std={st['stdev']:.1f}  range=[{st['min']}, {st['max']}]"


def _print_params(cfg: IncidentConfig) -> None:
    print("Parameters:")
    print(f"  tick_interval       = {cfg.tick_interval}s")
    print(f"  spawn_chance        = {cfg.spawn_chance_per_hour:.2%}/hour")
    print(f"  max_active          = {cfg.max_active_incidents}")
    print(f"  spread_duration     = {cfg.spread_duration}s")
    print(f"  max_spread          = {cfg.max_spread_count}")
    print(f"  raider_power        = {cfg.base_raider_power}")
    print(f"  starting_dwellers   = {cfg.starting_dwellers}")
    print(f"  avg_strength        = {cfg.avg_strength:.1f}")
    print(f"  avg_endurance       = {cfg.avg_endurance:.1f}")
    print(f"  avg_agility         = {cfg.avg_agility:.1f}")
    print(f"  avg_level           = {cfg.avg_level}")
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
            print(f"  {t:15} : {d['mean']:.1f} deaths from {i['mean']:.1f} incidents (death_rate={death_rate:.2f})")
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
    if hours > 24:
        return
    print("Hourly curves (average per run):")
    print("  hour | POP | DEATHS | INCIDENTS | POWER | FOOD | WATER | HAPPY")
    print("  " + "-" * 65)
    for h in range(hours):
        p = batch["pop_curve"][h]
        d = batch["deaths_curve"][h]
        i = batch["incidents_curve"][h]
        pw = batch["power_curve"][h]
        f = batch["food_curve"][h]
        w = batch["water_curve"][h]
        hp = batch["happiness_curve"][h]
        print(f"  {h:4} | {p:3.0f} | {d:6.1f} | {i:9.1f} | {pw:5.0f} | {f:4.0f} | {w:5.0f} | {hp:5.1f}")
    print()


def _print_balance(batch: BatchResult, hours: int) -> None:
    mean_deaths = batch["total_deaths"]["mean"]
    mean_survival = batch["survival_rate"]["mean"]
    mean_incidents = batch["total_incidents"]["mean"]
    mean_pop = batch["population"]["mean"]

    print("Balance assessment:")
    if mean_survival < 0.5:
        print("  Survival rate below 50% — incidents too deadly for current defenses.")
    elif mean_survival < 0.8:
        print("  Survival rate 50-80% — challenging but manageable.")
    else:
        print("  Survival rate above 80% — incidents are too easy.")
    print(f"  Deaths per incident={mean_deaths / mean_incidents:.2f} over {hours}h")
    print(f"  Population survived={mean_pop:.0f} from {DEFAULT_STARTING_DWELLERS}")
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
    print()
    print(banner(f"Parameter sweep: {param_name}"))
    print()
    print(
        f"{'Value':>12} | {'Inc':>5} | {'Res':>5} | {'Fail':>5} | {'Death':>5} | "
        f"{'Surv%':>5} | {'Pop':>5} | {'Power':>5} | {'Food':>5} | {'Water':>5} | Verdict"
    )
    print("-" * TERMINAL_WIDTH)

    for r in results:
        cfg: IncidentConfig = r["config"]
        value = getattr(cfg, param_name)
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

        vstr = f"{value:.2f}" if isinstance(value, float) else str(value)
        line = f"{vstr:>12} | {inc:>5.1f} | {res:>5.1f} | {fail:>5.1f} | {deaths:>5.1f}"
        line += f" | {surv:>5.1f} | {pop:>5.0f} | {power:>5.0f} | {food:>5.0f} | {water:>5.0f} | {verdict}"
        print(line)
    print()


app = typer.Typer(help="Simulate incident balance for the Fallout Shelter game.")


@app.command()
def simulate(
    days: Annotated[int, typer.Option(help="Simulation length in days")] = DEFAULT_SIMULATION_DAYS,
    runs: Annotated[int, typer.Option(help="Monte Carlo runs (higher = smoother)")] = DEFAULT_RUNS,
    sweep: Annotated[str | None, typer.Option(help="Parameter to sweep")] = None,
    tick_interval: Annotated[int, typer.Option()] = DEFAULT_TICK_INTERVAL,
    spawn_chance: Annotated[float, typer.Option()] = DEFAULT_SPAWN_CHANCE_PER_HOUR,
    max_active: Annotated[int, typer.Option()] = DEFAULT_MAX_ACTIVE_INCIDENTS,
    spread_duration: Annotated[int, typer.Option()] = DEFAULT_SPREAD_DURATION,
    max_spread: Annotated[int, typer.Option()] = DEFAULT_MAX_SPREAD_COUNT,
    raider_power: Annotated[int, typer.Option()] = DEFAULT_BASE_RAIDER_POWER,
    starting_dwellers: Annotated[int, typer.Option()] = DEFAULT_STARTING_DWELLERS,
    avg_strength: Annotated[float, typer.Option()] = DEFAULT_AVG_STRENGTH,
    avg_endurance: Annotated[float, typer.Option()] = DEFAULT_AVG_ENDURANCE,
    avg_agility: Annotated[float, typer.Option()] = DEFAULT_AVG_AGILITY,
    avg_level: Annotated[int, typer.Option()] = DEFAULT_AVG_LEVEL,
    resource_drain: Annotated[float, typer.Option()] = DEFAULT_RESOURCE_DRAIN_PER_TICK,
    happiness_penalty: Annotated[float, typer.Option()] = DEFAULT_HAPPINESS_PENALTY_ACTIVE,
    detailed: Annotated[bool, typer.Option(help="Show hourly cumulative curves")] = False,
    seed: Annotated[int | None, typer.Option(help="Fix random seed for reproducibility")] = None,
) -> None:
    hours = days * 24

    baseline = IncidentConfig(
        tick_interval=tick_interval,
        spawn_chance_per_hour=spawn_chance,
        max_active_incidents=max_active,
        spread_duration=spread_duration,
        max_spread_count=max_spread,
        base_raider_power=raider_power,
        starting_dwellers=starting_dwellers,
        starting_adults=max(1, int(starting_dwellers * 0.9)),
        avg_strength=avg_strength,
        avg_endurance=avg_endurance,
        avg_agility=avg_agility,
        avg_level=avg_level,
        resource_drain_per_tick=resource_drain,
        happiness_penalty_active=happiness_penalty,
    )

    if sweep:
        if sweep not in SWEEP_RANGES:
            typer.echo(f"Unknown parameter '{sweep}'. Available: {list(SWEEP_RANGES.keys())}", err=True)
            raise typer.Exit(code=1)
        results = run_parameter_sweep(sweep, baseline, hours, runs)
        for r in results:
            print_report(r, detailed=detailed)
        print_sweep_report(results, sweep)
    else:
        if seed is not None:
            random.seed(seed)
        result = run_monte_carlo(baseline, hours, runs)
        print_report(result, detailed=detailed)


def main() -> None:
    app()


if __name__ == "__main__":
    main()
