"""Objective evaluator base: the shared event-handling engine.

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
import contextvars
import logging
from typing import Any

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.event_bus import EventBus, GameEvent
from app.db.session import async_session_maker
from app.models.objective import Objective
from app.models.vault_objective import VaultObjectiveProgressLink

logger = logging.getLogger(__name__)

# Loop-local session maker: dramatiq worker threads each run ``asyncio.run(run_tick())``
# with their own event loop, so handlers must open sessions from the maker bound to
# the loop that emitted the event (not the module-global one, which would share a
# single asyncpg connection across loops and trigger InterfaceError collisions).
current_session_maker: contextvars.ContextVar[Any] = contextvars.ContextVar("current_session_maker", default=None)


def set_current_session_maker(maker: Any) -> None:
    """Set the session maker for the current event loop's context."""
    current_session_maker.set(maker)


class ObjectiveEvaluator(abc.ABC):
    """Base class for objective evaluators.

    Each evaluator handles a specific objective_type (e.g. "collect", "build")
    by subscribing to relevant GameEvent types and updating progress when
    matching events are emitted.
    """

    objective_type: str
    subscribed_events: tuple[GameEvent, ...]

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus
        for event_type in self.subscribed_events:
            self._event_bus.subscribe(event_type, self._handle_event)

    def unsubscribe(self) -> None:
        for event_type in self.subscribed_events:
            self._event_bus.unsubscribe(event_type, self._handle_event)

    async def _handle_event(self, event_type: str, vault_id: UUID4, data: dict[str, Any]) -> None:
        logger.debug(f"[DEBUG] {self.__class__.__name__} received {event_type} for vault {vault_id} with data: {data}")
        maker = current_session_maker.get() or async_session_maker
        async with maker() as db_session:
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
        from app.crud.objective import objective_crud

        objectives = await objective_crud.get_active_with_links(db_session, vault_id, self.objective_type)
        logger.debug(f"Found {len(objectives)} active '{self.objective_type}' objectives for vault {vault_id}")
        return objectives

    @abc.abstractmethod
    def _matches(self, objective: Objective, event_type: str, data: dict[str, Any]) -> bool:
        """Return True if this event data matches the objective's target_entity criteria."""

    def _extract_amount(self, data: dict[str, Any]) -> int:
        """Increment per matching event by default; amount-aware evaluators override."""
        return 1

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
        from app.utils.reward_delivery import defer_reward_delivery

        link.progress = objective.target_amount

        try:
            async with defer_reward_delivery(db_session):
                await reward_service.process_objective_reward(db_session, vault_id, link)
                link.is_completed = True
                await db_session.commit()
        except Exception:
            await db_session.rollback()
            logger.exception(f"Failed to grant reward for objective '{objective.challenge}' in vault {vault_id}")
            return

        await self._event_bus.emit(
            GameEvent.OBJECTIVE_COMPLETED,
            vault_id,
            {"objective_id": str(objective.id), "challenge": objective.challenge},
        )
        logger.info(f"Objective '{objective.challenge}' auto-completed and reward granted for vault {vault_id}")
