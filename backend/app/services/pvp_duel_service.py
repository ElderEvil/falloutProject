"""Cross-vault exhibition duels: posting, lazy expiry, accepting and settlement.

A duel settles exactly once, on accept, in one transaction with its bell
notification. Dwellers are never touched — the snapshot is the only record of who
fought.
"""

import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.enums import NotificationType, PvpDuelStatus
from app.crud import pvp_duel as pvp_duel_crud
from app.models.pvp_duel import PvpDuel
from app.models.vault import Vault
from app.schemas.pvp_duel import PvpDuelBoardEntry, PvpDuelRead, PvpPartyRead
from app.services.notification_service import NotificationService
from app.services.pvp.resolver import resolve_duel
from app.services.pvp.snapshots import build_snapshot, select_party
from app.utils.exceptions import (
    AccessDeniedException,
    NotFoundException,
    ResourceConflictException,
    ValidationException,
)
from app.utils.time import utcnow

logger = logging.getLogger(__name__)

OPEN_DUEL_TTL = timedelta(hours=24)


def _party(snapshot: dict[str, Any]) -> PvpPartyRead:
    return PvpPartyRead(
        vault_name=snapshot["vault_name"],
        party_size=int(snapshot["party_size"]),
        member_names=[member["name"] for member in snapshot["members"]],
        power_band=snapshot["power_band"],
    )


def _read(duel: PvpDuel) -> PvpDuelRead:
    defender_snapshot = duel.defender_snapshot
    return PvpDuelRead(
        duel_id=duel.id,
        status=PvpDuelStatus(duel.status),
        outcome=duel.outcome,
        challenger_vault_id=duel.challenger_vault_id,
        defender_vault_id=duel.defender_vault_id,
        challenger_party=_party(duel.challenger_snapshot),
        defender_party=_party(defender_snapshot) if defender_snapshot else None,
        journal=duel.journal,
        created_at=duel.created_at,
        accepted_at=duel.accepted_at,
        expires_at=duel.expires_at,
    )


