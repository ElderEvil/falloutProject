"""Objective evaluators that automatically track progress via EventBus subscriptions.

Each evaluator listens for specific game events, finds matching active objectives
for the vault, updates progress, and auto-completes when the target is reached.

Example flow:
    Player collects 100 caps
    -> Game code emits RESOURCE_COLLECTED event
    -> CollectEvaluator receives event
    -> Finds "Collect 100 Caps" objective for vault
    -> Updates progress: 50 -> 100
    -> Auto-completes and grants reward
"""

import abc
import logging
from typing import Any

from pydantic import UUID4
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.db.session import async_session_maker
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.event_bus import EventBus, GameEvent, event_bus
from app.utils.objective_constants import (
    normalize_item_type,
    normalize_resource_type,
    normalize_room_type,
)

logger = logging.getLogger(__name__)


class ObjectiveEvaluator(abc.ABC):
    """Base class for objective evaluators.

    Each evaluator handles a specific objective_type (e.g. "collect", "build")
    by subscribing to relevant GameEvent types and updating progress when
    matching events are emitted.
    """

    objective_type: str
    subscribed_events: list[GameEvent]

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        for event_type in self.subscribed_events:
            self._event_bus.subscribe(event_type, self._handle_event)

    def unsubscribe(self) -> None:
        for event_type in self.subscribed_events:
            self._event_bus.unsubscribe(event_type, self._handle_event)

    async def _handle_event(self, event_type: str, vault_id: UUID4, data: dict[str, Any]) -> None:
        logger.debug(f"[DEBUG] {self.__class__.__name__} received {event_type} for vault {vault_id} with data: {data}")
        async with async_session_maker() as db_session:
            objectives = await self._get_active_objectives(db_session, vault_id)
            for objective, link in objectives:
                try:
                    if self._matches(objective, event_type, data):
                        logger.debug(f"[DEBUG] MATCH: Objective '{objective.challenge}' matches {event_type}")
                        amount = self._extract_amount(data)
                        await self._update_progress(db_session, vault_id, objective, link, amount)
                    else:
                        logger.debug(f"[DEBUG] NO MATCH: Objective '{objective.challenge}' does not match {event_type}")
                except Exception:
                    logger.exception(
                        f"{self.__class__.__name__} failed handling objective '{objective.challenge}' "
                        f"(id={objective.id}) for vault {vault_id} on event {event_type}"
                    )

    async def _get_active_objectives(
        self, db_session: AsyncSession, vault_id: UUID4
    ) -> list[tuple[Objective, VaultObjectiveProgressLink]]:
        query = (
            select(Objective, VaultObjectiveProgressLink)
            .join(VaultObjectiveProgressLink)
            .where(
                VaultObjectiveProgressLink.vault_id == vault_id,
                VaultObjectiveProgressLink.is_completed.is_(False),
                Objective.objective_type == self.objective_type,
            )
        )
        result = await db_session.execute(query)
        objectives = list(result.all())
        logger.debug(f"Found {len(objectives)} active '{self.objective_type}' objectives for vault {vault_id}")
        return objectives

    @abc.abstractmethod
    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        """Return True if this event data matches the objective's target_entity criteria."""

    def _extract_amount(self, data: dict[str, Any]) -> int:
        return data.get("amount", 1)

    async def _update_progress(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        objective: Objective,
        link: VaultObjectiveProgressLink,
        amount: int,
    ) -> None:
        old_progress = link.progress
        link.progress = min(link.progress + amount, objective.target_amount)
        link.total = objective.target_amount

        logger.info(
            f"Objective '{objective.challenge}' progress for vault {vault_id}: "
            f"{old_progress} -> {link.progress}/{objective.target_amount}"
        )

        if link.progress >= objective.target_amount:
            await self._auto_complete(db_session, vault_id, objective, link)
        else:
            await db_session.commit()

    async def _auto_complete(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        objective: Objective,
        link: VaultObjectiveProgressLink,
    ) -> None:
        """Auto-complete objective and grant reward in single transaction."""
        from app.services.reward_service import reward_service

        # Set completion flags
        link.is_completed = True
        link.progress = objective.target_amount

        # Emit event
        await self._event_bus.emit(
            GameEvent.OBJECTIVE_COMPLETED,
            vault_id,
            {"objective_id": str(objective.id), "challenge": objective.challenge},
        )

        # Grant reward - wrapped in try/except so completion isn't lost on reward failure
        try:
            await reward_service.process_objective_reward(db_session, vault_id, link)
            logger.info(f"Objective '{objective.challenge}' auto-completed and reward granted for vault {vault_id}")
        except Exception:
            logger.exception(f"Failed to grant reward for objective '{objective.challenge}' in vault {vault_id}")

        await db_session.commit()


