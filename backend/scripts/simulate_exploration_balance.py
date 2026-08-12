"""Vault Balance Simulator — multi-system simulation for Fallout Shelter.

Simulates wasteland exploration, resource economy, incident system,
population growth, and medical production to help balance the game.
Run standalone without the full backend.

Usage:
    cd backend
    uv run python scripts/simulate_exploration_balance.py
    uv run python scripts/simulate_exploration_balance.py --days 7 --runs 100
    uv run python scripts/simulate_exploration_balance.py --sweep discovery_chance

Output:
    Prints statistics about all game systems and their interactions.
"""

from __future__ import annotations

import dataclasses
import random
import statistics
from typing import Annotated, Any

import typer

DEFAULT_TICK_INTERVAL = 60
DEFAULT_EVENT_INTERVAL = 600
DEFAULT_FIRST_EVENT_DELAY = 300
DEFAULT_DISCOVERY_CHANCE = 0.10
DEFAULT_DURATION_MIN = 1
DEFAULT_DURATION_MAX = 12
DEFAULT_CONCURRENT_EXPLORATIONS = 2

DEFAULT_RECRUITMENT_RATE_PER_HOUR = 1.0 / 6.0
DEFAULT_AVG_VISITED_PLACES = 1.5
DEFAULT_ORIGIN_SKIP_RATE = 0.05
DEFAULT_NAME_POOL_SIZE = 500

DEFAULT_BASE_PRODUCTION_RATE = 0.1
DEFAULT_TIER_1_MULT = 1.0
DEFAULT_TIER_2_MULT = 1.5
DEFAULT_TIER_3_MULT = 2.0
DEFAULT_POWER_CONSUMPTION_RATE = 0.5 / 60
DEFAULT_FOOD_CONSUMPTION_PER_DWELLER = 0.36 / 60
DEFAULT_WATER_CONSUMPTION_PER_DWELLER = 0.36 / 60
DEFAULT_RESOURCE_LOW_THRESHOLD = 0.20
DEFAULT_RESOURCE_CRITICAL_THRESHOLD = 0.05

DEFAULT_SPAWN_CHANCE_PER_HOUR = 0.05
DEFAULT_MIN_VAULT_POPULATION = 5
DEFAULT_MAX_ACTIVE_INCIDENTS = 5
DEFAULT_SPAWN_COOLDOWN_SECONDS = 120
DEFAULT_SPREAD_DURATION = 60
DEFAULT_MAX_SPREAD_COUNT = 3

DEFAULT_CONCEPTION_CHANCE_PER_TICK = 0.20
DEFAULT_PREGNANCY_DURATION_HOURS = 3
DEFAULT_CHILD_GROWTH_DURATION_HOURS = 3

DEFAULT_SIMULATION_DAYS = 3
DEFAULT_RUNS = 50


@dataclasses.dataclass(frozen=True)
class ExplorationConfig:
    tick_interval: int = DEFAULT_TICK_INTERVAL
    event_interval: int = DEFAULT_EVENT_INTERVAL
    first_event_delay: int = DEFAULT_FIRST_EVENT_DELAY
    discovery_chance: float = DEFAULT_DISCOVERY_CHANCE
    duration_min: int = DEFAULT_DURATION_MIN
    duration_max: int = DEFAULT_DURATION_MAX
    concurrent_explorations: int = DEFAULT_CONCURRENT_EXPLORATIONS

    recruitment_rate_per_hour: float = DEFAULT_RECRUITMENT_RATE_PER_HOUR
    avg_visited_places: float = DEFAULT_AVG_VISITED_PLACES
    origin_skip_rate: float = DEFAULT_ORIGIN_SKIP_RATE
    name_pool_size: int = DEFAULT_NAME_POOL_SIZE

    base_production_rate: float = DEFAULT_BASE_PRODUCTION_RATE
    tier_1_multiplier: float = DEFAULT_TIER_1_MULT
    tier_2_multiplier: float = DEFAULT_TIER_2_MULT
    tier_3_multiplier: float = DEFAULT_TIER_3_MULT
    power_consumption_rate: float = DEFAULT_POWER_CONSUMPTION_RATE
    food_consumption_per_dweller: float = DEFAULT_FOOD_CONSUMPTION_PER_DWELLER
    water_consumption_per_dweller: float = DEFAULT_WATER_CONSUMPTION_PER_DWELLER
    resource_low_threshold: float = DEFAULT_RESOURCE_LOW_THRESHOLD
    resource_critical_threshold: float = DEFAULT_RESOURCE_CRITICAL_THRESHOLD

    spawn_chance_per_hour: float = DEFAULT_SPAWN_CHANCE_PER_HOUR
    min_vault_population: int = DEFAULT_MIN_VAULT_POPULATION
    max_active_incidents: int = DEFAULT_MAX_ACTIVE_INCIDENTS
    spawn_cooldown_seconds: int = DEFAULT_SPAWN_COOLDOWN_SECONDS
    spread_duration: int = DEFAULT_SPREAD_DURATION
    max_spread_count: int = DEFAULT_MAX_SPREAD_COUNT

    conception_chance_per_tick: float = DEFAULT_CONCEPTION_CHANCE_PER_TICK
    pregnancy_duration_hours: int = DEFAULT_PREGNANCY_DURATION_HOURS
    child_growth_duration_hours: int = DEFAULT_CHILD_GROWTH_DURATION_HOURS

    def events_per_exploration(self, duration_hours: int) -> int:
        duration_seconds = duration_hours * 3600
        if duration_seconds <= self.first_event_delay:
            return 0
        return 1 + (duration_seconds - self.first_event_delay) // self.event_interval

    def get_tier_multiplier(self, tier: int) -> float:
        return {1: self.tier_1_multiplier, 2: self.tier_2_multiplier, 3: self.tier_3_multiplier}.get(tier, 1.0)


