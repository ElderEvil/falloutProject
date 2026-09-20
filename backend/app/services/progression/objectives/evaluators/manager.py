"""Objective evaluator registration and lifecycle."""

import logging

from app.core.event_bus import EventBus, event_bus
from app.services.progression.objectives.evaluators.base import ObjectiveEvaluator
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

logger = logging.getLogger(__name__)


class ObjectiveEvaluatorManager:
    """Manages all objective evaluators, initializing them with the event bus.

    Provides a centralized point for registration/unregistration of evaluators.
    Use the module-level `evaluator_manager` singleton instance.
    """

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        self._evaluators: list[ObjectiveEvaluator] = []
        self._initialized = False

    def initialize(self) -> None:
        if self._initialized:
            logger.debug("ObjectiveEvaluatorManager already initialized, skipping")
            return

        evaluator_classes: list[type[ObjectiveEvaluator]] = [
            CollectEvaluator,
            BuildEvaluator,
            TrainEvaluator,
            AssignEvaluator,
            AssignCorrectEvaluator,
            ReachEvaluator,
            ExpeditionEvaluator,
            LevelUpEvaluator,
        ]

        for cls in evaluator_classes:
            evaluator = cls(self._event_bus)
            self._evaluators.append(evaluator)
            logger.info(f"[INIT] Registered {cls.__name__} for '{cls.objective_type}' objectives")
            logger.debug(f"[INIT] Subscribed to events: {cls.subscribed_events}")

        self._initialized = True
        logger.info(f"ObjectiveEvaluatorManager initialized with {len(self._evaluators)} evaluator(s)")

    def shutdown(self) -> None:
        for evaluator in self._evaluators:
            evaluator.unsubscribe()
            logger.debug(f"Unregistered {evaluator.__class__.__name__}")

        self._evaluators.clear()
        self._initialized = False
        logger.info("ObjectiveEvaluatorManager shut down")

    @property
    def evaluators(self) -> list[ObjectiveEvaluator]:
        return list(self._evaluators)

    @property
    def is_initialized(self) -> bool:
        return self._initialized


evaluator_manager = ObjectiveEvaluatorManager(event_bus)
