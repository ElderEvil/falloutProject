"""Server-wide co-op world events: contributions, lifecycle, read state and claims.

The single ACTIVE event is the shared goal. Contributions are credited from ordinary play
(best-effort, never raising into the caller); the lifecycle advances from a periodic actor
(which owns its transaction); reads never write; a claim pays the stored reward list once.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import WorldEventStatus
from app.crud import world_event as world_event_crud
from app.models.world_event import WorldEvent, WorldEventParticipation
from app.schemas.world_event import WorldEventClaimRead, WorldEventRead
from app.services.notification_service import NotificationService
from app.services.reward_service import reward_service
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.reward_delivery import defer_reward_delivery
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

# Fallback when an event's own window is degenerate (ends_at at or before starts_at).
DEFAULT_EXTENSION_WINDOW = timedelta(days=1)

# Which contribution sources each event kind accepts. A kind missing here still credits (with a
# warning) so a newly seeded kind cannot silently stop counting.
CONTRIBUTION_SOURCES: dict[str, frozenset[str]] = {
    "BLACKOUT_WATCH": frozenset({"incident"}),
    "WASTELAND_RELAY": frozenset({"expedition"}),
}


def _extension_window(event: WorldEvent) -> timedelta:
    """One extension worth of time: the event's original window, floored to a day."""
    window = event.ends_at - event.starts_at
    return window if window > timedelta(0) else DEFAULT_EXTENSION_WINDOW


def _reward_summary(reward: list[dict[str, Any]]) -> str:
    """One-line summary for the completion notification, e.g. ``2000 caps + 1 lunchbox``."""
    parts = [f"{item.get('amount', 1)} {item.get('reward_type', 'reward')}" for item in reward]
    return " + ".join(parts) or "no reward"


