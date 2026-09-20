"""Compatibility facade — canonical implementation: ``app.services.progression.objectives.evaluators``.

This is a named-export re-export only. Code that mutates the module — monkeypatching
``async_session_maker`` or ``current_session_maker`` for tests, or anything that must
change the module's own globals — must target the canonical module
``app.services.progression.objectives.evaluators``; mutations made here do not forward.
"""

from app.services.progression.objectives.evaluators import (
    AssignCorrectEvaluator,
    AssignEvaluator,
    BuildEvaluator,
    CollectEvaluator,
    ExpeditionEvaluator,
    LevelUpEvaluator,
    ObjectiveEvaluator,
    ObjectiveEvaluatorManager,
    ReachEvaluator,
    TrainEvaluator,
    async_session_maker,
    current_session_maker,
    evaluator_manager,
    set_current_session_maker,
)

__all__ = [
    "AssignCorrectEvaluator",
    "AssignEvaluator",
    "BuildEvaluator",
    "CollectEvaluator",
    "ExpeditionEvaluator",
    "LevelUpEvaluator",
    "ObjectiveEvaluator",
    "ObjectiveEvaluatorManager",
    "ReachEvaluator",
    "TrainEvaluator",
    "async_session_maker",
    "current_session_maker",
    "evaluator_manager",
    "set_current_session_maker",
]
