"""Rules for a dweller who asks to leave the vault.

The ask is a standing request held on the dweller; it is withdrawn once their mood recovers.
Granting it is a living departure, not a death: the person leaves the vault (canonical
``wasteland``/``departure`` with no active membership) and may later be recruited through the
shared pool, so nothing is written to the death fields and no revival window applies.
"""

import logging
from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.db_locks import try_advisory_xact_lock
from app.core.enums import AvailabilityEnum, DwellerStatusEnum, LifecycleEnum, TrainingStatus
from app.core.game_config import game_config
from app.crud import training as training_crud
from app.crud.dweller import dweller as dweller_crud
from app.crud.vault import vault as vault_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.notification_service import notification_service
from app.utils.exceptions import ResourceNotFoundException, VaultOperationException

logger = logging.getLogger(__name__)

_AWAY_STATUSES = {
    DwellerStatusEnum.EXPLORING,
    DwellerStatusEnum.QUESTING,
}


class ExitRequestService:
    """A dweller who asks to leave is let go: the vault cannot keep them and they do not return."""

    async def list_pending(self, db_session: AsyncSession, vault_id: UUID4) -> list[Dweller]:
        """Dwellers of a vault who have asked to leave and are still waiting."""
        return list(await dweller_crud.get_pending_exit_requests(db_session, vault_id))

    def _eligibility_reason(self, dweller: Dweller) -> str | None:
        """Why this dweller may not take part in the exit flow, or None when eligible."""
        if dweller.is_dead:
            return "Dweller is already dead"
        if dweller.is_deleted:
            return "Dweller is no longer in this vault"
        if not dweller.is_mature:
            return "Only grown dwellers can choose to leave the vault"
        if dweller.status == DwellerStatusEnum.FIGHTING:
            return "Dweller is busy in an arena match"
        if dweller.status in _AWAY_STATUSES:
            return "Dweller is away from the vault"
        return None

    async def request_exit(self, db_session: AsyncSession, dweller_id: UUID4, *, commit: bool = True) -> Dweller:
        """Record that the dweller has asked to leave, without removing them yet.

        ``commit=False`` lets the chat flow fold the ask into its own transaction.
        """
        dweller = await self._get_dweller(db_session, dweller_id)
        vault_id = self._require_vault_id(dweller)
        reason = self._eligibility_reason(dweller)
        if reason:
            raise VaultOperationException(detail=reason)
        reason = await self._population_block(db_session, vault_id)
        if reason:
            raise VaultOperationException(detail=reason)

        now = datetime.now(UTC).replace(tzinfo=None)
        if not await self._lock_exit_requests(db_session, vault_id):
            raise VaultOperationException(detail="Another exit request is already being handled")

        vault = await vault_crud.get(db_session, vault_id)
        if vault is not None:
            reason = await self._daily_cap_block(db_session, vault, now)
            if reason:
                raise VaultOperationException(detail=reason)

        dweller.exit_requested_at = now
        if vault is not None:
            vault.last_exit_request_at = now
            db_session.add(vault)
        db_session.add(dweller)
        if commit:
            await db_session.commit()
            await db_session.refresh(dweller)
        else:
            await db_session.flush()
        await self._announce_request(db_session, dweller, vault_id=vault_id, commit=commit)

        logger.info("Dweller %s asked to leave vault %s", dweller_id, vault_id)
        return dweller

    async def refuse_exit(self, db_session: AsyncSession, vault: Vault, dweller_id: UUID4) -> Dweller:
        """Decline the ask: the request is answered, and the whole vault pays for it."""
        if not await self._lock_exit_requests(db_session, vault.id):
            raise VaultOperationException(detail="Another exit request is already being handled")
        dweller = await self._get_pending(db_session, vault, dweller_id)
        vault_penalty = game_config.exit_request.vault_refusal_happiness_penalty

        for member in await dweller_crud.get_living_in_vault(db_session, vault.id):
            member.happiness = max(10, member.happiness - vault_penalty)

        dweller.exit_requested_at = None
        vault.last_exit_request_at = datetime.now(UTC).replace(tzinfo=None)
        db_session.add(vault)
        db_session.add(dweller)
        await db_session.commit()
        await db_session.refresh(dweller)

        logger.info("Vault %s refused %s's exit request; morale -%d", vault.id, dweller_id, vault_penalty)
        return dweller

    async def grant_exit(self, db_session: AsyncSession, vault: Vault, dweller_id: UUID4) -> Dweller:
        """Let the dweller go: a living departure, not a death."""
        if not await self._lock_exit_requests(db_session, vault.id):
            raise VaultOperationException(detail="Another exit request is already being handled")
        dweller = await self._get_pending(db_session, vault, dweller_id)
        reason = self._eligibility_reason(dweller)
        if reason:
            raise VaultOperationException(detail=reason)
        from app.services.combat.incident_service import committed_responder_ids

        if dweller.id in await committed_responder_ids(db_session, vault.id):
            raise VaultOperationException(detail="Dweller is responding to an active incident")
        reason = await self._population_block(db_session, vault.id)
        if reason:
            raise VaultOperationException(detail=reason)

        from app.services.combat.arena_service import arena_service

        await arena_service.clear_fighter_slots_for_dweller(db_session, dweller_id, commit=False)
        now = datetime.now(UTC).replace(tzinfo=None)
        await self._stop_training(db_session, dweller_id, now)
        dweller.exit_requested_at = None
        dweller.despair_since = None
        dweller.room_id = None
        dweller.apprentice_stat = None
        dweller.apprentice_started_at = None
        dweller.status = DwellerStatusEnum.IDLE
        dweller.lifecycle = LifecycleEnum.WASTELAND
        dweller.availability = AvailabilityEnum.DEPARTURE
        dweller.departed_at = now
        dweller.departure_eligible_at = now + timedelta(days=game_config.radio.recycle_min_age_days)
        dweller.previous_vault_id = vault.id
        dweller.vault_id = None
        vault.last_exit_request_at = now
        db_session.add(vault)
        db_session.add(dweller)
        await db_session.commit()
        await db_session.refresh(dweller)

        logger.info("Dweller %s left vault %s as a living departure", dweller_id, vault.id)
        return dweller

    async def sync_despair_requests(self, db_session: AsyncSession, vault_id: UUID4) -> list[Dweller]:
        """Raise requests for dwellers in despair, and withdraw requests from dwellers who recovered."""
        threshold = game_config.exit_request.despair_happiness
        now = datetime.now(UTC).replace(tzinfo=None)

        asked = await self._ask_the_despairing(db_session, vault_id, threshold, now)
        await self._withdraw_recovered(db_session, vault_id, threshold)
        for dweller in asked:
            await self._announce_request(db_session, dweller, vault_id=vault_id, commit=False)
        await db_session.commit()
        await notification_service.deliver_deferred_notifications(db_session)
        if asked:
            logger.info("%d dweller(s) in vault %s asked to leave", len(asked), vault_id)
        return asked

    async def _lock_exit_requests(self, db_session: AsyncSession, vault_id: UUID4) -> bool:
        """Serialize the cap check-and-stamp per vault (a no-op outside PostgreSQL)."""
        return await try_advisory_xact_lock(db_session, f"exit-request:{vault_id}")

    async def _stop_training(self, db_session: AsyncSession, dweller_id: UUID4, now: datetime) -> None:
        """Cancel the departing person's active training in the departure transaction.

        A departure clears the operational row so the source vault's training tick, which
        only loads ACTIVE sessions, no longer processes the person who left.
        """
        active_training = await training_crud.training.get_active_by_dweller(db_session, dweller_id)
        if active_training is None:
            return
        active_training.status = TrainingStatus.CANCELLED
        active_training.completed_at = now
        db_session.add(active_training)

    @staticmethod
    def _require_vault_id(dweller: Dweller) -> UUID4:
        """A dweller in the exit flow is a vault member; a departure must not reach here."""
        if dweller.vault_id is None:
            raise VaultOperationException(detail="Dweller is no longer in this vault")
        return dweller.vault_id

    async def _daily_cap_block(self, db_session: AsyncSession, vault: Vault, now: datetime) -> str | None:
        """Why the vault cannot raise another ask right now, or None when it can."""
        if await dweller_crud.get_pending_exit_requests(db_session, vault.id):
            return "A dweller is already waiting on an answer"
        per_day = game_config.exit_request.max_exit_requests_per_day
        throttle = timedelta(days=1) / per_day
        if vault.last_exit_request_at is not None and now - vault.last_exit_request_at < throttle:
            return "The vault has already heard an exit request in the last day"
        return None

    async def _ask_the_despairing(
        self, db_session: AsyncSession, vault_id: UUID4, threshold: int, now: datetime
    ) -> list[Dweller]:
        vault = await vault_crud.get(db_session, vault_id)
        if vault is None:
            return []

        if await self._lock_exit_requests(db_session, vault_id):
            block = await self._daily_cap_block(db_session, vault, now)
            if block is None:
                block = await self._population_block(db_session, vault_id)
        else:
            block = "Another exit request is already being handled"

        grace = timedelta(hours=game_config.exit_request.despair_grace_hours)
        eligible: list[Dweller] = []
        for dweller in await dweller_crud.get_living_in_vault(db_session, vault_id):
            if dweller.happiness > threshold:
                dweller.despair_since = None
                continue
            if dweller.despair_since is None:
                dweller.despair_since = now
            if (
                dweller.exit_requested_at is None
                and now - dweller.despair_since >= grace
                and self._eligibility_reason(dweller) is None
            ):
                eligible.append(dweller)

        if block:
            return []

        eligible.sort(key=lambda dweller: dweller.happiness)
        asked = eligible[:1]
        for dweller in asked:
            dweller.exit_requested_at = now
        if asked:
            vault.last_exit_request_at = now
            db_session.add(vault)
        return asked

    async def _withdraw_recovered(self, db_session: AsyncSession, vault_id: UUID4, threshold: int) -> list[Dweller]:
        withdrawn: list[Dweller] = []
        for dweller in await dweller_crud.get_exit_requests_above_happiness(db_session, vault_id, threshold):
            dweller.exit_requested_at = None
            db_session.add(dweller)
            withdrawn.append(dweller)
        if withdrawn:
            logger.info("%d dweller(s) in vault %s withdrew their exit request", len(withdrawn), vault_id)
        return withdrawn

    async def _announce_request(
        self, db_session: AsyncSession, dweller: Dweller, *, vault_id: UUID4, commit: bool
    ) -> None:
        """Tell the owner a dweller has asked to leave, so the ask is never silent."""
        await notification_service.notify_owner(
            db_session,
            vault_id,
            context=f"exit_requested vault={vault_id} dweller={dweller.id}",
            sender=lambda user_id: notification_service.notify_exit_requested(
                db_session,
                user_id=user_id,
                vault_id=vault_id,
                dweller_id=dweller.id,
                dweller_name=dweller.display_name,
                meta_data={"vault_id": str(vault_id)},
                commit=commit,
            ),
        )

    async def _population_block(self, db_session: AsyncSession, vault_id: UUID4) -> str | None:
        living = await dweller_crud.count_living_in_vault(db_session, vault_id)
        if living <= game_config.exit_request.min_population:
            return "The vault must keep more than its minimum population"
        return None

    async def _get_dweller(self, db_session: AsyncSession, dweller_id: UUID4) -> Dweller:
        dweller = await dweller_crud.get(db_session, dweller_id)
        if dweller is None:
            raise ResourceNotFoundException(Dweller, identifier=dweller_id)
        return dweller

    async def _get_pending(self, db_session: AsyncSession, vault: Vault, dweller_id: UUID4) -> Dweller:
        dweller = await dweller_crud.get(db_session, dweller_id, include_deleted=True)
        if dweller.vault_id != vault.id:
            raise VaultOperationException(detail="Dweller does not belong to this vault")
        if dweller.exit_requested_at is None:
            raise VaultOperationException(detail="Dweller has not asked to leave")
        if dweller.is_dead:
            raise VaultOperationException(detail="Dweller is already dead")
        if dweller.is_deleted:
            raise VaultOperationException(detail="Dweller is no longer in this vault")
        return dweller


# Singleton instance
exit_request_service = ExitRequestService()
