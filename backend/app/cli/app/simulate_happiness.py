"""Happiness Balance Simulator — focused happiness and productivity simulation.

Models how happiness changes under various vault conditions and how
happiness loss translates to reduced production efficiency.
Run standalone without the full backend.

Usage:
    cd backend
    uv run fo-cli simulate-happiness
    uv run fo-cli simulate-happiness --days 3 --runs 50
    uv run fo-cli simulate-happiness --sweep base_decay
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
DEFAULT_WORKING_RATIO = 0.7
DEFAULT_TRAINING_RATIO = 0.1
DEFAULT_HEALTHY_RATIO = 0.8
DEFAULT_PARTNER_RATIO = 0.3

DEFAULT_BASE_DECAY = 0.5
DEFAULT_RESOURCE_SHORTAGE_DECAY = 2.0
DEFAULT_CRITICAL_RESOURCE_DECAY = 5.0
DEFAULT_INCIDENT_PENALTY = 3.0
DEFAULT_IDLE_DECAY = 1.0

DEFAULT_WORKING_GAIN = 1.0
DEFAULT_HIGH_HEALTH_BONUS = 0.5
DEFAULT_PARTNER_NEARBY_BONUS = 1.0

DEFAULT_LIVING_QUARTERS_BONUS = 1.5
DEFAULT_TRAINING_ROOM_BONUS = 0.5
DEFAULT_RADIO_ROOM_BONUS = 1.0

DEFAULT_COMBAT_PENALTY = 2.0
DEFAULT_TRAINING_GAIN = 0.5
DEFAULT_HIGH_VAULT_RESOURCES_BONUS = 0.5
DEFAULT_NO_INCIDENTS_BONUS = 0.3

DEFAULT_RESOURCE_LOW_THRESHOLD = 0.20
DEFAULT_RESOURCE_CRITICAL_THRESHOLD = 0.05

DEFAULT_INCIDENT_CHANCE_PER_TICK = 0.02
DEFAULT_MAX_CONCURRENT_INCIDENTS = 3

DEFAULT_RESOURCE_DRIFT = 0.02


@dataclasses.dataclass(frozen=True)
class HappinessConfig:
    tick_interval: int = DEFAULT_TICK_INTERVAL
    starting_dwellers: int = DEFAULT_STARTING_DWELLERS
    working_ratio: float = DEFAULT_WORKING_RATIO
    training_ratio: float = DEFAULT_TRAINING_RATIO
    healthy_ratio: float = DEFAULT_HEALTHY_RATIO
    partner_ratio: float = DEFAULT_PARTNER_RATIO

    base_decay: float = DEFAULT_BASE_DECAY
    resource_shortage_decay: float = DEFAULT_RESOURCE_SHORTAGE_DECAY
    critical_resource_decay: float = DEFAULT_CRITICAL_RESOURCE_DECAY
    incident_penalty: float = DEFAULT_INCIDENT_PENALTY
    idle_decay: float = DEFAULT_IDLE_DECAY

    working_gain: float = DEFAULT_WORKING_GAIN
    high_health_bonus: float = DEFAULT_HIGH_HEALTH_BONUS
    partner_nearby_bonus: float = DEFAULT_PARTNER_NEARBY_BONUS

    living_quarters_bonus: float = DEFAULT_LIVING_QUARTERS_BONUS
    training_room_bonus: float = DEFAULT_TRAINING_ROOM_BONUS
    radio_room_bonus: float = DEFAULT_RADIO_ROOM_BONUS

    combat_penalty: float = DEFAULT_COMBAT_PENALTY
    training_gain: float = DEFAULT_TRAINING_GAIN
    high_vault_resources_bonus: float = DEFAULT_HIGH_VAULT_RESOURCES_BONUS
    no_incidents_bonus: float = DEFAULT_NO_INCIDENTS_BONUS

    resource_low_threshold: float = DEFAULT_RESOURCE_LOW_THRESHOLD
    resource_critical_threshold: float = DEFAULT_RESOURCE_CRITICAL_THRESHOLD

    incident_chance_per_tick: float = DEFAULT_INCIDENT_CHANCE_PER_TICK
    max_concurrent_incidents: int = DEFAULT_MAX_CONCURRENT_INCIDENTS
    resource_drift: float = DEFAULT_RESOURCE_DRIFT

    living_rooms: int = 1
    training_rooms: int = 1
    radio_rooms: int = 1

    @property
    def adults(self) -> int:
        return max(1, int(self.starting_dwellers * 0.9))

    @property
    def working_dwellers(self) -> int:
        return int(self.adults * self.working_ratio)

    @property
    def training_dwellers(self) -> int:
        return int(self.adults * self.training_ratio)

    @property
    def idle_dwellers(self) -> int:
        return max(0, self.adults - self.working_dwellers - self.training_dwellers)

    @property
    def healthy_dwellers(self) -> int:
        return int(self.starting_dwellers * self.healthy_ratio)

    @property
    def partnered_dwellers(self) -> int:
        return int(self.starting_dwellers * self.partner_ratio)


@dataclasses.dataclass
class VaultState:
    happiness: float = 75.0
    power_pct: float = 0.8
    food_pct: float = 0.8
    water_pct: float = 0.8
    active_incidents: int = 0
    total_ticks: int = 0
    ticks_below_20: int = 0
    ticks_below_50: int = 0
    ticks_below_75: int = 0
    total_happiness_delta: float = 0.0

    delta_breakdown: dict[str, float] = dataclasses.field(
        default_factory=lambda: dict.fromkeys(
            [
                "base_decay",
                "resource",
                "incidents",
                "idle",
                "working",
                "health",
                "partner",
                "rooms",
                "combat",
                "training",
                "vault_wide",
            ],
            0.0,
        )
    )


@dataclasses.dataclass
class SimulationResult:
    config: HappinessConfig
    total_ticks: int

    happiness_by_hour: list[float]
    productivity_by_hour: list[float]
    power_pct_by_hour: list[float]
    food_pct_by_hour: list[float]
    water_pct_by_hour: list[float]
    incidents_by_hour: list[int]

    final_happiness: float
    mean_happiness: float
    min_happiness: float
    max_happiness: float
    mean_productivity: float

    time_below_20_pct: float
    time_below_50_pct: float
    time_below_75_pct: float
    time_above_90_pct: float

    total_happiness_delta: float
    delta_breakdown: dict[str, float]


class HappinessSimulator:
    def __init__(self, config: HappinessConfig) -> None:
        self.cfg = config

    def run(self, simulation_hours: int, seed: int | None = None) -> SimulationResult:
        if seed is not None:
            random.seed(seed)

        duration_seconds = simulation_hours * 3600
        ticks = duration_seconds // self.cfg.tick_interval + 1

        vault = VaultState()
        happiness_snapshots: list[float] = []
        productivity_snapshots: list[float] = []
        power_snapshots: list[float] = []
        food_snapshots: list[float] = []
        water_snapshots: list[float] = []
        incident_snapshots: list[int] = []

        for _ in range(ticks):
            self._drift_resources(vault)
            self._spawn_or_resolve_incidents(vault)
            delta = self._calculate_happiness_delta(vault)
            vault.happiness = max(0, min(100, vault.happiness + delta))
            vault.total_ticks += 1
            vault.total_happiness_delta += abs(delta)

            self._track_happiness_band(vault)

            hour_idx = min(vault.total_ticks // 60, simulation_hours - 1)
            if hour_idx < simulation_hours:
                happiness_snapshots.append(vault.happiness)
                productivity_snapshots.append(self._productivity_multiplier(vault.happiness))
                power_snapshots.append(vault.power_pct * 100)
                food_snapshots.append(vault.food_pct * 100)
                water_snapshots.append(vault.water_pct * 100)
                incident_snapshots.append(vault.active_incidents)

        mean_happy = statistics.mean(happiness_snapshots) if happiness_snapshots else 0.0
        mean_prod = statistics.mean(productivity_snapshots) if productivity_snapshots else 0.0

        return SimulationResult(
            config=self.cfg,
            total_ticks=ticks,
            happiness_by_hour=self._hourly_avg(happiness_snapshots, simulation_hours),
            productivity_by_hour=self._hourly_avg(productivity_snapshots, simulation_hours),
            power_pct_by_hour=self._hourly_avg(power_snapshots, simulation_hours),
            food_pct_by_hour=self._hourly_avg(food_snapshots, simulation_hours),
            water_pct_by_hour=self._hourly_avg(water_snapshots, simulation_hours),
            incidents_by_hour=self._hourly_sum(incident_snapshots, simulation_hours),
            final_happiness=vault.happiness,
            mean_happiness=mean_happy,
            min_happiness=min(happiness_snapshots) if happiness_snapshots else 0.0,
            max_happiness=max(happiness_snapshots) if happiness_snapshots else 0.0,
            mean_productivity=mean_prod,
            time_below_20_pct=vault.ticks_below_20 / vault.total_ticks,
            time_below_50_pct=vault.ticks_below_50 / vault.total_ticks,
            time_below_75_pct=vault.ticks_below_75 / vault.total_ticks,
            time_above_90_pct=(
                sum(1 for h in happiness_snapshots if h >= 90) / vault.total_ticks if vault.total_ticks > 0 else 0.0
            ),
            total_happiness_delta=vault.total_happiness_delta,
            delta_breakdown=vault.delta_breakdown,
        )

    def _hourly_avg(self, values: list[float], hours: int) -> list[float]:
        result = [0.0] * hours
        counts = [0] * hours
        for i, v in enumerate(values):
            h = min(i // 60, hours - 1)
            result[h] += v
            counts[h] += 1
        for i in range(hours):
            if counts[i] > 0:
                result[i] /= counts[i]
        return result

    def _hourly_sum(self, values: list[int], hours: int) -> list[int]:
        result = [0] * hours
        for i, v in enumerate(values):
            h = min(i // 60, hours - 1)
            result[h] += v
        return result

    def _drift_resources(self, vault: VaultState) -> None:
        drift = self.cfg.resource_drift
        for attr in ("power_pct", "food_pct", "water_pct"):
            current = getattr(vault, attr)
            change = random.uniform(-drift, drift)
            setattr(vault, attr, max(0.0, min(1.0, current + change)))

    def _spawn_or_resolve_incidents(self, vault: VaultState) -> None:
        if vault.active_incidents > 0 and random.random() < 0.1:
            vault.active_incidents -= 1
        can_spawn = vault.active_incidents < self.cfg.max_concurrent_incidents
        if can_spawn and random.random() < self.cfg.incident_chance_per_tick:
            vault.active_incidents += 1

    def _calculate_happiness_delta(self, vault: VaultState) -> float:
        delta = 0.0
        breakdown = vault.delta_breakdown

        delta -= self.cfg.base_decay
        breakdown["base_decay"] -= self.cfg.base_decay

        resource_penalty = self._resource_penalty(vault)
        delta -= resource_penalty
        breakdown["resource"] -= resource_penalty

        if vault.active_incidents > 0:
            incident_delta = vault.active_incidents * self.cfg.incident_penalty
            delta -= incident_delta
            breakdown["incidents"] -= incident_delta

        idle = self.cfg.idle_dwellers
        if idle > 0:
            idle_delta = idle * self.cfg.idle_decay
            delta -= idle_delta
            breakdown["idle"] -= idle_delta

        working = self.cfg.working_dwellers
        if working > 0:
            work_delta = working * self.cfg.working_gain
            delta += work_delta
            breakdown["working"] += work_delta

        healthy = self.cfg.healthy_dwellers
        if healthy > 0:
            health_delta = healthy * self.cfg.high_health_bonus
            delta += health_delta
            breakdown["health"] += health_delta

        partnered = self.cfg.partnered_dwellers
        if partnered > 0:
            partner_delta = partnered * self.cfg.partner_nearby_bonus
            delta += partner_delta
            breakdown["partner"] += partner_delta

        room_delta = (
            self.cfg.living_rooms * self.cfg.living_quarters_bonus
            + self.cfg.training_rooms * self.cfg.training_room_bonus
            + self.cfg.radio_rooms * self.cfg.radio_room_bonus
        )
        delta += room_delta
        breakdown["rooms"] += room_delta

        if vault.active_incidents > 0:
            combat_delta = vault.active_incidents * self.cfg.combat_penalty
            delta -= combat_delta
            breakdown["combat"] -= combat_delta

        training = self.cfg.training_dwellers
        if training > 0:
            train_delta = training * self.cfg.training_gain
            delta += train_delta
            breakdown["training"] += train_delta

        all_high = all(getattr(vault, attr) > 0.8 for attr in ("power_pct", "food_pct", "water_pct"))
        if all_high:
            delta += self.cfg.high_vault_resources_bonus
            breakdown["vault_wide"] += self.cfg.high_vault_resources_bonus
        if vault.active_incidents == 0:
            delta += self.cfg.no_incidents_bonus
            breakdown["vault_wide"] += self.cfg.no_incidents_bonus

        return delta

    def _resource_penalty(self, vault: VaultState) -> float:
        penalty = 0.0
        for pct in (vault.power_pct, vault.food_pct, vault.water_pct):
            if pct < self.cfg.resource_critical_threshold:
                penalty += self.cfg.critical_resource_decay
            elif pct < self.cfg.resource_low_threshold:
                penalty += self.cfg.resource_shortage_decay
        return penalty

    def _track_happiness_band(self, vault: VaultState) -> None:
        h = vault.happiness
        if h < 20:
            vault.ticks_below_20 += 1
        if h < 50:
            vault.ticks_below_50 += 1
        if h < 75:
            vault.ticks_below_75 += 1

    @staticmethod
    def _productivity_multiplier(happiness: float) -> float:
        return 0.5 + happiness / 200.0


BatchResult = dict[str, Any]


@dataclasses.dataclass
class _Aggregates:
    final_happiness: list[float] = dataclasses.field(default_factory=list)
    mean_happiness: list[float] = dataclasses.field(default_factory=list)
    min_happiness: list[float] = dataclasses.field(default_factory=list)
    max_happiness: list[float] = dataclasses.field(default_factory=list)
    mean_productivity: list[float] = dataclasses.field(default_factory=list)
    below_20: list[float] = dataclasses.field(default_factory=list)
    below_50: list[float] = dataclasses.field(default_factory=list)
    below_75: list[float] = dataclasses.field(default_factory=list)
    above_90: list[float] = dataclasses.field(default_factory=list)
    total_delta: list[float] = dataclasses.field(default_factory=list)

    def collect(self, result: SimulationResult) -> None:
        self.final_happiness.append(result.final_happiness)
        self.mean_happiness.append(result.mean_happiness)
        self.min_happiness.append(result.min_happiness)
        self.max_happiness.append(result.max_happiness)
        self.mean_productivity.append(result.mean_productivity)
        self.below_20.append(result.time_below_20_pct)
        self.below_50.append(result.time_below_50_pct)
        self.below_75.append(result.time_below_75_pct)
        self.above_90.append(result.time_above_90_pct)
        self.total_delta.append(result.total_happiness_delta)


@dataclasses.dataclass
class _Curves:
    happiness: list[float] = dataclasses.field(default_factory=list)
    productivity: list[float] = dataclasses.field(default_factory=list)
    power: list[float] = dataclasses.field(default_factory=list)
    food: list[float] = dataclasses.field(default_factory=list)
    water: list[float] = dataclasses.field(default_factory=list)
    incidents: list[float] = dataclasses.field(default_factory=list)

    @classmethod
    def zeroed(cls, hours: int) -> _Curves:
        return cls(**{k: [0.0] * hours for k in dataclasses.asdict(cls())})

    def add_result(self, result: SimulationResult, hours: int) -> None:
        for h in range(hours):
            self.happiness[h] += result.happiness_by_hour[h]
            self.productivity[h] += result.productivity_by_hour[h]
            self.power[h] += result.power_pct_by_hour[h]
            self.food[h] += result.food_pct_by_hour[h]
            self.water[h] += result.water_pct_by_hour[h]
            self.incidents[h] += result.incidents_by_hour[h]

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


def run_monte_carlo(config: HappinessConfig, simulation_hours: int, runs: int) -> BatchResult:
    sim = HappinessSimulator(config)
    ag = _Aggregates()
    curves = _Curves.zeroed(simulation_hours)
    delta_keys = [
        "base_decay",
        "resource",
        "incidents",
        "idle",
        "working",
        "health",
        "partner",
        "rooms",
        "combat",
        "training",
        "vault_wide",
    ]
    delta_totals: dict[str, list[float]] = {k: [] for k in delta_keys}

    for i in range(runs):
        result = sim.run(simulation_hours, seed=i)
        ag.collect(result)
        curves.add_result(result, simulation_hours)
        for k in delta_keys:
            delta_totals[k].append(result.delta_breakdown[k])

    curves.divide(runs)

    return {
        "config": config,
        "runs": runs,
        "simulation_hours": simulation_hours,
        "final_happiness": _stats(ag.final_happiness),
        "mean_happiness": _stats(ag.mean_happiness),
        "min_happiness": _stats(ag.min_happiness),
        "max_happiness": _stats(ag.max_happiness),
        "mean_productivity": _stats(ag.mean_productivity),
        "time_below_20": _stats(ag.below_20),
        "time_below_50": _stats(ag.below_50),
        "time_below_75": _stats(ag.below_75),
        "time_above_90": _stats(ag.above_90),
        "total_happiness_delta": _stats(ag.total_delta),
        "delta_breakdown": {k: _stats(delta_totals[k]) for k in delta_keys},
        "happiness_curve": curves.happiness,
        "productivity_curve": curves.productivity,
        "power_curve": curves.power,
        "food_curve": curves.food,
        "water_curve": curves.water,
        "incidents_curve": curves.incidents,
    }


SWEEP_RANGES: dict[str, list[Any]] = {
    "base_decay": [0.1, 0.3, 0.5, 0.8, 1.0, 1.5],
    "resource_shortage_decay": [0.5, 1.0, 2.0, 3.0, 5.0],
    "incident_penalty": [1.0, 2.0, 3.0, 5.0, 8.0],
    "idle_decay": [0.0, 0.5, 1.0, 1.5, 2.0],
    "working_gain": [0.5, 1.0, 1.5, 2.0],
    "working_ratio": [0.3, 0.5, 0.7, 0.9],
    "high_health_bonus": [0.0, 0.3, 0.5, 1.0],
    "partner_nearby_bonus": [0.0, 0.5, 1.0, 1.5],
    "living_quarters_bonus": [0.5, 1.0, 1.5, 2.0],
    "incident_chance_per_tick": [0.0, 0.01, 0.02, 0.05, 0.10],
    "resource_drift": [0.0, 0.02, 0.05, 0.10],
}


def run_parameter_sweep(
    param_name: str, baseline: HappinessConfig, simulation_hours: int, runs: int
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


def _print_params(cfg: HappinessConfig) -> None:
    print("Parameters:")
    print(f"  tick_interval       = {cfg.tick_interval}s")
    print(f"  dwellers            = {cfg.starting_dwellers} ({cfg.adults} adults)")
    print(f"  working_ratio       = {cfg.working_ratio:.0%} ({cfg.working_dwellers} working)")
    print(f"  training_ratio      = {cfg.training_ratio:.0%} ({cfg.training_dwellers} training)")
    print(f"  healthy_ratio       = {cfg.healthy_ratio:.0%}")
    print(f"  partner_ratio       = {cfg.partner_ratio:.0%}")
    print(f"  base_decay          = {cfg.base_decay:.1f}/tick")
    print(f"  resource_decay      = {cfg.resource_shortage_decay:.1f} (shortage)")
    print(f"  critical_decay      = {cfg.critical_resource_decay:.1f} (critical)")
    print(f"  incident_penalty    = {cfg.incident_penalty:.1f}/incident")
    print(f"  idle_decay          = {cfg.idle_decay:.1f}/idle")
    print(f"  working_gain        = {cfg.working_gain:.1f}/worker")
    print(f"  room bonuses        = LQ={cfg.living_quarters_bonus:.1f}")
    print(f"                      = TR={cfg.training_room_bonus:.1f} RD={cfg.radio_room_bonus:.1f}")
    print(f"  incident_chance     = {cfg.incident_chance_per_tick:.2%}/tick")
    print(f"  resource_drift      = ±{cfg.resource_drift:.2%}/tick")
    print()


def _print_happiness_distribution(batch: BatchResult) -> None:
    print("Happiness distribution:")
    print(f"  mean                : {fmt_stats(batch['mean_happiness'])}")
    print(f"  range               : {fmt_stats(batch['min_happiness'])} → {fmt_stats(batch['max_happiness'])}")
    print(f"  final               : {fmt_stats(batch['final_happiness'])}")
    print()


def _print_time_bands(batch: BatchResult) -> None:
    print("Time in happiness bands:")
    b20 = batch["time_below_20"]
    b50 = batch["time_below_50"]
    b75 = batch["time_below_75"]
    a90 = batch["time_above_90"]
    print(f"  critical (<20)      : {b20['mean']:.1%}  median={b20['median']:.1%}")
    print(f"  low (20-50)         : {b50['mean'] - b20['mean']:.1%}")
    print(f"  below normal (<75)  : {b75['mean']:.1%}  median={b75['median']:.1%}")
    print(f"  high (>90)          : {a90['mean']:.1%}  median={a90['median']:.1%}")
    print()


def _print_productivity(batch: BatchResult) -> None:
    print("Productivity impact:")
    mp = batch["mean_productivity"]
    print(f"  mean multiplier     : {mp['mean']:.2f}  median={mp['median']:.2f}")
    print(f"  range               : [{mp['min']:.2f}, {mp['max']:.2f}]")
    print(f"  effective capacity  : {mp['mean'] * 100:.0f}% of nominal")
    print()


def _print_delta_breakdown(batch: BatchResult) -> None:
    print("Happiness delta breakdown (avg per run):")
    for k, v in batch["delta_breakdown"].items():
        sign = "+" if v["mean"] >= 0 else ""
        print(f"  {k:15} : {sign}{v['mean']:.1f}  median={v['median']:.1f}")
    print()


def _print_hourly_curves(batch: BatchResult, hours: int) -> None:
    if hours > 24:
        return
    print("Hourly curves (average per run):")
    print("  hour | HAPPY | PROD% | POWER | FOOD | WATER | INC")
    print("  " + "-" * 55)
    for h in range(hours):
        ha = batch["happiness_curve"][h]
        pr = batch["productivity_curve"][h] * 100
        pw = batch["power_curve"][h]
        f = batch["food_curve"][h]
        w = batch["water_curve"][h]
        i = batch["incidents_curve"][h]
        print(f"  {h:4} | {ha:5.1f} | {pr:5.1f} | {pw:5.0f} | {f:4.0f} | {w:5.0f} | {i:3.0f}")
    print()


def _print_balance(batch: BatchResult) -> None:
    mean_h = batch["mean_happiness"]["mean"]
    below_75 = batch["time_below_75"]["mean"]
    prod = batch["mean_productivity"]["mean"]

    print("Balance assessment:")
    if mean_h < 30:
        print("  Mean happiness <30 — CRITICAL. Vault is in collapse.")
    elif mean_h < 50:
        print("  Mean happiness 30-50 — LOW. Major morale issues.")
    elif mean_h < 70:
        print("  Mean happiness 50-70 — MODERATE. Room for improvement.")
    elif mean_h < 85:
        print("  Mean happiness 70-85 — GOOD. Healthy vault.")
    else:
        print("  Mean happiness >85 — EXCELLENT. Dwellers are thriving.")
    print(f"  Time below 75%={below_75:.1%}, productivity={prod:.1%}")
    print()


def print_report(batch: BatchResult, detailed: bool = False) -> None:
    cfg: HappinessConfig = batch["config"]
    hours = batch["simulation_hours"]
    runs = batch["runs"]

    print()
    print(banner(f"Happiness Simulation: {hours}h x {runs} runs"))
    print()
    _print_params(cfg)
    _print_happiness_distribution(batch)
    _print_time_bands(batch)
    _print_productivity(batch)
    _print_delta_breakdown(batch)
    if detailed:
        _print_hourly_curves(batch, hours)
    _print_balance(batch)


def print_sweep_report(results: list[BatchResult], param_name: str) -> None:
    print()
    print(banner(f"Parameter sweep: {param_name}"))
    print()
    print(
        f"{'Value':>12} | {'Happy':>5} | {'Prod%':>5} | {'<20':>5} | {'<50':>5} | "
        f"{'<75':>5} | {'>90':>5} | {'Min':>5} | {'Max':>5} | Verdict"
    )
    print("-" * TERMINAL_WIDTH)

    for r in results:
        cfg: HappinessConfig = r["config"]
        value = getattr(cfg, param_name)
        happy = r["mean_happiness"]["mean"]
        prod = r["mean_productivity"]["mean"] * 100
        b20 = r["time_below_20"]["mean"] * 100
        b50 = r["time_below_50"]["mean"] * 100
        b75 = r["time_below_75"]["mean"] * 100
        a90 = r["time_above_90"]["mean"] * 100
        mn = r["min_happiness"]["mean"]
        mx = r["max_happiness"]["mean"]

        if happy < 30:
            verdict = "critical"
        elif happy < 50:
            verdict = "low"
        elif happy < 70:
            verdict = "ok"
        elif happy < 85:
            verdict = "good"
        else:
            verdict = "great"

        vstr = f"{value:.2f}" if isinstance(value, float) else str(value)
        line = f"{vstr:>12} | {happy:>5.1f} | {prod:>5.1f} | {b20:>5.1f} | {b50:>5.1f}"
        line += f" | {b75:>5.1f} | {a90:>5.1f} | {mn:>5.1f} | {mx:>5.1f} | {verdict}"
        print(line)
    print()


app = typer.Typer(help="Simulate happiness balance for the Fallout Shelter game.")


@app.command()
def simulate(
    days: Annotated[int, typer.Option(help="Simulation length in days")] = DEFAULT_SIMULATION_DAYS,
    runs: Annotated[int, typer.Option(help="Monte Carlo runs (higher = smoother)")] = DEFAULT_RUNS,
    sweep: Annotated[str | None, typer.Option(help="Parameter to sweep")] = None,
    tick_interval: Annotated[int, typer.Option()] = DEFAULT_TICK_INTERVAL,
    starting_dwellers: Annotated[int, typer.Option()] = DEFAULT_STARTING_DWELLERS,
    working_ratio: Annotated[float, typer.Option()] = DEFAULT_WORKING_RATIO,
    training_ratio: Annotated[float, typer.Option()] = DEFAULT_TRAINING_RATIO,
    healthy_ratio: Annotated[float, typer.Option()] = DEFAULT_HEALTHY_RATIO,
    partner_ratio: Annotated[float, typer.Option()] = DEFAULT_PARTNER_RATIO,
    base_decay: Annotated[float, typer.Option()] = DEFAULT_BASE_DECAY,
    resource_decay: Annotated[float, typer.Option()] = DEFAULT_RESOURCE_SHORTAGE_DECAY,
    critical_decay: Annotated[float, typer.Option()] = DEFAULT_CRITICAL_RESOURCE_DECAY,
    incident_penalty: Annotated[float, typer.Option()] = DEFAULT_INCIDENT_PENALTY,
    idle_decay: Annotated[float, typer.Option()] = DEFAULT_IDLE_DECAY,
    working_gain: Annotated[float, typer.Option()] = DEFAULT_WORKING_GAIN,
    incident_chance: Annotated[float, typer.Option()] = DEFAULT_INCIDENT_CHANCE_PER_TICK,
    resource_drift: Annotated[float, typer.Option()] = DEFAULT_RESOURCE_DRIFT,
    detailed: Annotated[bool, typer.Option(help="Show hourly cumulative curves")] = False,
    seed: Annotated[int | None, typer.Option(help="Fix random seed for reproducibility")] = None,
) -> None:
    hours = days * 24

    baseline = HappinessConfig(
        tick_interval=tick_interval,
        starting_dwellers=starting_dwellers,
        working_ratio=working_ratio,
        training_ratio=training_ratio,
        healthy_ratio=healthy_ratio,
        partner_ratio=partner_ratio,
        base_decay=base_decay,
        resource_shortage_decay=resource_decay,
        critical_resource_decay=critical_decay,
        incident_penalty=incident_penalty,
        idle_decay=idle_decay,
        working_gain=working_gain,
        incident_chance_per_tick=incident_chance,
        resource_drift=resource_drift,
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
