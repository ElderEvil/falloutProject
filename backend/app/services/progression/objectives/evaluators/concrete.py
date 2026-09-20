"""Concrete objective evaluators: the per-type event-matching rules.

All evaluators share the engine in ``base.ObjectiveEvaluator``; each class here
declares its ``objective_type``, the events it listens for, and how event data
matches an objective's ``target_entity``.
"""

import logging
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.event_bus import GameEvent
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink
from app.services.progression.objectives.evaluators.base import ObjectiveEvaluator
from app.utils.objective_constants import (
    normalize_item_type,
    normalize_resource_type,
    normalize_room_type,
)

logger = logging.getLogger(__name__)


class CollectEvaluator(ObjectiveEvaluator):
    """Evaluates 'collect' objectives (e.g. 'Collect 100 Caps', 'Collect 500 Food').

    Listens to RESOURCE_COLLECTED and ITEM_COLLECTED events.
    Matches on target_entity["resource_type"] or target_entity["item_type"].
    """

    objective_type = "collect"
    subscribed_events = (GameEvent.RESOURCE_COLLECTED, GameEvent.ITEM_COLLECTED)

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
    subscribed_events = (GameEvent.ROOM_BUILT, GameEvent.ROOM_UPGRADED)

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        target = objective.target_entity or {}
        target_room_type = target.get("room_type")

        # Wildcard matches any room ("*", "any", or null)
        if not target_room_type or target_room_type in ("*", "any"):
            return True

        # Use normalize_room_type to handle aliases (e.g., "living quarters" -> "living_room")
        event_room_type = normalize_room_type(data.get("room_type", ""))
        target_normalized = normalize_room_type(target_room_type)

        return event_room_type == target_normalized


class TrainEvaluator(ObjectiveEvaluator):
    """Evaluates 'train' objectives (e.g. 'Train a Dweller').

    Listens to DWELLER_TRAINED events.
    Optionally matches target_entity["stat"] for stat-specific training objectives.
    """

    objective_type = "train"
    subscribed_events = (GameEvent.DWELLER_TRAINED,)

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        target = objective.target_entity or {}
        target_stat = target.get("stat")

        if not target_stat:
            return True

        return data.get("stat_trained") == target_stat


class AssignEvaluator(ObjectiveEvaluator):
    """Evaluates 'assign' objectives (e.g. 'Assign 5 Dwellers to Rooms').

    Listens to DWELLER_ASSIGNED events.
    Optionally matches target_entity["room_type"] for room-specific assignments.
    """

    objective_type = "assign"
    subscribed_events = (GameEvent.DWELLER_ASSIGNED,)

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        target = objective.target_entity or {}
        target_room_type = target.get("room_type")

        if not target_room_type:
            return True

        event_room_type = normalize_room_type(data.get("room_type", ""))
        target_normalized = normalize_room_type(target_room_type)
        return event_room_type == target_normalized


class AssignCorrectEvaluator(ObjectiveEvaluator):
    """Evaluates 'assign_correct' objectives (e.g. 'Correctly Assign 5 Dwellers').

    A "correct" assignment means the dweller's highest SPECIAL stat matches
    the room's primary production stat (e.g., Strength for Power Plant).

    Listens to DWELLER_ASSIGNED_CORRECTLY events.
    """

    objective_type = "assign_correct"
    subscribed_events = (GameEvent.DWELLER_ASSIGNED_CORRECTLY,)

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        return data.get("is_correct", False)


class ReachEvaluator(ObjectiveEvaluator):
    """Evaluates 'reach' objectives (e.g. 'Reach 10 Dwellers', 'Reach Level 5').

    Listens to DWELLER_LEVEL_UP, DWELLER_ASSIGNED and DWELLER_ADDED events.
    For dweller count targets, checks current vault population.
    For level targets, checks if the leveled dweller meets the target.

    Note: 'reach' objectives use absolute values, not increments.
    Progress is set to the current value rather than incremented.
    """

    objective_type = "reach"
    subscribed_events = (GameEvent.DWELLER_LEVEL_UP, GameEvent.DWELLER_ASSIGNED, GameEvent.DWELLER_ADDED)

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        target = objective.target_entity or {}
        target_type = target.get("reach_type") or target.get("target")

        # Handle various target type keys
        if target_type in ("dweller_count", "population"):
            return event_type in (GameEvent.DWELLER_ASSIGNED, GameEvent.DWELLER_ADDED)

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
        from app.crud.vault import vault as vault_crud

        return await vault_crud.get_population(db_session=db_session, vault_id=vault_id)


class ExpeditionEvaluator(ObjectiveEvaluator):
    """Evaluates 'expedition' objectives (e.g. 'Complete 3 Expeditions', 'Complete 1 Main Quest').

    Listens to QUEST_COMPLETED events.
    Matches on target_entity["quest_type"] for specific quest types, or wildcard for any.
    """

    objective_type = "expedition"
    subscribed_events = (GameEvent.QUEST_COMPLETED,)

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        target = objective.target_entity or {}
        target_quest_type = target.get("quest_type")

        if not target_quest_type or target_quest_type in ("*", "any"):
            return True

        event_quest_type = data.get("quest_type", "")
        return event_quest_type.lower() == target_quest_type.lower()


class LevelUpEvaluator(ObjectiveEvaluator):
    """Evaluates 'level_up' objectives (e.g. 'Level up 2 Dwellers to Lv.5+').

    Listens to DWELLER_LEVEL_UP events.
    Matches if the new level >= target_entity["min_level"].
    Increments progress for each dweller meeting the level requirement.
    """

    objective_type = "level_up"
    subscribed_events = (GameEvent.DWELLER_LEVEL_UP,)

    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        target = objective.target_entity or {}
        raw_min_level = target.get("min_level", 1)
        try:
            min_level = int(raw_min_level)
        except (TypeError, ValueError):
            min_level = 1

        new_level = data.get("new_level", data.get("level", 1))
        return new_level >= min_level