class CollectEvaluator(ObjectiveEvaluator):
    """Evaluates 'collect' objectives (e.g. 'Collect 100 Caps', 'Collect 500 Food').

    Listens to RESOURCE_COLLECTED and ITEM_COLLECTED events.
    Matches on target_entity["resource_type"] or target_entity["item_type"].
    """

    objective_type = "collect"
    subscribed_events = [GameEvent.RESOURCE_COLLECTED, GameEvent.ITEM_COLLECTED]

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        target = objective.target_entity or {}

        if event_type == GameEvent.RESOURCE_COLLECTED:
            target_resource = target.get("resource_type")
            # Wildcard matches any resource ("*", "any", or null)
            if not target_resource or target_resource in ("*", "any"):
                return True
            # Use normalize_resource_type to handle aliases (e.g., "Caps" -> "caps")
            event_resource = normalize_resource_type(data.get("resource_type", ""))
            target_normalized = normalize_resource_type(target_resource)
            return event_resource == target_normalized

        if event_type == GameEvent.ITEM_COLLECTED:
            target_item = target.get("item_type")
            # Wildcard matches any item ("*", "any", or null)
            if not target_item or target_item in ("*", "any"):
                return True
            # Use normalize_item_type to handle aliases (e.g., "Weapons" -> "weapon")
            event_item = normalize_item_type(data.get("item_type", ""))
            target_normalized = normalize_item_type(target_item)
            return event_item == target_normalized

        return False

    def _extract_amount(self, data: dict[str, Any]) -> int:
        return data.get("amount", 1)


class BuildEvaluator(ObjectiveEvaluator):
    """Evaluates 'build' objectives (e.g. 'Build 3 Rooms', 'Build a Living Quarter').

    Listens to ROOM_BUILT and ROOM_UPGRADED events.
    Matches on target_entity["room_type"]. If room_type is absent or "*", matches any room.
    """

    objective_type = "build"
    subscribed_events = [GameEvent.ROOM_BUILT, GameEvent.ROOM_UPGRADED]

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:  # noqa: ARG002
        target = objective.target_entity or {}
        target_room_type = target.get("room_type")

        # Wildcard matches any room ("*", "any", or null)
        if not target_room_type or target_room_type in ("*", "any"):
            return True

        # Use normalize_room_type to handle aliases (e.g., "living quarters" -> "living_room")
        event_room_type = normalize_room_type(data.get("room_type", ""))
        target_normalized = normalize_room_type(target_room_type)

        return event_room_type == target_normalized

    def _extract_amount(self, data: dict[str, Any]) -> int:  # noqa: ARG002
        return 1


class TrainEvaluator(ObjectiveEvaluator):
    """Evaluates 'train' objectives (e.g. 'Train a Dweller').

    Listens to DWELLER_TRAINED events.
    Optionally matches target_entity["stat"] for stat-specific training objectives.
    """

    objective_type = "train"
    subscribed_events = [GameEvent.DWELLER_TRAINED]

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:  # noqa: ARG002
        target = objective.target_entity or {}
        target_stat = target.get("stat")

        if not target_stat:
            return True

        return data.get("stat_trained") == target_stat

    def _extract_amount(self, data: dict[str, Any]) -> int:  # noqa: ARG002
        return 1


class AssignEvaluator(ObjectiveEvaluator):
    """Evaluates 'assign' objectives (e.g. 'Assign 5 Dwellers to Rooms').

    Listens to DWELLER_ASSIGNED events.
    Optionally matches target_entity["room_type"] for room-specific assignments.
    """

    objective_type = "assign"
    subscribed_events = [GameEvent.DWELLER_ASSIGNED]

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:  # noqa: ARG002
        target = objective.target_entity or {}
        target_room_type = target.get("room_type")

        if not target_room_type:
            return True

        event_room_type = normalize_room_type(data.get("room_type", ""))
        target_normalized = normalize_room_type(target_room_type)
        return event_room_type == target_normalized

    def _extract_amount(self, data: dict[str, Any]) -> int:  # noqa: ARG002
        return 1