@dataclasses.dataclass
class ExplorationRun:
    start_time: int
    duration_hours: int
    events: list[dict[str, Any]] = dataclasses.field(default_factory=list)
    discoveries: int = 0
    next_event_time: int | None = None

    @property
    def end_time(self) -> int:
        return self.start_time + self.duration_hours * 3600

    def is_active(self, now: int) -> bool:
        return self.start_time <= now < self.end_time


@dataclasses.dataclass
class Incident:
    start_time: int
    difficulty: int
    spread_count: int = 0
    resolved: bool = False
    deaths: int = 0

    def elapsed(self, now: int) -> int:
        return now - self.start_time


@dataclasses.dataclass
class Pregnancy:
    start_time: int
    father_id: int
    mother_id: int

    def is_due(self, now: int, duration_hours: int) -> bool:
        return (now - self.start_time) >= duration_hours * 3600


@dataclasses.dataclass
class VaultState:
    population: int = 10
    adults: int = 8
    children: int = 2
    power: float = 80.0
    food: float = 80.0
    water: float = 80.0
    power_max: float = 100.0
    food_max: float = 100.0
    water_max: float = 100.0
    caps: int = 500
    stimpacks: int = 10
    radaways: int = 5
    happiness: float = 75.0
    incidents: list[Incident] = dataclasses.field(default_factory=list)
    pregnancies: list[Pregnancy] = dataclasses.field(default_factory=list)
    active_incidents: int = 0
    total_deaths: int = 0
    total_births: int = 0
    rooms: int = 6
    production_rooms: int = 3
    avg_special: float = 4.0


@dataclasses.dataclass
class SimulationResult:
    config: ExplorationConfig
    total_ticks: int
    total_explorations: int
    total_events: int
    total_discovery_events: int
    max_concurrent: int

    discovery_points: set[str]
    origin_points: set[str]
    visited_points: set[str]
    home_vault_points: int

    population_by_hour: list[int]
    deaths_by_hour: list[int]
    births_by_hour: list[int]
    incidents_by_hour: list[int]
    power_by_hour: list[float]
    food_by_hour: list[float]
    water_by_hour: list[float]
    happiness_by_hour: list[float]

    discoveries_by_hour: list[int]
    recruits_by_hour: list[int]

    final_population: int
    final_deaths: int
    final_births: int
    total_incidents: int
    resource_warnings: int

    discoveries_at_1h: int = 0
    discoveries_at_4h: int = 0
    discoveries_at_24h: int = 0
    discoveries_at_72h: int = 0
    total_map_points_at_1h: int = 0
    total_map_points_at_4h: int = 0
    total_map_points_at_24h: int = 0
    total_map_points_at_72h: int = 0

    @property
    def total_map_points(self) -> int:
        all_points = self.discovery_points | self.origin_points | self.visited_points
        return len(all_points) + self.home_vault_points


