"""Server-wide co-op world events: contributions, lifecycle ticks, reads and one-time claims."""

import logging
from datetime import datetime, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import WorldEventStatus
from app.core.game_config import game_config
from app.crud import world_event as world_event_crud
from app.models.world_event import WorldEvent, WorldEventParticipation
from app.schemas.world_event import WorldEventClaimRead, WorldEventRead
from app.services.notification_service import NotificationService
from app.services.reward_service import reward_service
from app.utils.exceptions import ResourceConflictException, ValidationException
from app.utils.reward_delivery import defer_reward_delivery
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

# Which contribution sources each event kind accepts. A kind missing here still credits (with a
# warning) so a newly seeded kind cannot silently stop counting.
CONTRIBUTION_SOURCES: dict[str, frozenset[str]] = {
    "BLACKOUT_WATCH": frozenset({"incident"}),
    "WASTELAND_RELAY": frozenset({"expedition"}),
}


def _extension_window(event: WorldEvent, floor: timedelta = timedelta(days=1)) -> timedelta:
    """One extension worth of time: the event's original window, floored for a degenerate one."""
    window = event.ends_at - event.starts_at
    return window if window > timedelta(0) else floor


def _reward_summary(reward: list[dict[str, Any]]) -> str:
    """One-line summary for the completion notification, e.g. ``2000 caps + 1 lunchbox``."""
    parts = [f"{item.get('amount', 1)} {item.get('reward_type', 'reward')}" for item in reward]
    return " + ".join(parts) or "no reward"


class WorldEventService:
    """Lifecycle, contribution and claim rules for the ACTIVE event."""

    async def record_contribution(self, db_session: AsyncSession, vault_id: UUID, amount: int, *, kind: str) -> None:
        """Credit the ACTIVE event from ordinary play; stages changes, never raises into the caller.

        No-op without an ACTIVE event or for a non-positive amount. A first-time insert that loses
        a race drops one contribution, which beats a 500 on the exploration path.
        """
        if amount <= 0:
            return
        try:
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
                        "Lost world event contribution for vault %s (%s): participation insert raced",
                        vault_id,
                        kind,
                    )
                    return

            participation.contribution += amount
            event.progress_amount += amount
            db_session.add(participation)
            db_session.add(event)
        except Exception:
            logger.exception("Failed to record world event contribution for vault %s (%s)", vault_id, kind)

    async def advance(self, db_session: AsyncSession) -> str | None:
        """Run one lifecycle step and commit it; owns the transaction, called by the actor."""
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
        """Read-only snapshot of the current or latest event."""
        event = await world_event_crud.get_current(db_session)
        if event is None:
            return WorldEventRead()

        participant_count = await world_event_crud.participant_count(db_session, event.id)
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
        """Pay the newest completed event this vault joined, exactly once.

        Deliberately not `get_current`: while the next event is ACTIVE that returns the ACTIVE
        row, which would strand the previous event's reward for every vault that had not claimed
        it yet.
        """
        event = await world_event_crud.get_claimable_for_vault(db_session, vault_id)
        if event is None:
            if await world_event_crud.has_completed(db_session):
                raise ValidationException("Your vault took no part in this world event.")
            raise ValidationException("The world event is not complete yet.")

        await db_session.flush()
        # The participation row lock serialises competing claims for one vault; the second
        # claim then observes reward_claimed_at and is rejected.
        participation = cast(
            "WorldEventParticipation",
            await world_event_crud.get_participation_for_update(db_session, event.id, vault_id),
        )
        if participation.reward_claimed_at is not None:
            raise ResourceConflictException("World event reward already claimed.")
        if participation.contribution < event.personal_min:
            raise ValidationException("Your vault did not reach the world event's personal contribution.")

        try:
            async with defer_reward_delivery(db_session):
                for reward in event.reward or []:
                    await reward_service.grant(db_session, vault_id, reward)
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
        )

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

    async def _advance(self, db_session: AsyncSession) -> str | None:
        now = utcnow()
        current = await world_event_crud.get_current(db_session)
        if current is not None and current.status == WorldEventStatus.ACTIVE:
            event = await world_event_crud.get_for_update(db_session, current.id)
            if event is not None and event.status == WorldEventStatus.ACTIVE:
                return await self._advance_active(db_session, event, now)

        scheduled = await world_event_crud.get_next_scheduled(db_session, at=now)
        if scheduled is None:
            scheduled = await self._schedule_next(db_session, current, now)
            if scheduled is None:
                return None
            db_session.add(scheduled)
            await db_session.flush()
        event = await world_event_crud.get_for_update(db_session, scheduled.id)
        if event is None or event.status != WorldEventStatus.SCHEDULED:
            return None
        # The partial unique index is only a backstop; never let the service propose a second ACTIVE.
        if current is not None and current.status == WorldEventStatus.ACTIVE:
            return None
        event.status = WorldEventStatus.ACTIVE
        db_session.add(event)
        return "activated"

    async def _schedule_next(
        self, db_session: AsyncSession, current: WorldEvent | None, now: datetime
    ) -> WorldEvent | None:
        """Seed the initial/next weekly relay, preserving any existing schedule."""
        if not game_config.features.world_events or await world_event_crud.has_scheduled(db_session):
            return None
        if current is not None and (current.updated_at or current.ends_at) + timedelta(days=1) > now:
            return None
        return WorldEvent(
            kind="WASTELAND_RELAY",
            title="Wasteland Relay",
            description="Every expedition strengthens the relay between our vaults.",
            target_amount=100,
            personal_min=5,
            reward=[{"reward_type": "caps", "amount": 250}],
            starts_at=now,
            ends_at=now + timedelta(days=7),
        )

    async def _advance_active(self, db_session: AsyncSession, event: WorldEvent, now: datetime) -> str | None:
        if event.progress_amount >= event.target_amount:
            event.status = WorldEventStatus.COMPLETED
            db_session.add(event)
            await self._notify_completed(db_session, event)
            return "completed"
        if now < event.ends_at:
            return None
        if event.extended_at is None:
            event.ends_at += _extension_window(event)
            event.extended_at = now
            db_session.add(event)
            return "extended"
        event.status = WorldEventStatus.EXPIRED
        db_session.add(event)
        return "expired"

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


world_event_service = WorldEventService()
