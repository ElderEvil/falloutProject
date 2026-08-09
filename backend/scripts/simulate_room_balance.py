"""
Room Balance Simulator — focused vault room and resource production simulation.

Simulates room building, upgrades, dweller assignment, and resource economy
to help balance room costs, production rates, and population growth pressure.
Run standalone without the full backend.

Usage:
    cd backend
    uv run python scripts/simulate_room_balance.py
    uv run python scripts/simulate_room_balance.py --days 3 --runs 50
    uv run python scripts/simulate_room_balance.py --sweep base_production_rate
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

DEFAULT_STARTING_CAPS = 500
DEFAULT_STARTING_DWELLERS = 10
DEFAULT_AVG_SPECIAL = 4.0

DEFAULT_BASE_PRODUCTION_RATE = 0.1
DEFAULT_TIER_1_MULT = 1.0
DEFAULT_TIER_2_MULT = 1.5
DEFAULT_TIER_3_MULT = 2.0
DEFAULT_POWER_CONSUMPTION_RATE = 0.5 / 60
DEFAULT_FOOD_CONSUMPTION_PER_DWELLER = 0.36 / 60
DEFAULT_WATER_CONSUMPTION_PER_DWELLER = 0.36 / 60

DEFAULT_RECRUITMENT_RATE_PER_HOUR = 1.0 / 6.0
DEFAULT_CONCEPTION_CHANCE_PER_TICK = 0.20
DEFAULT_PREGNANCY_DURATION_HOURS = 3
DEFAULT_CHILD_GROWTH_DURATION_HOURS = 3

DEFAULT_ROOM_BUILD_INTERVAL_HOURS = 2
DEFAULT_ROOM_UPGRADE_INTERVAL_HOURS = 4


@dataclasses.dataclass(frozen=True)
class RoomTemplate:
    name: str
    category: str
    ability: str | None
    base_cost: int
    incremental_cost: int
    t2_upgrade_cost: int | None
    t3_upgrade_cost: int | None
    size: int = 3
    output_formula: str | None = None
    capacity_formula: str | None = None
    population_required: int | None = None

    def output(self, tier: int) -> int:
        if self.output_formula is None:
            return 0
        base = {"Power Generator": 10, "Diner": 10, "Water Treatment": 10, "Medbay": 3, "Science Lab": 3}
        return base.get(self.name, 5) * tier

    def capacity(self, tier: int) -> int:
        if self.capacity_formula is None:
            return 0
        base = {"Living room": 4, "Storage room": 10}
        return base.get(self.name, 5) * tier

    def build_cost(self, existing_count: int) -> int:
        return self.base_cost + existing_count * (self.incremental_cost or 0)

    def upgrade_cost(self, current_tier: int) -> int | None:
        if current_tier == 1:
            return self.t2_upgrade_cost
        if current_tier == 2:
            return self.t3_upgrade_cost
        return None


ROOM_TEMPLATES: dict[str, RoomTemplate] = {
    "Power Generator": RoomTemplate(
        name="Power Generator",
        category="production",
        ability="strength",
        base_cost=100,
        incremental_cost=25,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        output_formula="(2*S*(L+4))-2",
    ),
    "Diner": RoomTemplate(
        name="Diner",
        category="production",
        ability="agility",
        base_cost=100,
        incremental_cost=25,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        output_formula="(2*S*(L+4))-2",
    ),
    "Water Treatment": RoomTemplate(
        name="Water Treatment",
        category="production",
        ability="perception",
        base_cost=100,
        incremental_cost=25,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        output_formula="(2*S*(L+4))-2",
    ),
    "Living room": RoomTemplate(
        name="Living room",
        category="capacity",
        ability="charisma",
        base_cost=100,
        incremental_cost=25,
        t2_upgrade_cost=500,
        t3_upgrade_cost=1500,
        capacity_formula="2*S/3*(L+4)-2",
    ),
    "Storage room": RoomTemplate(
        name="Storage room",
        category="capacity",
        ability="endurance",
        base_cost=300,
        incremental_cost=75,
        t2_upgrade_cost=750,
        t3_upgrade_cost=1500,
        capacity_formula="5*S*(L+1)",
        population_required=12,
    ),
    "Medbay": RoomTemplate(
        name="Medbay",
        category="production",
        ability="intelligence",
        base_cost=400,
        incremental_cost=100,
        t2_upgrade_cost=1000,
        t3_upgrade_cost=3000,
        output_formula="S",
        capacity_formula="10*S",
        population_required=14,
    ),
    "Science Lab": RoomTemplate(
        name="Science Lab",
        category="production",
        ability="intelligence",
        base_cost=400,
        incremental_cost=100,
        t2_upgrade_cost=1000,
        t3_upgrade_cost=3000,
        output_formula="S",
        capacity_formula="10*S",
        population_required=16,
    ),
    "Radio studio": RoomTemplate(
        name="Radio studio",
        category="production",
        ability="charisma",
        base_cost=600,
        incremental_cost=150,
        t2_upgrade_cost=1500,
        t3_upgrade_cost=4500,
        population_required=20,
    ),
}


@dataclasses.dataclass
class SimulatedRoom:
    template: RoomTemplate
    tier: int = 1
    assigned_dwellers: int = 0

    @property
    def name(self) -> str:
        return self.template.name

    @property
    def ability(self) -> str | None:
        return self.template.ability

    @property
    def output(self) -> int:
        return self.template.output(self.tier)

    @property
    def capacity(self) -> int:
        return self.template.capacity(self.tier)

    @property
    def category(self) -> str:
        return self.template.category

    def upgrade_cost(self) -> int | None:
        return self.template.upgrade_cost(self.tier)

    def power_consumption(self, seconds: int, rate: float) -> float:
        return rate * self.template.size * self.tier * seconds


@dataclasses.dataclass(frozen=True)
class RoomConfig:
    tick_interval: int = DEFAULT_TICK_INTERVAL
    starting_caps: int = DEFAULT_STARTING_CAPS
    starting_dwellers: int = DEFAULT_STARTING_DWELLERS
    avg_special: float = DEFAULT_AVG_SPECIAL

    base_production_rate: float = DEFAULT_BASE_PRODUCTION_RATE
    tier_1_multiplier: float = DEFAULT_TIER_1_MULT
    tier_2_multiplier: float = DEFAULT_TIER_2_MULT
    tier_3_multiplier: float = DEFAULT_TIER_3_MULT
    power_consumption_rate: float = DEFAULT_POWER_CONSUMPTION_RATE
    food_consumption_per_dweller: float = DEFAULT_FOOD_CONSUMPTION_PER_DWELLER
    water_consumption_per_dweller: float = DEFAULT_WATER_CONSUMPTION_PER_DWELLER

    recruitment_rate_per_hour: float = DEFAULT_RECRUITMENT_RATE_PER_HOUR
    conception_chance_per_tick: float = DEFAULT_CONCEPTION_CHANCE_PER_TICK
    pregnancy_duration_hours: int = DEFAULT_PREGNANCY_DURATION_HOURS
    child_growth_duration_hours: int = DEFAULT_CHILD_GROWTH_DURATION_HOURS

    room_build_interval_hours: int = DEFAULT_ROOM_BUILD_INTERVAL_HOURS
    room_upgrade_interval_hours: int = DEFAULT_ROOM_UPGRADE_INTERVAL_HOURS

    def get_tier_multiplier(self, tier: int) -> float:
        return {1: self.tier_1_multiplier, 2: self.tier_2_multiplier, 3: self.tier_3_multiplier}.get(tier, 1.0)


@dataclasses.dataclass
class Pregnancy:
    start_time: int
    father_id: int
    mother_id: int

    def is_due(self, now: int, duration_hours: int) -> bool:
        return (now - self.start_time) >= duration_hours * 3600


@dataclasses.dataclass
class VaultState:
    population: int = DEFAULT_STARTING_DWELLERS
    adults: int = DEFAULT_STARTING_DWELLERS
    children: int = 0
    power: float = 100.0
    food: float = 100.0
    water: float = 100.0
    power_max: float = 100.0
    food_max: float = 100.0
    water_max: float = 100.0
    caps: int = DEFAULT_STARTING_CAPS
    happiness: float = 75.0
    pregnancies: list[Pregnancy] = dataclasses.field(default_factory=list)
    total_births: int = 0
    total_deaths: int = 0
    room_instances: list[SimulatedRoom] = dataclasses.field(default_factory=list)
    last_build_time: int = -7200
    last_upgrade_time: int = -14400

    @property
    def rooms(self) -> int:
        return len(self.room_instances)

    @property
    def production_rooms(self) -> int:
        return sum(1 for r in self.room_instances if r.category == "production" and r.output > 0)

    def population_cap(self) -> int:
        cap = 10
        for room in self.room_instances:
            if room.name == "Living room":
                cap += room.capacity
        return cap


@dataclasses.dataclass
class SimulationResult:
    config: RoomConfig
    total_ticks: int

    population_by_hour: list[int]
    power_by_hour: list[float]
    food_by_hour: list[float]
    water_by_hour: list[float]
    happiness_by_hour: list[float]
    rooms_by_hour: list[int]
    production_rooms_by_hour: list[int]
    population_cap_by_hour: list[int]
    caps_by_hour: list[int]

    final_population: int
    final_rooms: int
    final_production_rooms: int
    final_population_cap: int
    final_caps: int
    room_builds: int
    room_upgrades: int
    total_births: int
    total_recruits: int
    resource_warnings: int


class RoomSimulator:
    def __init__(self, config: RoomConfig) -> None:
        self.cfg = config

    def run(self, simulation_hours: int, seed: int | None = None) -> SimulationResult:
        if seed is not None:
            random.seed(seed)

        duration_seconds = simulation_hours * 3600
        ticks = duration_seconds // self.cfg.tick_interval + 1

        vault = VaultState(
            caps=self.cfg.starting_caps,
            population=self.cfg.starting_dwellers,
            adults=self.cfg.starting_dwellers,
            last_build_time=-self.cfg.room_build_interval_hours * 3600,
            last_upgrade_time=-self.cfg.room_upgrade_interval_hours * 3600,
        )
        self._init_starting_rooms(vault)
        resource_warnings = 0
        room_builds = 0
        room_upgrades = 0
        total_recruits = 0

        pop_curve = [0] * simulation_hours
        power_curve = [0.0] * simulation_hours
        food_curve = [0.0] * simulation_hours
        water_curve = [0.0] * simulation_hours
        happy_curve = [0.0] * simulation_hours
        rooms_curve = [0] * simulation_hours
        prod_rooms_curve = [0] * simulation_hours
        pop_cap_curve = [0] * simulation_hours
        caps_curve = [0] * simulation_hours

        for tick in range(ticks):
            now = tick * self.cfg.tick_interval
            hour_idx = min(now // 3600, simulation_hours - 1)

            recruits = self._process_recruitment()
            total_recruits += recruits
            for _ in range(recruits):
                vault.population += 1
                vault.adults += 1

            births = self._process_breeding(vault, now)
            vault.total_births += births

            builds, upgrades = self._process_rooms(vault, now)
            room_builds += builds
            room_upgrades += upgrades

            self._process_resources(vault)

            if self._has_resource_warning(vault):
                resource_warnings += 1

            pop_curve[hour_idx] = vault.population
            power_curve[hour_idx] = vault.power
            food_curve[hour_idx] = vault.food
            water_curve[hour_idx] = vault.water
            happy_curve[hour_idx] = vault.happiness
            rooms_curve[hour_idx] = vault.rooms
            prod_rooms_curve[hour_idx] = vault.production_rooms
            pop_cap_curve[hour_idx] = vault.population_cap()
            caps_curve[hour_idx] = vault.caps

        return SimulationResult(
            config=self.cfg,
            total_ticks=ticks,
            population_by_hour=pop_curve,
            power_by_hour=power_curve,
            food_by_hour=food_curve,
            water_by_hour=water_curve,
            happiness_by_hour=happy_curve,
            rooms_by_hour=rooms_curve,
            production_rooms_by_hour=prod_rooms_curve,
            population_cap_by_hour=pop_cap_curve,
            caps_by_hour=caps_curve,
            final_population=vault.population,
            final_rooms=vault.rooms,
            final_production_rooms=vault.production_rooms,
            final_population_cap=vault.population_cap(),
            final_caps=vault.caps,
            room_builds=room_builds,
            room_upgrades=room_upgrades,
            total_births=vault.total_births,
            total_recruits=total_recruits,
            resource_warnings=resource_warnings,
        )

    def _init_starting_rooms(self, vault: VaultState) -> None:
        vault.room_instances = [
            SimulatedRoom(template=ROOM_TEMPLATES["Power Generator"], tier=1, assigned_dwellers=2),
            SimulatedRoom(template=ROOM_TEMPLATES["Diner"], tier=1, assigned_dwellers=2),
            SimulatedRoom(template=ROOM_TEMPLATES["Water Treatment"], tier=1, assigned_dwellers=2),
            SimulatedRoom(template=ROOM_TEMPLATES["Living room"], tier=1),
        ]

    def _process_rooms(self, vault: VaultState, now: int) -> tuple[int, int]:
        self._assign_dwellers(vault)
        builds = self._build_rooms(vault, now)
        upgrades = self._upgrade_rooms(vault, now)
        return builds, upgrades

    def _assign_dwellers(self, vault: VaultState) -> None:
        prod_rooms = [r for r in vault.room_instances if r.category == "production" and r.output > 0]
        if not prod_rooms:
            return
        per_room = vault.adults // len(prod_rooms)
        rem = vault.adults % len(prod_rooms)
        for i, room in enumerate(prod_rooms):
            room.assigned_dwellers = per_room + (1 if i < rem else 0)

    def _build_rooms(self, vault: VaultState, now: int) -> int:
        if now - vault.last_build_time < self.cfg.room_build_interval_hours * 3600:
            return 0
        if vault.population >= vault.population_cap() - 2 and self._try_build(vault, "Living room", now):
            return 1
        checks = [
            (vault.power, vault.power_max, "Power Generator"),
            (vault.food, vault.food_max, "Diner"),
            (vault.water, vault.water_max, "Water Treatment"),
        ]
        checks.sort(key=lambda x: x[0] / x[1] if x[1] > 0 else 1.0)
        for current, max_val, room_name in checks:
            if current < max_val * 0.2 and self._try_build(vault, room_name, now):
                return 1
        return 0

    def _try_build(self, vault: VaultState, room_name: str, now: int) -> bool:
        template = ROOM_TEMPLATES.get(room_name)
        if template is None:
            return False
        if template.population_required and vault.population < template.population_required:
            return False
        existing = sum(1 for r in vault.room_instances if r.name == room_name)
        cost = template.build_cost(existing)
        if vault.caps >= cost:
            vault.caps -= cost
            vault.room_instances.append(SimulatedRoom(template=template, tier=1))
            vault.last_build_time = now
            return True
        return False

    def _upgrade_rooms(self, vault: VaultState, now: int) -> int:
        if now - vault.last_upgrade_time < self.cfg.room_upgrade_interval_hours * 3600:
            return 0
        for room in vault.room_instances:
            cost = room.upgrade_cost()
            if cost is not None and vault.caps >= cost and room.tier < 3:
                vault.caps -= cost
                room.tier += 1
                vault.last_upgrade_time = now
                return 1
        return 0

    def _calculate_production(self, vault: VaultState, seconds: int) -> dict[str, float]:
        production = {"power": 0.0, "food": 0.0, "water": 0.0}
        power_outage = vault.power <= 0
        for room in vault.room_instances:
            if room.category != "production" or room.output <= 0 or room.assigned_dwellers <= 0:
                continue
            if power_outage and room.ability != "strength":
                continue
            ability_sum = room.assigned_dwellers * self.cfg.avg_special
            tier_mult = self.cfg.get_tier_multiplier(room.tier)
            prod = room.output * ability_sum * self.cfg.base_production_rate * tier_mult * seconds
            match room.ability:
                case "strength":
                    production["power"] += prod
                case "agility":
                    production["food"] += prod
                case "perception":
                    production["water"] += prod
                case "endurance":
                    per = prod / 3
                    for k in ("power", "food", "water"):
                        production[k] += per
        return production

    def _process_resources(self, vault: VaultState) -> None:
        seconds = self.cfg.tick_interval

        power_consumption = sum(
            r.power_consumption(seconds, self.cfg.power_consumption_rate) for r in vault.room_instances
        )
        food_consumption = vault.population * self.cfg.food_consumption_per_dweller * seconds
        water_consumption = vault.population * self.cfg.water_consumption_per_dweller * seconds

        production = self._calculate_production(vault, seconds)

        vault.power = max(0, min(vault.power - power_consumption + production["power"], vault.power_max))
        vault.food = max(0, min(vault.food - food_consumption + production["food"], vault.food_max))
        vault.water = max(0, min(vault.water - water_consumption + production["water"], vault.water_max))

        happiness_delta = -0.5
        if vault.food < vault.food_max * 0.2:
            happiness_delta -= 2.0
        if vault.water < vault.water_max * 0.2:
            happiness_delta -= 2.0
        if vault.power < vault.power_max * 0.2:
            happiness_delta -= 1.0
        if vault.adults > 0:
            happiness_delta += 0.3
        vault.happiness = max(0, min(100, vault.happiness + happiness_delta))

    def _process_recruitment(self) -> int:
        if self.cfg.recruitment_rate_per_hour <= 0:
            return 0
        rate_per_tick = self.cfg.recruitment_rate_per_hour * (self.cfg.tick_interval / 3600.0)
        recruits = 0
        while rate_per_tick > 1.0:
            recruits += 1
            rate_per_tick -= 1.0
        if random.random() < rate_per_tick:
            recruits += 1
        return recruits

    def _process_breeding(self, vault: VaultState, now: int) -> int:
        births = 0

        if vault.adults >= 2:
            eligible_pairs = min(vault.adults // 2, 5)
            for _ in range(eligible_pairs):
                if random.random() < self.cfg.conception_chance_per_tick:
                    vault.pregnancies.append(Pregnancy(start_time=now, father_id=0, mother_id=0))

        due = [p for p in vault.pregnancies if p.is_due(now, self.cfg.pregnancy_duration_hours)]
        for _ in due:
            births += 1
            vault.children += 1
            vault.population += 1
            vault.pregnancies = [p for p in vault.pregnancies if not p.is_due(now, self.cfg.pregnancy_duration_hours)]

        growth_chance = self.cfg.tick_interval / (self.cfg.child_growth_duration_hours * 3600)
        while vault.children > 0 and random.random() < growth_chance:
            vault.children -= 1
            vault.adults += 1

        return births

    def _has_resource_warning(self, vault: VaultState) -> bool:
        checks = ((vault.power, vault.power_max), (vault.food, vault.food_max), (vault.water, vault.water_max))
        return any(resource < max_val * 0.05 or resource < max_val * 0.2 for resource, max_val in checks)


BatchResult = dict[str, Any]


@dataclasses.dataclass
class _Aggregates:
    final_pop: list[int] = dataclasses.field(default_factory=list)
    final_rooms: list[int] = dataclasses.field(default_factory=list)
    final_prod_rooms: list[int] = dataclasses.field(default_factory=list)
    final_pop_cap: list[int] = dataclasses.field(default_factory=list)
    final_caps: list[int] = dataclasses.field(default_factory=list)
    room_builds: list[int] = dataclasses.field(default_factory=list)
    room_upgrades: list[int] = dataclasses.field(default_factory=list)
    total_births: list[int] = dataclasses.field(default_factory=list)
    total_recruits: list[int] = dataclasses.field(default_factory=list)
    resource_warnings: list[int] = dataclasses.field(default_factory=list)
    final_power: list[float] = dataclasses.field(default_factory=list)
    final_food: list[float] = dataclasses.field(default_factory=list)
    final_water: list[float] = dataclasses.field(default_factory=list)
    final_happiness: list[float] = dataclasses.field(default_factory=list)

    def collect(self, result: SimulationResult) -> None:
        self.final_pop.append(result.final_population)
        self.final_rooms.append(result.final_rooms)
        self.final_prod_rooms.append(result.final_production_rooms)
        self.final_pop_cap.append(result.final_population_cap)
        self.final_caps.append(result.final_caps)
        self.room_builds.append(result.room_builds)
        self.room_upgrades.append(result.room_upgrades)
        self.total_births.append(result.total_births)
        self.total_recruits.append(result.total_recruits)
        self.resource_warnings.append(result.resource_warnings)
        self.final_power.append(result.power_by_hour[-1] if result.power_by_hour else 0)
        self.final_food.append(result.food_by_hour[-1] if result.food_by_hour else 0)
        self.final_water.append(result.water_by_hour[-1] if result.water_by_hour else 0)
        self.final_happiness.append(result.happiness_by_hour[-1] if result.happiness_by_hour else 0)


@dataclasses.dataclass
class _Curves:
    pop: list[float] = dataclasses.field(default_factory=list)
    power: list[float] = dataclasses.field(default_factory=list)
    food: list[float] = dataclasses.field(default_factory=list)
    water: list[float] = dataclasses.field(default_factory=list)
    happiness: list[float] = dataclasses.field(default_factory=list)
    rooms: list[float] = dataclasses.field(default_factory=list)
    prod_rooms: list[float] = dataclasses.field(default_factory=list)
    pop_cap: list[float] = dataclasses.field(default_factory=list)
    caps: list[float] = dataclasses.field(default_factory=list)

    @classmethod
    def zeroed(cls, hours: int) -> "_Curves":
        return cls(**{k: [0.0] * hours for k in dataclasses.asdict(cls())})

    def add_result(self, result: SimulationResult, hours: int) -> None:
        for h in range(hours):
            self.pop[h] += result.population_by_hour[h]
            self.power[h] += result.power_by_hour[h]
            self.food[h] += result.food_by_hour[h]
            self.water[h] += result.water_by_hour[h]
            self.happiness[h] += result.happiness_by_hour[h]
            self.rooms[h] += result.rooms_by_hour[h]
            self.prod_rooms[h] += result.production_rooms_by_hour[h]
            self.pop_cap[h] += result.population_cap_by_hour[h]
            self.caps[h] += result.caps_by_hour[h]

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


def run_monte_carlo(config: RoomConfig, simulation_hours: int, runs: int) -> BatchResult:
    sim = RoomSimulator(config)
    ag = _Aggregates()
    curves = _Curves.zeroed(simulation_hours)

    for i in range(runs):
        result = sim.run(simulation_hours, seed=i)
        ag.collect(result)
        curves.add_result(result, simulation_hours)

    curves.divide(runs)

    return {
        "config": config,
        "runs": runs,
        "simulation_hours": simulation_hours,
        "population": _stats(ag.final_pop),
        "rooms": _stats(ag.final_rooms),
        "production_rooms": _stats(ag.final_prod_rooms),
        "population_cap": _stats(ag.final_pop_cap),
        "caps": _stats(ag.final_caps),
        "room_builds": _stats(ag.room_builds),
        "room_upgrades": _stats(ag.room_upgrades),
        "births": _stats(ag.total_births),
        "recruits": _stats(ag.total_recruits),
        "resource_warnings": _stats(ag.resource_warnings),
        "final_power": _stats(ag.final_power),
        "final_food": _stats(ag.final_food),
        "final_water": _stats(ag.final_water),
        "final_happiness": _stats(ag.final_happiness),
        "pop_curve": curves.pop,
        "power_curve": curves.power,
        "food_curve": curves.food,
        "water_curve": curves.water,
        "happiness_curve": curves.happiness,
        "rooms_curve": curves.rooms,
        "prod_rooms_curve": curves.prod_rooms,
        "pop_cap_curve": curves.pop_cap,
        "caps_curve": curves.caps,
    }


SWEEP_RANGES: dict[str, list[Any]] = {
    "base_production_rate": [0.05, 0.08, 0.10, 0.15, 0.20, 0.30],
    "starting_caps": [200, 500, 1000, 2000],
    "room_build_interval_hours": [1, 2, 3, 4, 6],
    "room_upgrade_interval_hours": [2, 4, 6, 8, 12],
    "recruitment_rate_per_hour": [0.0, 1 / 12, 1 / 6, 1 / 3],
    "conception_chance_per_tick": [0.0, 0.10, 0.20, 0.30, 0.50],
    "avg_special": [2.0, 3.0, 4.0, 5.0, 6.0],
}


def run_parameter_sweep(param_name: str, baseline: RoomConfig, simulation_hours: int, runs: int) -> list[BatchResult]:
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


def _print_params(cfg: RoomConfig) -> None:
    print("Parameters:")
    print(f"  tick_interval       = {cfg.tick_interval}s")
    print(f"  starting_caps       = {cfg.starting_caps}")
    print(f"  starting_dwellers   = {cfg.starting_dwellers}")
    print(f"  avg_special         = {cfg.avg_special:.1f}")
    print(f"  base_production     = {cfg.base_production_rate:.2f}")
    print(f"  recruitment_rate    = {cfg.recruitment_rate_per_hour:.3f}/hour")
    print(f"  conception_chance   = {cfg.conception_chance_per_tick:.0%}/tick")
    print(f"  build_interval      = {cfg.room_build_interval_hours}h")
    print(f"  upgrade_interval    = {cfg.room_upgrade_interval_hours}h")
    print()


def _print_vault_state(batch: BatchResult) -> None:
    print("Vault state:")
    print(f"  final population    : {fmt_stats(batch['population'])}")
    print(f"  total births        : {fmt_stats(batch['births'])}")
    print(f"  total recruits      : {fmt_stats(batch['recruits'])}")
    print()


def _print_room_state(batch: BatchResult) -> None:
    print("Room state:")
    print(f"  total rooms         : {fmt_stats(batch['rooms'])}")
    print(f"  production rooms    : {fmt_stats(batch['production_rooms'])}")
    print(f"  population cap      : {fmt_stats(batch['population_cap'])}")
    print(f"  caps remaining      : {fmt_stats(batch['caps'])}")
    print(f"  room builds         : {fmt_stats(batch['room_builds'])}")
    print(f"  room upgrades       : {fmt_stats(batch['room_upgrades'])}")
    print()


def _print_resources(batch: BatchResult) -> None:
    print("Final resource state:")
    print(f"  power     : {fmt_stats(batch['final_power'])}")
    print(f"  food      : {fmt_stats(batch['final_food'])}")
    print(f"  water     : {fmt_stats(batch['final_water'])}")
    print(f"  happiness : {fmt_stats(batch['final_happiness'])}")
    print()


def _print_hourly_curves(batch: BatchResult, hours: int) -> None:
    if hours > 24:
        return
    print("Hourly curves (average per run):")
    print("  hour | POP | ROOMS | PROD | POPCAP | CAPS | POWER | FOOD | WATER | HAPPY")
    print("  " + "-" * 75)
    for h in range(hours):
        p = batch["pop_curve"][h]
        r = batch["rooms_curve"][h]
        pr = batch["prod_rooms_curve"][h]
        pc = batch["pop_cap_curve"][h]
        c = batch["caps_curve"][h]
        pw = batch["power_curve"][h]
        f = batch["food_curve"][h]
        w = batch["water_curve"][h]
        hp = batch["happiness_curve"][h]
        line = f"  {h:4} | {p:3.0f} | {r:5.0f} | {pr:4.0f} | {pc:6.0f} | {c:4.0f}"
        line += f" | {pw:5.0f} | {f:4.0f} | {w:5.0f} | {hp:5.1f}"
        print(line)
    print()


def _print_balance(batch: BatchResult, hours: int) -> None:
    mean_pop = batch["population"]["mean"]
    mean_cap = batch["population_cap"]["mean"]
    mean_rooms = batch["rooms"]["mean"]
    mean_warnings = batch["resource_warnings"]["mean"]

    print("Balance assessment:")
    if mean_pop > mean_cap * 0.9:
        print("  Population near cap — build more Living rooms or reduce growth.")
    elif mean_pop < mean_cap * 0.5:
        print("  Population well below cap — room capacity is abundant.")
    else:
        print("  Population/capacity ratio is healthy.")
    print(f"  Avg rooms={mean_rooms:.1f}, resource warnings={mean_warnings:.1f} over {hours}h")
    print()


def print_report(batch: BatchResult, detailed: bool = False) -> None:
    cfg: RoomConfig = batch["config"]
    hours = batch["simulation_hours"]
    runs = batch["runs"]

    print()
    print(banner(f"Room Simulation: {hours}h x {runs} runs"))
    print()
    _print_params(cfg)
    _print_vault_state(batch)
    _print_room_state(batch)
    _print_resources(batch)
    if detailed:
        _print_hourly_curves(batch, hours)
    _print_balance(batch, hours)


def print_sweep_report(results: list[BatchResult], param_name: str) -> None:
    print()
    print(banner(f"Parameter sweep: {param_name}"))
    print()
    print(
        f"{'Value':>12} | {'Pop':>5} | {'Rooms':>5} | {'Prod':>5} | {'Cap':>5} | "
        f"{'Caps':>5} | {'Build':>5} | {'Upg':>5} | {'Power':>5} | {'Food':>5} | {'Water':>5} | Verdict"
    )
    print("-" * TERMINAL_WIDTH)

    for r in results:
        cfg: RoomConfig = r["config"]
        value = getattr(cfg, param_name)
        pop = r["population"]["mean"]
        rooms = r["rooms"]["mean"]
        prod = r["production_rooms"]["mean"]
        cap = r["population_cap"]["mean"]
        caps = r["caps"]["mean"]
        builds = r["room_builds"]["mean"]
        upgrades = r["room_upgrades"]["mean"]
        power = r["final_power"]["mean"]
        food = r["final_food"]["mean"]
        water = r["final_water"]["mean"]

        if pop > cap * 0.9:
            verdict = "crowded"
        elif power < 20 or food < 20 or water < 20:
            verdict = "starving"
        else:
            verdict = "balanced"

        vstr = f"{value:.2f}" if isinstance(value, float) else str(value)
        line = f"{vstr:>12} | {pop:>5.0f} | {rooms:>5.0f} | {prod:>5.0f} | {cap:>5.0f}"
        line += f" | {caps:>5.0f} | {builds:>5.1f} | {upgrades:>5.1f}"
        line += f" | {power:>5.0f} | {food:>5.0f} | {water:>5.0f} | {verdict}"
        print(line)
    print()


app = typer.Typer(help="Simulate room balance for the Fallout Shelter game.")


@app.command()
def simulate(  # noqa: PLR0917 - Typer command with many CLI options
    days: Annotated[int, typer.Option(help="Simulation length in days")] = DEFAULT_SIMULATION_DAYS,
    runs: Annotated[int, typer.Option(help="Monte Carlo runs (higher = smoother)")] = DEFAULT_RUNS,
    sweep: Annotated[str | None, typer.Option(help="Parameter to sweep")] = None,
    tick_interval: Annotated[int, typer.Option()] = DEFAULT_TICK_INTERVAL,
    starting_caps: Annotated[int, typer.Option()] = DEFAULT_STARTING_CAPS,
    starting_dwellers: Annotated[int, typer.Option()] = DEFAULT_STARTING_DWELLERS,
    avg_special: Annotated[float, typer.Option()] = DEFAULT_AVG_SPECIAL,
    base_production_rate: Annotated[float, typer.Option()] = DEFAULT_BASE_PRODUCTION_RATE,
    recruitment_rate: Annotated[float, typer.Option()] = DEFAULT_RECRUITMENT_RATE_PER_HOUR,
    conception_chance: Annotated[float, typer.Option()] = DEFAULT_CONCEPTION_CHANCE_PER_TICK,
    build_interval: Annotated[int, typer.Option()] = DEFAULT_ROOM_BUILD_INTERVAL_HOURS,
    upgrade_interval: Annotated[int, typer.Option()] = DEFAULT_ROOM_UPGRADE_INTERVAL_HOURS,
    detailed: Annotated[bool, typer.Option(help="Show hourly cumulative curves")] = False,
    seed: Annotated[int | None, typer.Option(help="Fix random seed for reproducibility")] = None,
) -> None:
    hours = days * 24

    baseline = RoomConfig(
        tick_interval=tick_interval,
        starting_caps=starting_caps,
        starting_dwellers=starting_dwellers,
        avg_special=avg_special,
        base_production_rate=base_production_rate,
        recruitment_rate_per_hour=recruitment_rate,
        conception_chance_per_tick=conception_chance,
        room_build_interval_hours=build_interval,
        room_upgrade_interval_hours=upgrade_interval,
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