class VaultSimulator:
    def __init__(self, config: ExplorationConfig) -> None:
        self.cfg = config

    def _init_hourly_buckets(self, hours: int) -> dict[str, list[Any]]:
        return {
            "discoveries": [0] * hours,
            "recruits": [0] * hours,
            "population": [0] * hours,
            "deaths": [0] * hours,
            "births": [0] * hours,
            "incidents": [0] * hours,
            "power": [0.0] * hours,
            "food": [0.0] * hours,
            "water": [0.0] * hours,
            "happiness": [0.0] * hours,
        }

    def run(self, simulation_hours: int, seed: int | None = None) -> SimulationResult:
        if seed is not None:
            random.seed(seed)

        duration_seconds = simulation_hours * 3600
        ticks = duration_seconds // self.cfg.tick_interval + 1

        explorations: list[ExplorationRun] = []
        total_events = 0
        total_discovery_events = 0
        max_concurrent = 0

        discovery_points: set[str] = set()
        origin_points: set[str] = set()
        visited_points: set[str] = set()

        vault = VaultState()
        last_incident_time = -self.cfg.spawn_cooldown_seconds
        resource_warnings = 0

        buckets = self._init_hourly_buckets(simulation_hours)
        m = Milestones()

        for tick in range(ticks):
            now = tick * self.cfg.tick_interval
            hour_idx = min(now // 3600, simulation_hours - 1)

            active = [e for e in explorations if e.is_active(now)]
            max_concurrent = max(max_concurrent, len(active))
            active = self._replenish(active, now, explorations)
            tick_events, tick_discoveries = self._process_tick(active, now, discovery_points)
            total_events += tick_events
            total_discovery_events += tick_discoveries
            buckets["discoveries"][hour_idx] += tick_discoveries

            tick_recruits = self._process_recruitment()
            buckets["recruits"][hour_idx] += tick_recruits
            for _ in range(tick_recruits):
                vault.population += 1
                vault.adults += 1
                self._add_dweller_bio_places(origin_points, visited_points)

            births = self._process_breeding(vault, now)
            buckets["births"][hour_idx] += births
            vault.total_births += births

            self._process_resources(vault, now)
            buckets["power"][hour_idx] = vault.power
            buckets["food"][hour_idx] = vault.food
            buckets["water"][hour_idx] = vault.water
            buckets["happiness"][hour_idx] = vault.happiness
            buckets["population"][hour_idx] = vault.population

            new_incidents, deaths = self._process_incidents(vault, now, last_incident_time)
            if new_incidents:
                last_incident_time = now
            buckets["incidents"][hour_idx] += new_incidents
            buckets["deaths"][hour_idx] += deaths
            vault.total_deaths += deaths

            if self._has_resource_warning(vault):
                resource_warnings += 1

            m.capture(now, len(discovery_points), len(origin_points), len(visited_points))

        m.resolve_final(len(discovery_points), len(origin_points), len(visited_points))

        return SimulationResult(
            config=self.cfg,
            total_ticks=ticks,
            total_explorations=len(explorations),
            total_events=total_events,
            total_discovery_events=total_discovery_events,
            max_concurrent=max_concurrent,
            discovery_points=discovery_points,
            origin_points=origin_points,
            visited_points=visited_points,
            home_vault_points=1,
            population_by_hour=buckets["population"],
            deaths_by_hour=buckets["deaths"],
            births_by_hour=buckets["births"],
            incidents_by_hour=buckets["incidents"],
            power_by_hour=buckets["power"],
            food_by_hour=buckets["food"],
            water_by_hour=buckets["water"],
            happiness_by_hour=buckets["happiness"],
            discoveries_by_hour=buckets["discoveries"],
            recruits_by_hour=buckets["recruits"],
            final_population=vault.population,
            final_deaths=vault.total_deaths,
            final_births=vault.total_births,
            total_incidents=sum(buckets["incidents"]),
            resource_warnings=resource_warnings,
            discoveries_at_1h=m.discoveries_at_1h,
            discoveries_at_4h=m.discoveries_at_4h,
            discoveries_at_24h=m.discoveries_at_24h,
            discoveries_at_72h=m.discoveries_at_72h,
            total_map_points_at_1h=m.total_map_points_at_1h,
            total_map_points_at_4h=m.total_map_points_at_4h,
            total_map_points_at_24h=m.total_map_points_at_24h,
            total_map_points_at_72h=m.total_map_points_at_72h,
        )

    def _replenish(
        self, active: list[ExplorationRun], now: int, explorations: list[ExplorationRun]
    ) -> list[ExplorationRun]:
        while len(active) < self.cfg.concurrent_explorations:
            duration = random.randint(self.cfg.duration_min, self.cfg.duration_max)
            new_exp = ExplorationRun(start_time=now, duration_hours=duration)
            explorations.append(new_exp)
            active.append(new_exp)
        return active

    def _process_tick(self, active: list[ExplorationRun], now: int, discovery_points: set[str]) -> tuple[int, int]:
        events = 0
        discoveries = 0
        for exp in active:
            elapsed = now - exp.start_time
            if elapsed < self.cfg.first_event_delay:
                continue
            if exp.next_event_time is None:
                exp.next_event_time = exp.start_time + self.cfg.first_event_delay
            if now >= exp.next_event_time:
                events += 1
                event_type = self._roll_event()
                if event_type == "discovery":
                    exp.discoveries += 1
                    discoveries += 1
                    place = self._pick_place_name()
                    discovery_points.add(place)
                exp.next_event_time += self.cfg.event_interval
        return events, discoveries

    def _roll_event(self) -> str:
        return "discovery" if random.random() < self.cfg.discovery_chance else "other"

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

    def _add_dweller_bio_places(self, origin_points: set[str], visited_points: set[str]) -> None:
        origin_name = self._pick_place_name()
        if random.random() >= self.cfg.origin_skip_rate and origin_name not in origin_points:
            origin_points.add(origin_name)
        visited_count = self._sample_visited_count()
        for _ in range(visited_count):
            place = self._pick_place_name()
            if place != origin_name and place not in visited_points:
                visited_points.add(place)

    def _pick_place_name(self) -> str:
        return f"Place_{random.randint(1, self.cfg.name_pool_size)}"

    def _sample_visited_count(self) -> int:
        mean = self.cfg.avg_visited_places
        count = 0
        p = 1.0
        threshold = 2.718281828459045 ** (-mean)
        while True:
            p *= random.random()
            if p < threshold:
                break
            count += 1
        return min(count, 5)

    def _process_breeding(self, vault: VaultState, now: int) -> int:
        births = 0

        if vault.adults >= 2:
            eligible_pairs = min(vault.adults // 2, 5)
            for _ in range(eligible_pairs):
                if random.random() < self.cfg.conception_chance_per_tick:
                    vault.pregnancies.append(Pregnancy(start_time=now, father_id=0, mother_id=0))

        due_pregnancies = [p for p in vault.pregnancies if p.is_due(now, self.cfg.pregnancy_duration_hours)]
        for _ in due_pregnancies:
            births += 1
            vault.children += 1
            vault.population += 1
            vault.pregnancies = [p for p in vault.pregnancies if not p.is_due(now, self.cfg.pregnancy_duration_hours)]

        growth_chance = self.cfg.tick_interval / (self.cfg.child_growth_duration_hours * 3600)
        while vault.children > 0 and random.random() < growth_chance:
            vault.children -= 1
            vault.adults += 1

        return births

    def _process_resources(self, vault: VaultState, _now: int) -> None:
        seconds = self.cfg.tick_interval

        power_consumption = self.cfg.power_consumption_rate * vault.rooms * seconds * 1.5
        food_consumption = vault.population * self.cfg.food_consumption_per_dweller * seconds
        water_consumption = vault.population * self.cfg.water_consumption_per_dweller * seconds

        ability_sum = vault.adults * vault.avg_special
        tier_mult = self.cfg.get_tier_multiplier(2)
        production = vault.production_rooms * ability_sum * self.cfg.base_production_rate * tier_mult * seconds

        power_production = production * 0.4
        food_production = production * 0.3
        water_production = production * 0.3

        if vault.power <= 0:
            power_production = production * 0.8
            food_production = 0
            water_production = 0

        vault.power = max(0, min(vault.power - power_consumption + power_production, vault.power_max))
        vault.food = max(0, min(vault.food - food_consumption + food_production, vault.food_max))
        vault.water = max(0, min(vault.water - water_consumption + water_production, vault.water_max))

        happiness_delta = -0.5
        if vault.food < vault.food_max * self.cfg.resource_low_threshold:
            happiness_delta -= 2.0
        if vault.water < vault.water_max * self.cfg.resource_low_threshold:
            happiness_delta -= 2.0
        if vault.power < vault.power_max * self.cfg.resource_low_threshold:
            happiness_delta -= 1.0
        if vault.adults > 0:
            happiness_delta += 0.3
        vault.happiness = max(0, min(100, vault.happiness + happiness_delta))

    def _resolve_incident(self, vault: VaultState, incident: Incident, now: int, deaths_ref: list[int]) -> bool:
        elapsed = incident.elapsed(now)
        if elapsed >= self.cfg.spread_duration:
            if incident.spread_count < self.cfg.max_spread_count:
                incident.spread_count += 1
                vault.happiness -= 3.0
            else:
                incident.resolved = True
                vault.caps += incident.difficulty * 20
                return False

        if vault.adults > 0:
            dweller_power = vault.adults * vault.avg_special * 0.5
            raider_power = incident.difficulty * 10
            if dweller_power > raider_power:
                incident.resolved = True
                vault.caps += incident.difficulty * 20
                return False
            damage = max(1, int((raider_power - dweller_power) * 0.1))
            death_chance = min(0.3, damage / (vault.population * 10))
            if random.random() < death_chance and vault.adults > 0:
                deaths_ref[0] += 1
                vault.adults -= 1
                vault.population -= 1
                vault.total_deaths += 1
            return True

        if incident.spread_count < self.cfg.max_spread_count:
            incident.spread_count += 1
        return True

    def _process_incidents(self, vault: VaultState, now: int, last_incident_time: int) -> tuple[int, int]:
        new_incidents = 0
        deaths = 0
        deaths_ref = [deaths]

        if vault.population < self.cfg.min_vault_population:
            return 0, 0

        active_incidents = []
        for incident in vault.incidents:
            if incident.resolved:
                continue
            if self._resolve_incident(vault, incident, now, deaths_ref):
                active_incidents.append(incident)

        vault.incidents = active_incidents
        vault.active_incidents = len(active_incidents)

        if vault.active_incidents < self.cfg.max_active_incidents:
            seconds_since_last = now - last_incident_time
            if seconds_since_last >= self.cfg.spawn_cooldown_seconds:
                hours_passed = min(self.cfg.tick_interval / 3600, 2.0)
                spawn_chance = self.cfg.spawn_chance_per_hour * hours_passed
                if random.random() < spawn_chance:
                    difficulty = random.choices(range(1, 11), weights=[5, 10, 15, 20, 20, 15, 10, 3, 1, 1], k=1)[0]
                    vault.incidents.append(Incident(start_time=now, difficulty=difficulty))
                    new_incidents = 1
                    vault.happiness -= 5.0

        return new_incidents, deaths_ref[0]

    def _has_resource_warning(self, vault: VaultState) -> bool:
        checks = [
            (vault.power, vault.power_max),
            (vault.food, vault.food_max),
            (vault.water, vault.water_max),
        ]
        for resource, max_val in checks:
            if resource < max_val * self.cfg.resource_critical_threshold:
                return True
            if resource < max_val * self.cfg.resource_low_threshold:
                return True
        return False


@dataclasses.dataclass
class Milestones:
    discoveries_at_1h: int = 0
    discoveries_at_4h: int = 0
    discoveries_at_24h: int = 0
    discoveries_at_72h: int = 0
    total_map_points_at_1h: int = 0
    total_map_points_at_4h: int = 0
    total_map_points_at_24h: int = 0
    total_map_points_at_72h: int = 0

    def capture(self, now: int, discoveries: int, origins: int, visited: int) -> None:
        total = discoveries + origins + visited + 1
        if now == 3600:
            self.discoveries_at_1h = discoveries
            self.total_map_points_at_1h = total
        elif now == 4 * 3600:
            self.discoveries_at_4h = discoveries
            self.total_map_points_at_4h = total
        elif now == 24 * 3600:
            self.discoveries_at_24h = discoveries
            self.total_map_points_at_24h = total
        elif now == 72 * 3600:
            self.discoveries_at_72h = discoveries
            self.total_map_points_at_72h = total

    def resolve_final(self, discoveries: int, origins: int, visited: int) -> None:
        total = discoveries + origins + visited + 1
        if self.discoveries_at_1h == 0:
            self.discoveries_at_1h = discoveries
            self.total_map_points_at_1h = total
        if self.discoveries_at_4h == 0:
            self.discoveries_at_4h = discoveries
            self.total_map_points_at_4h = total
        if self.discoveries_at_24h == 0:
            self.discoveries_at_24h = discoveries
            self.total_map_points_at_24h = total
        if self.discoveries_at_72h == 0:
            self.discoveries_at_72h = discoveries
            self.total_map_points_at_72h = total


BatchResult = dict[str, Any]


@dataclasses.dataclass
class _Aggregates:
    discoveries: list[int] = dataclasses.field(default_factory=list)
    explorations: list[int] = dataclasses.field(default_factory=list)
    total_map_points: list[int] = dataclasses.field(default_factory=list)
    discovery_points: list[int] = dataclasses.field(default_factory=list)
    origin_points: list[int] = dataclasses.field(default_factory=list)
    visited_points: list[int] = dataclasses.field(default_factory=list)
    recruits: list[int] = dataclasses.field(default_factory=list)
    final_pop: list[int] = dataclasses.field(default_factory=list)
    final_deaths: list[int] = dataclasses.field(default_factory=list)
    final_births: list[int] = dataclasses.field(default_factory=list)
    total_incidents: list[int] = dataclasses.field(default_factory=list)
    resource_warnings: list[int] = dataclasses.field(default_factory=list)
    final_power: list[float] = dataclasses.field(default_factory=list)
    final_food: list[float] = dataclasses.field(default_factory=list)
    final_water: list[float] = dataclasses.field(default_factory=list)
    final_happiness: list[float] = dataclasses.field(default_factory=list)

    def collect(self, result: SimulationResult) -> None:
        self.discoveries.append(result.total_discovery_events)
        self.explorations.append(result.total_explorations)
        self.total_map_points.append(result.total_map_points)
        self.discovery_points.append(len(result.discovery_points))
        self.origin_points.append(len(result.origin_points))
        self.visited_points.append(len(result.visited_points))
        self.recruits.append(sum(result.recruits_by_hour))
        self.final_pop.append(result.final_population)
        self.final_deaths.append(result.final_deaths)
        self.final_births.append(result.final_births)
        self.total_incidents.append(result.total_incidents)
        self.resource_warnings.append(result.resource_warnings)
        self.final_power.append(result.power_by_hour[-1] if result.power_by_hour else 0)
        self.final_food.append(result.food_by_hour[-1] if result.food_by_hour else 0)
        self.final_water.append(result.water_by_hour[-1] if result.water_by_hour else 0)
        self.final_happiness.append(result.happiness_by_hour[-1] if result.happiness_by_hour else 0)


@dataclasses.dataclass
class _Curves:
    cumulative: list[float] = dataclasses.field(default_factory=list)
    total_map: list[float] = dataclasses.field(default_factory=list)
    pop: list[float] = dataclasses.field(default_factory=list)
    death: list[float] = dataclasses.field(default_factory=list)
    incident: list[float] = dataclasses.field(default_factory=list)
    power: list[float] = dataclasses.field(default_factory=list)
    food: list[float] = dataclasses.field(default_factory=list)
    water: list[float] = dataclasses.field(default_factory=list)
    happiness: list[float] = dataclasses.field(default_factory=list)

    @classmethod
    def zeroed(cls, hours: int) -> _Curves:
        return cls(**{k: [0.0] * hours for k in dataclasses.asdict(cls())})

    def add_result(self, result: SimulationResult, hours: int) -> None:
        for h in range(hours):
            self.cumulative[h] += result.discoveries_by_hour[h]
            self.total_map[h] += result.total_map_points
            self.pop[h] += result.population_by_hour[h]
            self.death[h] += result.deaths_by_hour[h]
            self.incident[h] += result.incidents_by_hour[h]
            self.power[h] += result.power_by_hour[h]
            self.food[h] += result.food_by_hour[h]
            self.water[h] += result.water_by_hour[h]
            self.happiness[h] += result.happiness_by_hour[h]

    def divide(self, divisor: int) -> None:
        for k in dataclasses.asdict(self):
            arr = getattr(self, k)
            for i in range(len(arr)):
                arr[i] /= divisor


@dataclasses.dataclass
class _MilestoneLists:
    discoveries_1h: list[int] = dataclasses.field(default_factory=list)
    discoveries_4h: list[int] = dataclasses.field(default_factory=list)
    discoveries_24h: list[int] = dataclasses.field(default_factory=list)
    discoveries_72h: list[int] = dataclasses.field(default_factory=list)
    total_map_1h: list[int] = dataclasses.field(default_factory=list)
    total_map_4h: list[int] = dataclasses.field(default_factory=list)
    total_map_24h: list[int] = dataclasses.field(default_factory=list)
    total_map_72h: list[int] = dataclasses.field(default_factory=list)

    def collect(self, result: SimulationResult) -> None:
        self.discoveries_1h.append(result.discoveries_at_1h)
        self.discoveries_4h.append(result.discoveries_at_4h)
        self.discoveries_24h.append(result.discoveries_at_24h)
        self.discoveries_72h.append(result.discoveries_at_72h)
        self.total_map_1h.append(result.total_map_points_at_1h)
        self.total_map_4h.append(result.total_map_points_at_4h)
        self.total_map_24h.append(result.total_map_points_at_24h)
        self.total_map_72h.append(result.total_map_points_at_72h)


def stats(values: list[int] | list[float]) -> dict[str, float]:
    return {
        "mean": statistics.mean(values),
        "median": statistics.median(values),
        "stdev": statistics.stdev(values) if len(values) > 1 else 0.0,
        "min": min(values),
        "max": max(values),
    }


def run_monte_carlo(config: ExplorationConfig, simulation_hours: int, runs: int) -> BatchResult:
    sim = VaultSimulator(config)
    ag = _Aggregates()
    curves = _Curves.zeroed(simulation_hours)
    milestones = _MilestoneLists()

    for i in range(runs):
        result = sim.run(simulation_hours, seed=i)
        ag.collect(result)
        curves.add_result(result, simulation_hours)
        milestones.collect(result)

    curves.divide(runs)

    return {
        "config": config,
        "runs": runs,
        "simulation_hours": simulation_hours,
        "discoveries": stats(ag.discoveries),
        "explorations": stats(ag.explorations),
        "recruits": stats(ag.recruits),
        "discovery_points": stats(ag.discovery_points),
        "origin_points": stats(ag.origin_points),
        "visited_points": stats(ag.visited_points),
        "total_map_points": stats(ag.total_map_points),
        "population": stats(ag.final_pop),
        "deaths": stats(ag.final_deaths),
        "births": stats(ag.final_births),
        "incidents": stats(ag.total_incidents),
        "resource_warnings": stats(ag.resource_warnings),
        "final_power": stats(ag.final_power),
        "final_food": stats(ag.final_food),
        "final_water": stats(ag.final_water),
        "final_happiness": stats(ag.final_happiness),
        "milestones": {
            "1h": {"discoveries": stats(milestones.discoveries_1h), "total_map": stats(milestones.total_map_1h)},
            "4h": {"discoveries": stats(milestones.discoveries_4h), "total_map": stats(milestones.total_map_4h)},
            "24h": {"discoveries": stats(milestones.discoveries_24h), "total_map": stats(milestones.total_map_24h)},
            "72h": {"discoveries": stats(milestones.discoveries_72h), "total_map": stats(milestones.total_map_72h)},
        },
        "cumulative_curve": curves.cumulative,
        "total_map_curve": curves.total_map,
        "pop_curve": curves.pop,
        "death_curve": curves.death,
        "incident_curve": curves.incident,
        "power_curve": curves.power,
        "food_curve": curves.food,
        "water_curve": curves.water,
        "happiness_curve": curves.happiness,
    }


SWEEP_RANGES: dict[str, list[Any]] = {
    "discovery_chance": [0.05, 0.08, 0.10, 0.12, 0.15, 0.20, 0.25],
    "event_interval": [300, 450, 600, 900, 1200],
    "first_event_delay": [60, 180, 300, 600, 900],
    "concurrent_explorations": [1, 2, 3, 4, 5],
    "recruitment_rate_per_hour": [0.0, 1 / 12, 1 / 6, 1 / 3, 0.5, 1.0],
    "avg_visited_places": [0.0, 0.5, 1.0, 1.5, 2.0, 3.0],
    "spawn_chance_per_hour": [0.0, 0.02, 0.05, 0.08, 0.10, 0.15],
    "conception_chance_per_tick": [0.0, 0.10, 0.20, 0.30, 0.50],
    "base_production_rate": [0.05, 0.08, 0.10, 0.15, 0.20],
}


def run_parameter_sweep(
    param_name: str, baseline: ExplorationConfig, simulation_hours: int, runs: int
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


def _print_params(cfg: ExplorationConfig) -> None:
    print("Parameters:")
    print(f"  tick_interval       = {cfg.tick_interval}s")
    print(f"  event_interval      = {cfg.event_interval}s ({cfg.event_interval / 60:.0f} min)")
    print(f"  first_event_delay   = {cfg.first_event_delay}s ({cfg.first_event_delay / 60:.0f} min)")
    print(f"  discovery_chance    = {cfg.discovery_chance:.0%}")
    print(f"  duration_range      = {cfg.duration_min}h - {cfg.duration_max}h")
    print(f"  concurrent_exps     = {cfg.concurrent_explorations}")
    print(f"  recruitment_rate    = {cfg.recruitment_rate_per_hour:.3f}/hour")
    print(f"  avg_visited_places  = {cfg.avg_visited_places:.1f}")
    print(f"  spawn_chance        = {cfg.spawn_chance_per_hour:.2%}/hour")
    print(f"  conception_chance   = {cfg.conception_chance_per_tick:.0%}/tick")
    print(f"  base_production     = {cfg.base_production_rate:.2f}")
    print()


def _print_theoretical(cfg: ExplorationConfig) -> None:
    theoretical = cfg.events_per_exploration(cfg.duration_max) * cfg.discovery_chance
    print("Theoretical max per exploration:")
    print(f"  events_per_exp (max duration) = {cfg.events_per_exploration(cfg.duration_max)}")
    print(f"  expected discoveries per exp    = {theoretical:.2f}")
    print()


def _print_aggregate_results(batch: BatchResult) -> None:
    print("Aggregate results:")
    print(f"  explorations launched : {fmt_stats(batch['explorations'])}")
    print(f"  radio recruits        : {fmt_stats(batch['recruits'])}")
    print()


def _print_map_points(batch: BatchResult) -> None:
    print("Map point sources:")
    print(f"  DISCOVERY (exploration) : {fmt_stats(batch['discovery_points'])}")
    print(f"  ORIGIN   (birthplace)   : {fmt_stats(batch['origin_points'])}")
    print(f"  VISITED  (dweller bios) : {fmt_stats(batch['visited_points'])}")
    print("  HOME_VAULT              : 1 (fixed)")
    print("  ----------------------------------------")
    print(f"  TOTAL unique map points : {fmt_stats(batch['total_map_points'])}")
    print()


def _print_vault_lifecycle(batch: BatchResult) -> None:
    print("Vault lifecycle:")
    print(f"  final population    : {fmt_stats(batch['population'])}")
    print(f"  total deaths        : {fmt_stats(batch['deaths'])}")
    print(f"  total births        : {fmt_stats(batch['births'])}")
    print(f"  total incidents     : {fmt_stats(batch['incidents'])}")
    print(f"  resource warnings   : {fmt_stats(batch['resource_warnings'])}")
    print()


def _print_final_resources(batch: BatchResult) -> None:
    print("Final resource state:")
    print(f"  power     : {fmt_stats(batch['final_power'])}")
    print(f"  food      : {fmt_stats(batch['final_food'])}")
    print(f"  water     : {fmt_stats(batch['final_water'])}")
    print(f"  happiness : {fmt_stats(batch['final_happiness'])}")
    print()


def _print_milestones(batch: BatchResult, hours: int) -> None:
    print("Milestone discoveries & total map points:")
    for label, key in [("1h", "1h"), ("4h", "4h"), ("24h", "24h"), ("72h", "72h")]:
        if hours >= int(label[:-1]):
            d = batch["milestones"][key]["discoveries"]
            t = batch["milestones"][key]["total_map"]
            print(f"  at {label:4} : DISCOVERY={d['mean']:.0f}  TOTAL_MAP={t['mean']:.0f}")
    print()


def _print_hourly_curves(batch: BatchResult, hours: int) -> None:
    if hours > 24:
        return
    print("Hourly curves (average per run):")
    print("  hour | POP | DEATHS | INCIDENTS | POWER | FOOD | WATER | HAPPY")
    print("  " + "-" * 65)
    for h in range(hours):
        p = batch["pop_curve"][h]
        d = batch["death_curve"][h]
        i = batch["incident_curve"][h]
        pw = batch["power_curve"][h]
        f = batch["food_curve"][h]
        w = batch["water_curve"][h]
        hp = batch["happiness_curve"][h]
        print(f"  {h:4} | {p:3.0f} | {d:6.1f} | {i:9.1f} | {pw:5.0f} | {f:4.0f} | {w:5.0f} | {hp:5.1f}")
    print()


def _print_balance_assessment(batch: BatchResult, hours: int) -> None:
    mean_discoveries = batch["discoveries"]["mean"]
    mean_total = batch["total_map_points"]["mean"]
    rate = mean_discoveries / hours if hours > 0 else 0
    total_rate = mean_total / hours if hours > 0 else 0
    mean_pop = batch["population"]["mean"]
    mean_deaths = batch["deaths"]["mean"]

    print("Balance assessment:")
    if rate < 0.3:
        advice = "Consider increasing discovery_chance or reducing event_interval."
        print(f"  Discovery rate={rate:.2f}/hour — VERY SLOW. {advice}")
    elif rate < 0.8:
        print(f"  Discovery rate={rate:.2f}/hour — MODERATE. Good for slow-burn games.")
    elif rate < 2.0:
        print(f"  Discovery rate={rate:.2f}/hour — HEALTHY. Fits active exploration games.")
    else:
        advice = "Map may saturate quickly; consider reducing discovery_chance."
        print(f"  Discovery rate={rate:.2f}/hour — FAST. {advice}")
    print(f"  Total map growth={total_rate:.2f} points/hour (all sources)")
    print(f"  Population change: +{mean_pop - 10:.0f} net over {hours}h (deaths={mean_deaths:.1f})")
    print()


def print_report(batch: BatchResult, detailed: bool = False) -> None:
    cfg: ExplorationConfig = batch["config"]
    hours = batch["simulation_hours"]
    runs = batch["runs"]

    print()
    print(banner(f"Simulation: {hours}h x {runs} runs"))
    print()
    _print_params(cfg)
    _print_theoretical(cfg)
    _print_aggregate_results(batch)
    _print_map_points(batch)
    _print_vault_lifecycle(batch)
    _print_final_resources(batch)
    _print_milestones(batch, hours)
    if detailed:
        _print_hourly_curves(batch, hours)
    _print_balance_assessment(batch, hours)


def print_sweep_report(results: list[BatchResult], param_name: str) -> None:
    print()
    print(banner(f"Parameter sweep: {param_name}"))
    print()
    print(
        f"{'Value':>12} | {'D/h':>5} | {'T/h':>5} | {'Pop':>5} | {'Death':>5} | {'Inc':>5} | "
        f"{'Power':>5} | {'Food':>5} | {'Water':>5} | {'Happy':>5} | Verdict"
    )
    print("-" * TERMINAL_WIDTH)

    for r in results:
        cfg: ExplorationConfig = r["config"]
        value = getattr(cfg, param_name)
        hours = r["simulation_hours"]
        d_mean = r["discoveries"]["mean"]
        rate = d_mean / hours if hours > 0 else 0
        total_rate = r["total_map_points"]["mean"] / hours if hours > 0 else 0
        pop = r["population"]["mean"]
        deaths = r["deaths"]["mean"]
        incidents = r["incidents"]["mean"]
        power = r["final_power"]["mean"]
        food = r["final_food"]["mean"]
        water = r["final_water"]["mean"]
        happy = r["final_happiness"]["mean"]

        if rate < 0.3:
            verdict = "slow"
        elif rate < 0.8:
            verdict = "moderate"
        elif rate < 2.0:
            verdict = "healthy"
        else:
            verdict = "fast"

        vstr = f"{value:.2f}" if isinstance(value, float) else str(value)
        print(
            f"{vstr:>12} | {rate:>5.2f} | {total_rate:>5.2f} | {pop:>5.0f} | {deaths:>5.1f} | {incidents:>5.1f} | "
            f"{power:>5.0f} | {food:>5.0f} | {water:>5.0f} | {happy:>5.1f} | {verdict}"
        )
    print()


app = typer.Typer(help="Simulate vault balance for the Fallout Shelter game.")


@app.command()
def simulate(
    days: Annotated[int, typer.Option(help="Simulation length in days")] = DEFAULT_SIMULATION_DAYS,
    runs: Annotated[int, typer.Option(help="Monte Carlo runs (higher = smoother)")] = DEFAULT_RUNS,
    sweep: Annotated[str | None, typer.Option(help="Parameter to sweep")] = None,
    tick_interval: Annotated[int, typer.Option()] = DEFAULT_TICK_INTERVAL,
    event_interval: Annotated[int, typer.Option()] = DEFAULT_EVENT_INTERVAL,
    first_event_delay: Annotated[int, typer.Option()] = DEFAULT_FIRST_EVENT_DELAY,
    discovery_chance: Annotated[float, typer.Option()] = DEFAULT_DISCOVERY_CHANCE,
    duration_min: Annotated[int, typer.Option()] = DEFAULT_DURATION_MIN,
    duration_max: Annotated[int, typer.Option()] = DEFAULT_DURATION_MAX,
    concurrent: Annotated[int, typer.Option()] = DEFAULT_CONCURRENT_EXPLORATIONS,
    recruitment_rate: Annotated[float, typer.Option()] = DEFAULT_RECRUITMENT_RATE_PER_HOUR,
    avg_visited: Annotated[float, typer.Option()] = DEFAULT_AVG_VISITED_PLACES,
    spawn_chance: Annotated[float, typer.Option()] = DEFAULT_SPAWN_CHANCE_PER_HOUR,
    conception_chance: Annotated[float, typer.Option()] = DEFAULT_CONCEPTION_CHANCE_PER_TICK,
    production_rate: Annotated[float, typer.Option()] = DEFAULT_BASE_PRODUCTION_RATE,
    detailed: Annotated[bool, typer.Option(help="Show hourly cumulative curves")] = False,
    seed: Annotated[int | None, typer.Option(help="Fix random seed for reproducibility")] = None,
) -> None:
    hours = days * 24

    baseline = ExplorationConfig(
        tick_interval=tick_interval,
        event_interval=event_interval,
        first_event_delay=first_event_delay,
        discovery_chance=discovery_chance,
        duration_min=duration_min,
        duration_max=duration_max,
        concurrent_explorations=concurrent,
        recruitment_rate_per_hour=recruitment_rate,
        avg_visited_places=avg_visited,
        spawn_chance_per_hour=spawn_chance,
        conception_chance_per_tick=conception_chance,
        base_production_rate=production_rate,
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