class AssignCorrectEvaluator(ObjectiveEvaluator):
    """Evaluates 'assign_correct' objectives (e.g. 'Correctly Assign 5 Dwellers').

    A "correct" assignment means the dweller's highest SPECIAL stat matches
    the room's primary production stat (e.g., Strength for Power Plant).

    Listens to DWELLER_ASSIGNED_CORRECTLY events.
    """

    objective_type = "assign_correct"
    subscribed_events = [GameEvent.DWELLER_ASSIGNED_CORRECTLY]

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:  # noqa: ARG002
        return data.get("is_correct", False)

    def _extract_amount(self, data: dict[str, Any]) -> int:  # noqa: ARG002
        return 1


class ReachEvaluator(ObjectiveEvaluator):
    """Evaluates 'reach' objectives (e.g. 'Reach 10 Dwellers', 'Reach Level 5').

    Listens to DWELLER_LEVEL_UP events.
    For dweller count targets, checks current vault population.
    For level targets, checks if the leveled dweller meets the target.

    Note: 'reach' objectives use absolute values, not increments.
    Progress is set to the current value rather than incremented.
    """

    objective_type = "reach"
    subscribed_events = [GameEvent.DWELLER_LEVEL_UP, GameEvent.DWELLER_ASSIGNED]

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:  # noqa: ARG002
        target = objective.target_entity or {}
        target_type = target.get("reach_type") or target.get("target")

        # Handle various target type keys
        if target_type in ("dweller_count", "population"):
            return event_type == GameEvent.DWELLER_ASSIGNED

        if target_type == "level":
            return event_type == GameEvent.DWELLER_LEVEL_UP

        # Unknown or missing target_type - don't match to avoid false positives
        if not target_type:
            return False

        return False

    async def _update_progress(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        objective: Objective,
        link: VaultObjectiveProgressLink,
        amount: int,
    ) -> None:
        """Override: 'reach' objectives use absolute values from event data."""
        target = objective.target_entity or {}
        target_type = target.get("reach_type") or target.get("target")

        if target_type in ("dweller_count", "population"):
            current_value = await self._get_dweller_count(db_session, vault_id)
        elif target_type == "level":
            current_value = amount
        else:
            current_value = amount

        old_progress = link.progress
        link.progress = current_value
        link.total = objective.target_amount

        logger.info(
            f"Objective '{objective.challenge}' progress for vault {vault_id}: "
            f"{old_progress} -> {link.progress}/{objective.target_amount}"
        )

        if link.progress >= objective.target_amount:
            await self._auto_complete(db_session, vault_id, objective, link)
        else:
            await db_session.commit()

    def _extract_amount(self, data: dict[str, Any]) -> int:
        return data.get("current_value", data.get("level", data.get("amount", 1)))

    @staticmethod
    async def _get_dweller_count(db_session: AsyncSession, vault_id: UUID4) -> int:
        """Get count of dwellers in vault using COUNT query (no materialization)."""
        from sqlalchemy import func, select

        from app.models.dweller import Dweller

        query = select(func.count()).select_from(Dweller).where(Dweller.vault_id == vault_id)
        result = await db_session.execute(query)
        return result.scalar_one_or_none() or 0


class ExpeditionEvaluator(ObjectiveEvaluator):
    """Evaluates 'expedition' objectives (e.g. 'Complete 3 Expeditions', 'Complete 1 Main Quest').

    Listens to QUEST_COMPLETED events.
    Matches on target_entity["quest_type"] for specific quest types, or wildcard for any.
    """

    objective_type = "expedition"
    subscribed_events = [GameEvent.QUEST_COMPLETED]

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:  # noqa: ARG002
        target = objective.target_entity or {}
        target_quest_type = target.get("quest_type")

        if not target_quest_type or target_quest_type in ("*", "any"):
            return True

        event_quest_type = data.get("quest_type", "")
        return event_quest_type.lower() == target_quest_type.lower()

    def _extract_amount(self, data: dict[str, Any]) -> int:  # noqa: ARG002
        return 1


class LevelUpEvaluator(ObjectiveEvaluator):
    """Evaluates 'level_up' objectives (e.g. 'Level up 2 Dwellers to Lv.5+').

    Listens to DWELLER_LEVEL_UP events.
    Matches if the new level >= target_entity["min_level"].
    Increments progress for each dweller meeting the level requirement.
    """

    objective_type = "level_up"
    subscribed_events = [GameEvent.DWELLER_LEVEL_UP]

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:  # noqa: ARG002
        target = objective.target_entity or {}
        raw_min_level = target.get("min_level", 1)
        try:
            min_level = int(raw_min_level)
        except (TypeError, ValueError):
            min_level = 1

        new_level = data.get("new_level", data.get("level", 1))
        return new_level >= min_level

    def _extract_amount(self, data: dict[str, Any]) -> int:  # noqa: ARG002
        return 1


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