class WorldEventService:
    """Lifecycle and contribution rules for the global co-op event."""

    async def record_contribution(self, db_session: AsyncSession, vault_id: UUID, amount: int, *, kind: str) -> None:
        """Credit the ACTIVE event from ordinary play; never raises into the caller.

        ``kind`` names the contributing source; the ACTIVE event's kind must accept it.
        transaction: this method only stages changes. No-op when there is no ACTIVE event or
        the amount is non-positive. A concurrent first-time insert may drop one contribution,
        which is preferable to a 500 on the exploration path.
        """
        if amount <= 0:
            return
        try:
            await self._record_contribution(db_session, vault_id, amount, kind=kind)
        except Exception:
            logger.exception("Failed to record world event contribution for vault %s (%s)", vault_id, kind)

    async def advance(self, db_session: AsyncSession) -> dict[str, Any]:
        """Run one lifecycle step and commit it; called by the periodic actor, not a request."""
        try:
            change = await self._advance(db_session)
            await db_session.commit()
        except Exception:
            NotificationService.discard_deferred_notifications(db_session)
            await db_session.rollback()
            raise
        # Completion notifications are staged inside the transaction and only pushed now, so a
        # rolled-back advance never tells anyone the event is done.
        await NotificationService.deliver_deferred_notifications(db_session)
        return change

    async def get_state(self, db_session: AsyncSession, vault_id: UUID) -> WorldEventRead:
        """Read-only snapshot of the current or latest event; never writes."""
        event = await world_event_crud.get_current(db_session)
        if event is None:
            return WorldEventRead()

        participant_count, _ = await world_event_crud.totals(db_session, event.id)
        participation = await world_event_crud.get_participation(db_session, event.id, vault_id)
        contribution = participation.contribution if participation is not None else 0
        can_claim = (
            event.status == WorldEventStatus.COMPLETED
            and participation is not None
            and participation.reward_claimed_at is None
            and contribution >= event.personal_min
        )
        return WorldEventRead(
            event_id=event.id,
            kind=event.kind,
            title=event.title,
            description=event.description,
            target_amount=event.target_amount,
            progress_amount=event.progress_amount,
            participant_count=participant_count,
            contribution=contribution,
            personal_min=event.personal_min,
            can_claim=can_claim,
            status=event.status,
            starts_at=event.starts_at,
            ends_at=event.ends_at,
            extended_at=event.extended_at,
            reward=list(event.reward or []),
        )

    async def claim(self, db_session: AsyncSession, vault_id: UUID) -> WorldEventClaimRead:
        """Pay the latest completed event's reward list to a qualifying vault exactly once."""
        event = await world_event_crud.get_current(db_session)
        if event is None or event.status != WorldEventStatus.COMPLETED:
            raise ValidationException("The world event is not complete yet.")

        await db_session.flush()
        # The participation row lock serialises competing claims for one vault; the second
        # claim then observes reward_claimed_at and is rejected.
        participation = await world_event_crud.get_participation_for_update(db_session, event.id, vault_id)
        if participation is None:
            raise ValidationException("Your vault took no part in this world event.")
        if participation.reward_claimed_at is not None:
            raise ResourceConflictException("World event reward already claimed.")
        if participation.contribution < event.personal_min:
            raise ValidationException("Your vault did not reach the world event's personal contribution.")

        try:
            async with defer_reward_delivery(db_session):
                granted: list[dict[str, Any]] = [
                    await reward_service.grant(db_session, vault_id, reward) for reward in event.reward or []
                ]
                participation.reward_claimed_at = utcnow()
                db_session.add(participation)
                await db_session.commit()
        except Exception:
            await db_session.rollback()
            raise

        logger.info("World event %s reward claimed by vault %s", event.id, vault_id)
        return WorldEventClaimRead(
            event_id=event.id,
            contribution=participation.contribution,
            rewards=granted,
        )

    async def _record_contribution(self, db_session: AsyncSession, vault_id: UUID, amount: int, *, kind: str) -> None:
        current = await world_event_crud.get_current(db_session)
        if current is None or current.status != WorldEventStatus.ACTIVE:
            return

        # Sessions run with autoflush off; flush pending work so the row-locked reload below
        # sees this caller's earlier contributions instead of overwriting them.
        await db_session.flush()
        event = await world_event_crud.get_for_update(db_session, current.id)
        if event is None or event.status != WorldEventStatus.ACTIVE:
            return

        sources = CONTRIBUTION_SOURCES.get(event.kind)
        if sources is None:
            logger.warning("World event kind %r has no contribution sources; crediting %s", event.kind, kind)
        elif kind not in sources:
            return

        participation = await world_event_crud.get_participation_for_update(db_session, event.id, vault_id)
        if participation is None:
            participation = await self._insert_participation(db_session, event.id, vault_id)
            if participation is None:
                logger.warning(
                    "Lost world event contribution for vault %s (%s): participation insert raced", vault_id, kind
                )
                return

        participation.contribution += amount
        event.progress_amount += amount
        db_session.add(participation)
        db_session.add(event)

    async def _insert_participation(
        self, db_session: AsyncSession, event_id: UUID, vault_id: UUID
    ) -> WorldEventParticipation | None:
        """Insert an empty participation, retrying once with a row-locked read on a race."""
        participation = WorldEventParticipation(world_event_id=event_id, vault_id=vault_id, contribution=0)
        try:
            # Savepoint: an IntegrityError would otherwise poison the caller's transaction.
            async with db_session.begin_nested():
                db_session.add(participation)
                await db_session.flush()
        except IntegrityError:
            return await world_event_crud.get_participation_for_update(db_session, event_id, vault_id)
        return participation

    async def _advance(self, db_session: AsyncSession) -> dict[str, Any]:
        now = utcnow()
        current = await world_event_crud.get_current(db_session)
        if current is not None and current.status == WorldEventStatus.ACTIVE:
            event = await world_event_crud.get_for_update(db_session, current.id)
            if event is not None and event.status == WorldEventStatus.ACTIVE:
                return await self._advance_active(db_session, event, now)

        scheduled = await world_event_crud.get_next_scheduled(db_session, at=now)
        if scheduled is None:
            return self._change(None, None)
        event = await world_event_crud.get_for_update(db_session, scheduled.id)
        if event is None or event.status != WorldEventStatus.SCHEDULED:
            return self._change(None, event)
        # The partial unique index is only a backstop; never let the service propose a second ACTIVE.
        active = await world_event_crud.get_current(db_session)
        if active is not None and active.status == WorldEventStatus.ACTIVE:
            return self._change(None, event)
        event.status = WorldEventStatus.ACTIVE
        db_session.add(event)
        return self._change("activated", event)

    async def _advance_active(self, db_session: AsyncSession, event: WorldEvent, now: datetime) -> dict[str, Any]:
        if event.progress_amount >= event.target_amount:
            event.status = WorldEventStatus.COMPLETED
            db_session.add(event)
            await self._notify_completed(db_session, event)
            return self._change("completed", event)
        if now < event.ends_at:
            return self._change(None, event)
        if event.extended_at is None:
            event.ends_at += _extension_window(event)
            event.extended_at = now
            db_session.add(event)
            return self._change("extended", event)
        event.status = WorldEventStatus.EXPIRED
        db_session.add(event)
        return self._change("expired", event)

    async def _notify_completed(self, db_session: AsyncSession, event: WorldEvent) -> None:
        """Stage one completion notification per participating vault; ``advance`` delivers it."""
        reward_summary = _reward_summary(event.reward or [])
        for vault_id in await world_event_crud.list_participant_vault_ids(db_session, event.id):
            await NotificationService.notify_owner(
                db_session,
                vault_id,
                context=f"world event completed vault={vault_id} event={event.id}",
                sender=lambda user_id, vault_id=vault_id: NotificationService.notify_world_event_completed(
                    db_session,
                    user_id=user_id,
                    vault_id=vault_id,
                    event_id=event.id,
                    event_title=event.title,
                    reward_summary=reward_summary,
                ),
            )

    @staticmethod
    def _change(action: str | None, event: WorldEvent | None) -> dict[str, Any]:
        return {
            "action": action,
            "event_id": event.id if event is not None else None,
            "status": event.status if event is not None else None,
        }


world_event_service = WorldEventService()
