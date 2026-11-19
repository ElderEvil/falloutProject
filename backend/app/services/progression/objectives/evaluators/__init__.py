"""Objective evaluators tracking progress via EventBus subscriptions; re-exports keep the public import surface.

Mutable state (current_session_maker, async_session_maker patch point) lives in base: tests must monkeypatch
...evaluators.base.async_session_maker — patching this package's re-export would not forward.
"""

from app.services.progression.objectives.evaluators.base import (
    ObjectiveEvaluator,
    async_session_maker,
    current_session_maker,
    set_current_session_maker,
)
from app.services.progression.objectives.evaluators.concrete import (
    AssignCorrectEvaluator,
    AssignEvaluator,
    BuildEvaluator,
    CollectEvaluator,
    ExpeditionEvaluator,
    ExploreEvaluator,
    LevelUpEvaluator,
    ReachEvaluator,
    ScrapEvaluator,
    TrainEvaluator,
)
from app.services.progression.objectives.evaluators.manager import (
    ObjectiveEvaluatorManager,
    evaluator_manager,
)

__all__ = [
    "AssignCorrectEvaluator",
    "AssignEvaluator",
    "BuildEvaluator",
    "CollectEvaluator",
    "ExpeditionEvaluator",
    "ExploreEvaluator",
    "LevelUpEvaluator",
    "ObjectiveEvaluator",
    "ObjectiveEvaluatorManager",
    "ReachEvaluator",
    "ScrapEvaluator",
    "TrainEvaluator",
    "async_session_maker",
    "current_session_maker",
    "evaluator_manager",
    "set_current_session_maker",
]
