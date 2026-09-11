"""Internal result shapes for tick phases.

These are working contracts between tick collaborators, not wire schemas:
every field is optional (error keys appear only on failure paths) so assembly
code can build results incrementally. ``ty`` checks every key read and write;
tests keep subscripting unchanged.
"""

from typing import Any, TypedDict


class ExplorationStats(TypedDict, total=False):
    active_count: int
    events_generated: int
    completed: int
    error: str


class WorkXpStats(TypedDict, total=False):
    xp_awarded: int
    leveled_up: int


class DwellersStats(TypedDict, total=False):
    health_updated: int
    leveled_up: int
    xp_awarded: int
    deaths: int
    irradiated: int


class ApprenticeStats(TypedDict, total=False):
    active_count: int
    stats_awarded: int


class TrainingStats(TypedDict, total=False):
    sessions_updated: int
    completed: int
    active_count: int
    error: str


class EventsStats(TypedDict, total=False):
    triggered: int
    events: list[dict[str, Any]]


class RelationshipsStats(TypedDict, total=False):
    relationships_updated: int


class PregnancyStats(TypedDict, total=False):
    conceptions: int
    births: int


class AgeStats(TypedDict, total=False):
    children_aged: int


class BreedingStats(TypedDict, total=False):
    relationships_updated: int
    conceptions: int
    births: int
    children_aged: int


class ResourcesStats(TypedDict, total=False):
    power: float
    food: float
    water: float
    events: dict[str, Any]
    error: str


class TickUpdates(TypedDict, total=False):
    resources: ResourcesStats
    explorations: ExplorationStats
    dwellers: DwellersStats
    apprenticeships: ApprenticeStats
    training: TrainingStats
    happiness: dict[str, Any]
    breeding: BreedingStats
    events: EventsStats


class VaultTickResult(TypedDict, total=False):
    vault_id: str
    seconds_passed: int
    updates: TickUpdates
    status: str


class GameTickResult(TypedDict, total=False):
    vaults_processed: int
    vaults_skipped: int
    errors: int
    total_time: float
