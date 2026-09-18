"""Rules for a dweller who asks to leave the vault.

The ask is a standing request held on the dweller; it is withdrawn once their mood recovers.
The grant is final: the dweller is marked dead by ``EXILE`` and permanently dead in the same
write, so the caps-revival window is skipped and they never come back.
"""

import logging
from datetime import UTC, datetime

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import DeathCauseEnum, DwellerStatusEnum
from app.core.game_config import game_config
from app.crud.dweller import dweller as dweller_crud
from app.models.dweller import Dweller
from app.models.vault import Vault
from app.services.family.death_service import death_service
from app.services.notification_service import notification_service
from app.utils.exceptions import ResourceNotFoundException, VaultOperationException

logger = logging.getLogger(__name__)

_AWAY_STATUSES = {
    DwellerStatusEnum.EXPLORING,
    DwellerStatusEnum.QUESTING,
    DwellerStatusEnum.FIGHTING,
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
        if dweller.status in _AWAY_STATUSES:
            return "Dweller is away from the vault"
        return None

    async def request_exit(self, db_session: AsyncSession, dweller_id: UUID4, *, commit: bool = True) -> Dweller:
        """Record that the dweller has asked to leave, without removing them yet.

        ``commit=False`` lets the chat flow fold the ask into its own transaction.
        """
        dweller = await self._get_dweller(db_session, dweller_id)
        reason = self._eligibility_reason(dweller)
        if reason:
            raise VaultOperationException(detail=reason)
        reason = await self._population_block(db_session, dweller.vault_id)
        if reason:
            raise VaultOperationException(detail=reason)

        dweller.exit_requested_at = datetime.now(UTC).replace(tzinfo=None)
        db_session.add(dweller)
        if commit:
            await db_session.commit()
            await db_session.refresh(dweller)
        else:
            await db_session.flush()
        await self._announce_request(db_session, dweller, commit=commit)

        logger.info("Dweller %s asked to leave vault %s", dweller_id, dweller.vault_id)
        return dweller

    async def refuse_exit(self, db_session: AsyncSession, vault: Vault, dweller_id: UUID4) -> Dweller:
        """Decline the ask: the dweller takes a happiness hit and the request stands."""
        dweller = await self._get_pending(db_session, vault, dweller_id)

        dweller.happiness = max(10, dweller.happiness - game_config.exit_request.refusal_happiness_penalty)
        db_session.add(dweller)
        await db_session.commit()
        await db_session.refresh(dweller)

        logger.info("Vault %s refused %s's exit request", vault.id, dweller_id)
        return dweller

    async def grant_exit(self, db_session: AsyncSession, vault: Vault, dweller_id: UUID4) -> Dweller:
        """Let the dweller go: permanent death by exile, with no revive window."""
        dweller = await self._get_pending(db_session, vault, dweller_id)
        reason = self._eligibility_reason(dweller)
        if reason:
            raise VaultOperationException(detail=reason)
        reason = await self._population_block(db_session, vault.id)
        if reason:
            raise VaultOperationException(detail=reason)

        dweller.exit_requested_at = None
        db_session.add(dweller)
        await db_session.flush()

        return await death_service.mark_as_dead(
            db_session,
            dweller,
            DeathCauseEnum.EXILE,
            commit=True,
            permanent=True,
        )

    async def sync_despair_requests(self, db_session: AsyncSession, vault_id: UUID4) -> list[Dweller]:
        """Raise requests for dwellers in despair, and withdraw requests from dwellers who recovered."""
        threshold = game_config.exit_request.despair_happiness
        now = datetime.now(UTC).replace(tzinfo=None)

        asked = await self._ask_the_despairing(db_session, vault_id, threshold, now)
        withdrawn = await self._withdraw_recovered(db_session, vault_id, threshold)
        for dweller in asked:
            await self._announce_request(db_session, dweller, commit=False)
        if asked or withdrawn:
            await db_session.commit()
        await notification_service.deliver_deferred_notifications(db_session)
        if asked:
            logger.info("%d dweller(s) in vault %s asked to leave", len(asked), vault_id)
        return asked

    async def _ask_the_despairing(
        self, db_session: AsyncSession, vault_id: UUID4, threshold: int, now: datetime
    ) -> list[Dweller]:
        candidates = await dweller_crud.get_despairing_without_exit_request(db_session, vault_id, threshold)
        asked: list[Dweller] = []
        for dweller in candidates:
            if self._eligibility_reason(dweller):
                continue
            dweller.exit_requested_at = now
            db_session.add(dweller)
            asked.append(dweller)
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

    async def _announce_request(self, db_session: AsyncSession, dweller: Dweller, *, commit: bool) -> None:
        """Tell the owner a dweller has asked to leave, so the ask is never silent."""
        await notification_service.notify_owner(
            db_session,
            dweller.vault_id,
            context=f"exit_requested vault={dweller.vault_id} dweller={dweller.id}",
            sender=lambda user_id: notification_service.notify_exit_requested(
                db_session,
                user_id=user_id,
                vault_id=dweller.vault_id,
                dweller_id=dweller.id,
                dweller_name=dweller.display_name,
                meta_data={"vault_id": str(dweller.vault_id)},
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
