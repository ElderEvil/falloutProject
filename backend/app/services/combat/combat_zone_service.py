"""Combat Zone service — commands, reads, and the transaction boundary.

Tick mechanics (travel, pairing, rounds, settlement) live in
``combat_zone_engine``. This module owns the HTTP-facing surface: one public
operation, one transaction, domain exceptions, and the views the API returns.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from app.core import db_locks
from app.core.combat_zone_dispatch import request_combat_zone_tick
from app.core.enums import CombatZonePartyStatus, CombatZoneStance, DwellerStatusEnum, LifecycleEnum
from app.core.game_config import game_config
from app.crud import vault as vault_crud
from app.crud.combat_zone import combat_zone_crud
from app.crud.incident import incident_crud
from app.models.combat_zone import CombatZoneMatch, CombatZoneParty
from app.schemas.combat_zone import (
    CombatZoneEventRead,
    CombatZoneLobbyParty,
    CombatZoneLobbyRead,
    CombatZoneMatchPartyRead,
    CombatZoneMatchRead,
    CombatZoneMatchSummary,
    CombatZonePartyRead,
)
from app.services.combat.combat_zone_engine import (
    TICK_LOCK_KEY,
    CombatZoneTickStats,
    combat_zone_engine,
)
from app.utils.combat import combat_power
from app.utils.exceptions import (
    FeatureDisabledException,
    NotFoundException,
    ResourceConflictException,
    ValidationException,
)

if TYPE_CHECKING:
    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller
    from app.models.vault import Vault

logger = logging.getLogger(__name__)

SENDABLE_STATUSES = (DwellerStatusEnum.IDLE, DwellerStatusEnum.WORKING)


def _now() -> datetime:
    return datetime.utcnow()


class CombatZoneService:
    """Combat Zone commands and read models; tick work is delegated."""

    # -- Guards -------------------------------------------------------------------

    @staticmethod
    def _ensure_enabled() -> None:
        if not game_config.combat_zone.enabled:
            raise FeatureDisabledException("The Combat Zone is currently offline.")

    @staticmethod
    def _assert_active_vault(vault: Vault | None) -> Vault:
        if vault is None or vault.is_deleted:
            raise NotFoundException("Vault not found.")
        return vault

    @staticmethod
    def _assert_party(party: CombatZoneParty | None, *, statuses: tuple[CombatZonePartyStatus, ...]) -> CombatZoneParty:
        if party is None or party.status not in statuses:
            raise ResourceConflictException("The party is not in a state that allows this action.")
        return party

    # -- Reads --------------------------------------------------------------------

    async def get_party(self, db_session: AsyncSession, vault_id: UUID4) -> CombatZonePartyRead | None:
        self._ensure_enabled()
        party = await combat_zone_crud.get_party_by_vault(db_session, vault_id)
        if party is None:
            return None
        return await self._party_read(db_session, party)

    async def get_lobby(self, db_session: AsyncSession) -> CombatZoneLobbyRead:
        self._ensure_enabled()
        now = _now()
        queued_rows = await combat_zone_crud.list_queued_with_owners(db_session)
        queued = [
            CombatZoneLobbyParty(
                party_id=party.id,
                vault_number=vault.number,
                dweller_name=dweller.display_name,
                level=dweller.level,
                power=combat_power(dweller),
                stance=party.stance,
                queued_seconds=max(0, int((now - party.arrives_at).total_seconds())) if party.arrives_at else 0,
            )
            for party, dweller, vault in queued_rows
        ]

        active = await combat_zone_crud.list_active_matches(db_session)
        active_matches = [
            CombatZoneMatchSummary(
                match_id=match.id,
                vault_a_number=match.party_a_vault_number,
                vault_b_number=match.party_b_vault_number,
                dweller_a_name=match.party_a_name,
                dweller_b_name=match.party_b_name,
                pot_caps=match.pot_caps,
                round_seq=match.round_seq,
                started_at=match.started_at,
            )
            for match in active
        ]

        return CombatZoneLobbyRead(
            enabled=True,
            server_time=now,
            entry_fee_caps=game_config.combat_zone.entry_fee_caps,
            travel_seconds=game_config.combat_zone.travel_seconds,
            queued=queued,
            active_matches=active_matches,
        )

    async def get_match(self, db_session: AsyncSession, match_id: UUID4) -> CombatZoneMatchRead:
        self._ensure_enabled()
        match = await combat_zone_crud.get_match(db_session, match_id)
        if match is None:
            raise NotFoundException("Match not found.")

        parties = {
            party.id: party
            for party in await combat_zone_crud.get_parties(db_session, [match.party_a_id, match.party_b_id])
        }
        dweller_ids = [
            dweller_id for dweller_id in (match.party_a_dweller_id, match.party_b_dweller_id) if dweller_id is not None
        ]
        dwellers = {
            dweller.id: dweller for dweller in await combat_zone_crud.get_dwellers_by_ids(db_session, dweller_ids)
        }
        party_a = parties.get(match.party_a_id)
        party_b = parties.get(match.party_b_id)
        if party_a is None or party_b is None:
            raise NotFoundException("Match participants are no longer available.")

        events = await combat_zone_crud.list_events(db_session, match_id)
        return CombatZoneMatchRead(
            id=match.id,
            status=match.status.value,
            round_seq=match.round_seq,
            next_attack_party=match.next_attack_party,
            pot_caps=match.pot_caps,
            finish_reason=match.finish_reason,
            started_at=match.started_at,
            finished_at=match.finished_at,
            max_ends_at=match.max_ends_at,
            party_a=self._match_party_read(match, party_a, dwellers.get(match.party_a_dweller_id), "A"),
            party_b=self._match_party_read(match, party_b, dwellers.get(match.party_b_dweller_id), "B"),
            events=[
                CombatZoneEventRead(
                    id=event.id,
                    round_seq=event.round_seq,
                    kind=event.kind,
                    message=event.message,
                    created_at=event.created_at,
                )
                for event in events
            ],
        )

    async def get_events(
        self, db_session: AsyncSession, match_id: UUID4, after_seq: int | None = None
    ) -> list[CombatZoneEventRead]:
        self._ensure_enabled()
        if await combat_zone_crud.get_match(db_session, match_id) is None:
            raise NotFoundException("Match not found.")
        events = await combat_zone_crud.list_events(db_session, match_id, after_seq)
        return [
            CombatZoneEventRead(
                id=event.id,
                round_seq=event.round_seq,
                kind=event.kind,
                message=event.message,
                created_at=event.created_at,
            )
            for event in events
        ]

    # -- Commands -----------------------------------------------------------------

    async def send_party(self, db_session: AsyncSession, vault_id: UUID4, dweller_id: UUID4) -> CombatZonePartyRead:
        self._ensure_enabled()
        now = _now()

        party = await combat_zone_crud.get_party_by_vault_for_update(db_session, vault_id)
        if party is not None and party.status != CombatZonePartyStatus.HOME:
            raise ResourceConflictException("This vault already has a party in the Combat Zone.")

        dweller = await combat_zone_crud.get_dweller_for_update(db_session, dweller_id)
        if dweller is None or dweller.is_deleted or dweller.vault_id != vault_id:
            raise NotFoundException("Dweller not found in this vault.")
        dead_lifecycles = (
            LifecycleEnum.DEAD_REVIVABLE,
            LifecycleEnum.DEAD_PERMANENT,
            LifecycleEnum.WASTELAND,
        )
        if dweller.is_dead or dweller.lifecycle in dead_lifecycles:
            raise ValidationException("Only a living, vault-affiliated dweller can be sent to the Combat Zone.")
        if not dweller.is_mature:
            raise ValidationException("Only an adult or elder can be sent to the Combat Zone.")
        if dweller.status not in SENDABLE_STATUSES:
            raise ValidationException("This dweller is unavailable for a Combat Zone assignment.")
        if await incident_crud.get_active_by_vault(db_session, vault_id):
            raise ResourceConflictException("Resolve the vault incident before sending a party.")

        # Last lock in the send path so it matches the tick's party -> vault order.
        vault = self._assert_active_vault(await vault_crud.get_for_update(db_session, vault_id))
        fee = game_config.combat_zone.entry_fee_caps
        if vault.bottle_caps < fee:
            raise ValidationException(f"Sending a party requires {fee} bottle caps.")

        vault.bottle_caps -= fee
        if party is None:
            party = CombatZoneParty(vault_id=vault_id, dweller_id=dweller.id)
            db_session.add(party)

        party.dweller_id = dweller.id
        party.origin_room_id = dweller.room_id
        party.status = CombatZonePartyStatus.TRAVELING
        party.stance = CombatZoneStance.DEFENSIVE
        party.stance_updated_at = now
        party.arrives_at = now + timedelta(seconds=game_config.combat_zone.travel_seconds)
        party.escrow_caps = fee

        # Reuse FIGHTING: the dweller is in combat, just off-vault. This service is
        # the only writer while deployed and restores the posting on return.
        dweller.status = DwellerStatusEnum.FIGHTING
        dweller.room_id = None
        db_session.add(vault)
        db_session.add(dweller)
        db_session.add(party)
        await db_session.commit()
        await db_session.refresh(party)
        request_combat_zone_tick()
        return await self._party_read(db_session, party)

    async def recall_party(self, db_session: AsyncSession, vault_id: UUID4) -> CombatZonePartyRead:
        self._ensure_enabled()
        now = _now()
        party = self._assert_party(
            await combat_zone_crud.get_party_by_vault_for_update(db_session, vault_id),
            statuses=(
                CombatZonePartyStatus.TRAVELING,
                CombatZonePartyStatus.QUEUED,
                CombatZonePartyStatus.IN_MATCH,
            ),
        )

        if party.status == CombatZonePartyStatus.IN_MATCH:
            party.stance = CombatZoneStance.RETREAT
            party.stance_updated_at = now
            db_session.add(party)
            await db_session.commit()
            await db_session.refresh(party)
            return await self._party_read(db_session, party)

        if party.escrow_caps:
            await combat_zone_engine.credit_vault(db_session, party.vault_id, party.escrow_caps)
            party.escrow_caps = 0
        party.status = CombatZonePartyStatus.RETURNING
        party.arrives_at = now + timedelta(seconds=game_config.combat_zone.travel_seconds)
        party.stance = CombatZoneStance.DEFENSIVE
        party.stance_updated_at = now
        db_session.add(party)
        await db_session.commit()
        await db_session.refresh(party)
        return await self._party_read(db_session, party)

    async def set_stance(
        self, db_session: AsyncSession, vault_id: UUID4, stance: CombatZoneStance
    ) -> CombatZonePartyRead:
        self._ensure_enabled()
        party = self._assert_party(
            await combat_zone_crud.get_party_by_vault_for_update(db_session, vault_id),
            statuses=(CombatZonePartyStatus.QUEUED, CombatZonePartyStatus.IN_MATCH),
        )
        party.stance = stance
        party.stance_updated_at = _now()
        db_session.add(party)
        await db_session.commit()
        await db_session.refresh(party)
        return await self._party_read(db_session, party)

    async def challenge(self, db_session: AsyncSession, vault_id: UUID4, target_party_id: UUID4) -> CombatZoneMatchRead:
        self._ensure_enabled()
        async with db_locks.hold_advisory_lock(db_session, TICK_LOCK_KEY) as acquired:
            if not acquired:
                raise ResourceConflictException("The Combat Zone is busy; retry in a moment.")

            attacker = self._assert_party(
                await combat_zone_crud.get_party_by_vault_for_update(db_session, vault_id),
                statuses=(CombatZonePartyStatus.QUEUED,),
            )
            target = self._assert_party(
                await combat_zone_crud.get_party_for_update(db_session, target_party_id),
                statuses=(CombatZonePartyStatus.QUEUED,),
            )
            if target.vault_id == attacker.vault_id:
                raise ValidationException("A vault cannot challenge its own party.")

            match = await combat_zone_engine.create_match(db_session, attacker, target, _now())
            if match is None:
                raise ResourceConflictException("One of the parties is no longer queued.")
            await db_session.commit()
            match_id = match.id
        request_combat_zone_tick()
        return await self.get_match(db_session, match_id)

    # -- Tick ---------------------------------------------------------------------

    async def process_ticks(
        self, db_session: AsyncSession, seconds_passed: int | None = None, now: datetime | None = None
    ) -> CombatZoneTickStats:
        return await combat_zone_engine.process(db_session, seconds_passed, now)

    # -- Internal helpers ---------------------------------------------------------

    async def _party_read(self, db_session: AsyncSession, party: CombatZoneParty) -> CombatZonePartyRead:
        rows = await combat_zone_crud.list_parties_with_owners(db_session, [party.id])
        if not rows:
            raise NotFoundException("Party participant no longer exists.")
        _party, dweller, vault = rows[0]
        return CombatZonePartyRead(
            id=party.id,
            vault_id=party.vault_id,
            vault_number=vault.number,
            dweller_id=dweller.id,
            dweller_name=dweller.display_name,
            level=dweller.level,
            health=dweller.health,
            max_health=dweller.effective_max_health,
            power=combat_power(dweller),
            status=party.status,
            stance=party.stance,
            arrives_at=party.arrives_at,
            escrow_caps=party.escrow_caps,
        )

    @staticmethod
    def _match_party_read(
        match: CombatZoneMatch,
        party: CombatZoneParty,
        dweller: Dweller | None,
        side: str,
    ) -> CombatZoneMatchPartyRead:
        if side == "A":
            dweller_id = match.party_a_dweller_id
            name = match.party_a_name
            vault_number = match.party_a_vault_number
        else:
            dweller_id = match.party_b_dweller_id
            name = match.party_b_name
            vault_number = match.party_b_vault_number

        return CombatZoneMatchPartyRead(
            party_id=party.id,
            vault_id=party.vault_id,
            vault_number=vault_number,
            dweller_id=dweller_id,
            dweller_name=dweller.display_name if dweller is not None else name,
            level=dweller.level if dweller is not None else 0,
            health=dweller.health if dweller is not None else 1,
            max_health=dweller.effective_max_health if dweller is not None else 1,
            power=combat_power(dweller) if dweller is not None else 0.0,
            stance=party.stance,
            is_winner=match.winner_party_id == party.id,
        )


combat_zone_service = CombatZoneService()
