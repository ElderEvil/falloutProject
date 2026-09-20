"""Objective evaluators that automatically track progress via EventBus subscriptions.

This is a package now: the ABC + session machinery live in ``base``, the concrete
evaluators in ``concrete``, and the manager in ``manager``. The public surface is
re-exported here so ``from app.services.progression.objectives.evaluators import X``
keeps working.

Mutable module state — ``current_session_maker`` / ``set_current_session_maker`` and
the ``async_session_maker`` patch point — lives in ``base``. Tests monkeypatch
``app.services.progression.objectives.evaluators.base.async_session_maker``, not this
package's re-export; patching here would not forward.
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
    LevelUpEvaluator,
    ReachEvaluator,
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
