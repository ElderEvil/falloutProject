"""Combat Zone service — commands, reads, and the transaction boundary.

Tick mechanics (travel, pairing, rounds, settlement) live in
``combat_zone_engine``. This module owns the HTTP-facing surface: one public
operation, one transaction, domain exceptions, and the views the API returns.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.core import db_locks
from app.core.combat_zone_dispatch import request_combat_zone_tick
from app.core.enums import (
    CombatZoneMatchStatus,
    CombatZonePartyStatus,
    CombatZoneStance,
    DwellerStatusEnum,
    LifecycleEnum,
)
from app.core.game_config import game_config
from app.crud import vault as vault_crud
from app.crud.combat_zone import combat_zone_crud
from app.crud.incident import incident_crud
from app.models.combat_zone import CombatZoneEvent, CombatZoneMatch, CombatZoneParty
from app.schemas.arena import ArenaFighter
from app.schemas.combat_zone import (
    CombatZoneCursor,
    CombatZoneEventRead,
    CombatZoneHistoryEntry,
    CombatZoneLobbyParty,
    CombatZoneLobbyRead,
    CombatZoneMatchPartyRead,
    CombatZoneMatchRead,
    CombatZoneMatchSummary,
    CombatZonePartyRead,
)
from app.services.combat.arena_participants import fighter_view, participant_from_dweller
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
from app.utils.time import utcnow

if TYPE_CHECKING:
    from uuid import UUID

    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller
    from app.models.vault import Vault

logger = logging.getLogger(__name__)

SENDABLE_STATUSES = (DwellerStatusEnum.IDLE, DwellerStatusEnum.WORKING)


def _now() -> datetime:
    return utcnow()


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


def _event_read(event: CombatZoneEvent) -> CombatZoneEventRead:
    return CombatZoneEventRead(
        id=event.id,
        sequence=event.sequence,
        round_seq=event.round_seq,
        kind=event.kind,
        message=event.message,
        action=event.action,
        created_at=event.created_at,
    )


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

    async def get_party(self, db_session: AsyncSession, vault_id: UUID) -> CombatZonePartyRead | None:
        vault = await vault_crud.get_or_none(db_session, vault_id)
        if vault is None:
            raise NotFoundException("Vault not found.")
        party = await combat_zone_crud.get_party_by_vault(db_session, vault_id)
        if party is None:
            return None
        return await self._party_read(db_session, party)

    async def get_lobby(self, db_session: AsyncSession) -> CombatZoneLobbyRead:
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
                queued_seconds=max(0, int((now - _aware(party.arrives_at)).total_seconds())) if party.arrives_at else 0,
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
            enabled=game_config.combat_zone.enabled,
            server_time=now,
            entry_fee_caps=game_config.combat_zone.entry_fee_caps,
            travel_seconds=game_config.combat_zone.travel_seconds,
            queued=queued,
            active_matches=active_matches,
        )

    async def _readable_match(
        self, db_session: AsyncSession, match_id: UUID, viewer_user_id: UUID | None
    ) -> tuple[CombatZoneMatch, CombatZoneParty, CombatZoneParty]:
        match = await combat_zone_crud.get_match(db_session, match_id)
        if match is None:
            raise NotFoundException("Match not found.")
        parties = {
            party.id: party
            for party in await combat_zone_crud.get_parties(db_session, [match.party_a_id, match.party_b_id])
        }
        party_a = parties.get(match.party_a_id)
        party_b = parties.get(match.party_b_id)
        if party_a is None or party_b is None:
            raise NotFoundException("Match participants are no longer available.")
        if match.status == CombatZoneMatchStatus.FINISHED:
            owner_ids = set()
            for party in (party_a, party_b):
                vault = await vault_crud.get_or_none(db_session, party.vault_id)
                if vault is not None and vault.user_id is not None:
                    owner_ids.add(vault.user_id)
            if viewer_user_id not in owner_ids:
                raise NotFoundException("Match not found.")
        return match, party_a, party_b

    async def _begin_read_snapshot(self, db_session: AsyncSession) -> bool:
        if db_session.get_bind().dialect.name != "postgresql":
            return False
        await db_session.rollback()
        await db_session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        return True

    async def get_match(
        self, db_session: AsyncSession, match_id: UUID, viewer_user_id: UUID | None = None
    ) -> CombatZoneMatchRead:
        snapshotted = await self._begin_read_snapshot(db_session)
        match, party_a, party_b = await self._readable_match(db_session, match_id, viewer_user_id)
        dwellers = {}
        if match.status != CombatZoneMatchStatus.FINISHED:
            dweller_ids = [
                dweller_id
                for dweller_id in (match.party_a_dweller_id, match.party_b_dweller_id)
                if dweller_id is not None
            ]
            dwellers = {
                dweller.id: dweller for dweller in await combat_zone_crud.get_dwellers_by_ids(db_session, dweller_ids)
            }
        events = await combat_zone_crud.list_events(db_session, match_id)
        view = CombatZoneMatchRead(
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
            events=[_event_read(event) for event in events],
            cursor=CombatZoneCursor(
                sequence=events[-1].sequence if events else 0,
                round_seq=match.round_seq,
                status=match.status.value,
            ),
        )
        if snapshotted:
            await db_session.rollback()
        return view

    async def get_events(
        self,
        db_session: AsyncSession,
        match_id: UUID,
        after_sequence: int | None = None,
        viewer_user_id: UUID | None = None,
    ) -> list[CombatZoneEventRead]:
        snapshotted = await self._begin_read_snapshot(db_session)
        await self._readable_match(db_session, match_id, viewer_user_id)
        events = await combat_zone_crud.list_events(db_session, match_id, after_sequence)
        result = [_event_read(event) for event in events]
        if snapshotted:
            await db_session.rollback()
        return result

    async def history(
        self, db_session: AsyncSession, vault_id: UUID, *, limit: int = 20
    ) -> list[CombatZoneHistoryEntry]:
        """Bounded recent finished bouts involving this vault, newest first."""
        matches = await combat_zone_crud.list_history_for_vault(db_session, vault_id, limit=min(limit, 50))
        entries: list[CombatZoneHistoryEntry] = []
        for match in matches:
            parties = {
                party.id: party
                for party in await combat_zone_crud.get_parties(db_session, [match.party_a_id, match.party_b_id])
            }
            party_a = parties.get(match.party_a_id)
            party_b = parties.get(match.party_b_id)
            if party_a is None or party_b is None:
                continue
            entries.append(
                CombatZoneHistoryEntry(
                    match_id=match.id,
                    finish_reason=match.finish_reason,
                    pot_caps=match.pot_caps,
                    round_seq=match.round_seq,
                    winner_party_id=match.winner_party_id,
                    party_a=self._match_party_read(match, party_a, None, "A"),
                    party_b=self._match_party_read(match, party_b, None, "B"),
                    started_at=match.started_at,
                    finished_at=match.finished_at,
                )
            )
        return entries

    # -- Commands -----------------------------------------------------------------

    async def send_party(self, db_session: AsyncSession, vault_id: UUID, dweller_id: UUID) -> CombatZonePartyRead:
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

        if party is None:
            # The vault row lock serializes concurrent first sends; re-read now so the
            # loser returns a domain conflict instead of surfacing a unique-constraint error.
            if await combat_zone_crud.get_party_by_vault(db_session, vault_id) is not None:
                raise ResourceConflictException("This vault already has a party in the Combat Zone.")
            party = CombatZoneParty(vault_id=vault_id, dweller_id=dweller.id)
            db_session.add(party)

        vault.bottle_caps -= fee

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

    async def recall_party(self, db_session: AsyncSession, vault_id: UUID) -> CombatZonePartyRead:
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
        self, db_session: AsyncSession, vault_id: UUID, stance: CombatZoneStance
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

    async def challenge(self, db_session: AsyncSession, vault_id: UUID, target_party_id: UUID) -> CombatZoneMatchRead:
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
            challenger_vault = await vault_crud.get_or_none(db_session, attacker.vault_id)
            if challenger_vault is None or challenger_vault.user_id is None:
                raise ResourceConflictException("The challenging vault is no longer available.")
            match = await combat_zone_engine.create_match(db_session, attacker, target, _now())
            if match is None:
                raise ResourceConflictException("One of the parties is no longer queued.")
            await db_session.commit()
            match_id = match.id
            challenger_user_id = challenger_vault.user_id
        request_combat_zone_tick()
        return await self.get_match(db_session, match_id, viewer_user_id=challenger_user_id)

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
            level = match.party_a_level
            power = match.party_a_power
            age_group = match.party_a_age_group
            race = match.party_a_race
            health = match.party_a_health
            max_health = match.party_a_max_health
            credited = match.party_a_credited_caps
        else:
            dweller_id = match.party_b_dweller_id
            name = match.party_b_name
            vault_number = match.party_b_vault_number
            level = match.party_b_level
            power = match.party_b_power
            age_group = match.party_b_age_group
            race = match.party_b_race
            health = match.party_b_health
            max_health = match.party_b_max_health
            credited = match.party_b_credited_caps

        if dweller is not None and match.status != CombatZoneMatchStatus.FINISHED:
            fighter = fighter_view(participant_from_dweller(dweller)).model_copy(
                update={"active_skill": None, "pet": None}
            )
        else:
            fighter = ArenaFighter(
                id=str(dweller_id or party.id),
                name=name,
                level=level or 0,
                health=health if health is not None else 0,
                max_health=max_health if max_health is not None else 1,
                power=power or 0.0,
                age_group=age_group,
                race=race,
            )

        stance = party.stance
        if match.status == CombatZoneMatchStatus.FINISHED:
            stored_stance = match.party_a_stance if side == "A" else match.party_b_stance
            if stored_stance is not None:
                stance = CombatZoneStance(stored_stance)

        return CombatZoneMatchPartyRead(
            fighter=fighter,
            party_id=party.id,
            vault_id=party.vault_id,
            vault_number=vault_number,
            dweller_id=dweller_id,
            stance=stance,
            is_winner=match.winner_party_id == party.id,
            credited_caps=credited,
        )


combat_zone_service = CombatZoneService()