class PvpDuelService:
    """Posts challenges and settles them without touching either vault's dweller rows."""

    async def post(
        self,
        db_session: AsyncSession,
        vault_id: UUID,
        *,
        defender_vault_id: UUID | None = None,
        dweller_ids: list[UUID],
    ) -> PvpDuelRead:
        """Post one open duel; lazily releases this vault's expired slot first."""
        now = utcnow()
        vault = await self._vault(db_session, vault_id)
        if defender_vault_id is not None:
            if defender_vault_id == vault_id:
                raise ValidationException("A vault cannot challenge itself.")
            await self._vault(db_session, defender_vault_id)

        await self._release_expired_slots(db_session, vault_id, now)
        challenger_snapshot = await self._snapshot(db_session, vault, dweller_ids)
        duel = PvpDuel(
            challenger_vault_id=vault_id,
            defender_vault_id=defender_vault_id,
            challenger_snapshot=challenger_snapshot,
            expires_at=now + OPEN_DUEL_TTL,
        )
        db_session.add(duel)
        await db_session.commit()
        await db_session.refresh(duel)
        return _read(duel)

    async def list_board(self, db_session: AsyncSession, vault_id: UUID) -> list[PvpDuelBoardEntry]:
        """Open challenges this vault may accept, with expiry applied on read."""
        now = utcnow()
        entries: list[PvpDuelBoardEntry] = []
        for duel in await pvp_duel_crud.list_open_board(db_session, vault_id):
            if duel.expires_at <= now:
                duel.status = PvpDuelStatus.EXPIRED
                db_session.add(duel)
                continue
            snapshot = duel.challenger_snapshot
            entries.append(
                PvpDuelBoardEntry(
                    duel_id=duel.id,
                    challenger_vault_name=snapshot["vault_name"],
                    party_size=int(snapshot["party_size"]),
                    member_names=[member["name"] for member in snapshot["members"]],
                    power_band=snapshot["power_band"],
                    expires_at=duel.expires_at,
                )
            )
        await db_session.commit()
        return entries

    async def get(self, db_session: AsyncSession, vault_id: UUID, duel_id: UUID) -> PvpDuelRead:
        """Full duel for replay; only its two participants may read it."""
        duel = await self._duel_for_vault(db_session, vault_id, duel_id)
        if PvpDuelStatus(duel.status) == PvpDuelStatus.OPEN and duel.expires_at <= utcnow():
            duel.status = PvpDuelStatus.EXPIRED
            db_session.add(duel)
            await db_session.commit()
        return _read(duel)

    async def accept(
        self,
        db_session: AsyncSession,
        vault_id: UUID,
        duel_id: UUID,
        *,
        dweller_ids: list[UUID],
    ) -> PvpDuelRead:
        """Accept, freeze the defender party, settle and notify the challenger once."""
        duel = await pvp_duel_crud.get_for_update(db_session, duel_id)
        if duel is None:
            raise NotFoundException("Duel not found.")
        if PvpDuelStatus(duel.status) != PvpDuelStatus.OPEN:
            raise ResourceConflictException("This duel is no longer open.")

        now = utcnow()
        if duel.expires_at <= now:
            # Rejected, not applied: record the expiry so the slot frees, then refuse.
            duel.status = PvpDuelStatus.EXPIRED
            db_session.add(duel)
            await db_session.commit()
            raise ValidationException("This duel has expired.")

        if duel.challenger_vault_id == vault_id:
            raise ValidationException("A vault cannot accept its own duel.")
        if duel.defender_vault_id is not None and duel.defender_vault_id != vault_id:
            raise AccessDeniedException("This duel is aimed at another vault.")

        defender = await self._vault(db_session, vault_id)
        defender_snapshot = await self._snapshot(db_session, defender, dweller_ids)
        resolution = resolve_duel(duel.challenger_snapshot, defender_snapshot)

        duel.defender_vault_id = vault_id
        duel.defender_snapshot = defender_snapshot
        duel.outcome = resolution.outcome
        duel.journal = resolution.journal
        duel.status = PvpDuelStatus.ACCEPTED
        duel.accepted_at = now
        db_session.add(duel)

        won = resolution.outcome == "challenger"
        await NotificationService.notify_owner(
            db_session,
            duel.challenger_vault_id,
            context=f"pvp duel settled duel={duel.id} challenger={duel.challenger_vault_id}",
            sender=lambda user_id: NotificationService.create_and_send(
                db_session,
                user_id=user_id,
                vault_id=duel.challenger_vault_id,
                notification_type=NotificationType.COMBAT_VICTORY if won else NotificationType.COMBAT_DEFEAT,
                title="Exhibition duel won" if won else "Exhibition duel lost",
                message=(
                    f"{defender_snapshot['vault_name']} accepted your challenge — you won."
                    if won
                    else f"{defender_snapshot['vault_name']} accepted your challenge — you lost."
                ),
                meta_data={"duel_id": str(duel.id)},
                commit=False,
            ),
        )
        try:
            await db_session.commit()
        except Exception:
            NotificationService.discard_deferred_notifications(db_session)
            await db_session.rollback()
            raise
        await NotificationService.deliver_deferred_notifications(db_session)
        logger.info("Pvp duel %s settled: %s", duel.id, duel.outcome)
        return _read(duel)

    async def _release_expired_slots(self, db_session: AsyncSession, vault_id: UUID, now: datetime) -> None:
        """Expire this vault's stale OPEN rows; any survivor means the slot is still taken."""
        open_duels = await pvp_duel_crud.list_open_by_challenger(db_session, vault_id)
        live = 0
        for duel in open_duels:
            if duel.expires_at <= now:
                duel.status = PvpDuelStatus.EXPIRED
                db_session.add(duel)
            else:
                live += 1
        if live:
            raise ResourceConflictException("Your vault already has an open duel.")
        await db_session.flush()

    async def _snapshot(self, db_session: AsyncSession, vault: Vault, dweller_ids: list[UUID]) -> dict[str, Any]:
        pool = await pvp_duel_crud.get_party(db_session, vault.id, dweller_ids)
        try:
            party = select_party(pool, dweller_ids)
        except ValueError as exc:
            raise ValidationException(str(exc)) from exc
        if not party:
            raise ValidationException("Pick at least one living dweller to fight.")
        return build_snapshot(vault, party)

    async def _vault(self, db_session: AsyncSession, vault_id: UUID) -> Vault:
        vault = await pvp_duel_crud.get_vault(db_session, vault_id)
        if vault is None:
            raise NotFoundException("Vault not found.")
        return vault

    async def _duel_for_vault(self, db_session: AsyncSession, vault_id: UUID, duel_id: UUID) -> PvpDuel:
        duel = await pvp_duel_crud.get_duel(db_session, duel_id)
        if duel is None or vault_id not in (duel.challenger_vault_id, duel.defender_vault_id):
            raise NotFoundException("Duel not found.")
        return duel


pvp_duel_service = PvpDuelService()
