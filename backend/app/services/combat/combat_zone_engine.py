"""Combat Zone match engine: travel, pairing, rounds, and escrow settlement.

The engine is the only writer of match/party lifecycle state. It runs one step per
actor tick under the process-wide advisory lock; the public ``CombatZoneService``
owns the HTTP-facing command/read surface and delegates here for tick work.

A match snapshots its participants (dweller id, display name, vault number) when it
is created: party rows are reused on the next send, so reading history through the
party's current dweller would rewrite finished matches.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING

from app.core import db_locks
from app.core.enums import (
    CombatZoneMatchStatus,
    CombatZonePartyStatus,
    CombatZoneStance,
    DwellerStatusEnum,
    NotificationType,
)
from app.core.game_config import game_config
from app.crud import vault as vault_crud
from app.crud.combat_zone import combat_zone_crud
from app.crud.dweller import determine_status_for_room
from app.models.combat_zone import CombatZoneEvent, CombatZoneMatch, CombatZoneParty
from app.services.combat.arena_participants import participant_from_dweller
from app.services.combat.attack_service import resolve_attacks
from app.services.notification_service import NotificationService
from app.services.room_assignment_policy import validate_room_worker_capacity
from app.utils.combat import combat_power
from app.utils.exceptions import ResourceConflictException
from app.utils.time import utcnow

if TYPE_CHECKING:
    from pydantic import UUID4
    from sqlmodel.ext.asyncio.session import AsyncSession

    from app.models.dweller import Dweller

logger = logging.getLogger(__name__)

TICK_LOCK_KEY = "combat-zone-tick"
STANCE_MULTIPLIERS: dict[CombatZoneStance, tuple[float, float]] = {
    CombatZoneStance.AGGRESSIVE: (1.25, 1.15),
    CombatZoneStance.DEFENSIVE: (0.80, 0.75),
    CombatZoneStance.FOCUS: (1.10, 1.00),
    CombatZoneStance.RETREAT: (0.50, 0.60),
}


@dataclass(frozen=True)
class CombatZoneTickStats:
    """One actor tick's outcome; ``skipped`` explains a no-op tick."""

    matches: int = 0
    paired: int = 0
    arrived: int = 0
    returned: int = 0
    pending: int = 0
    skipped: str | None = None


def _aware(value: datetime) -> datetime:
    return value if value.tzinfo is not None else value.replace(tzinfo=UTC)


class CombatZoneTickEngine:
    """Resolve party movement, pairing, and one micro-round per call."""

    async def process(
        self, db_session: AsyncSession, seconds_passed: int | None = None, now: datetime | None = None
    ) -> CombatZoneTickStats:
        current = _aware(now) if now is not None else utcnow()
        seconds = seconds_passed or game_config.combat_zone.tick_seconds
        disabled = not game_config.combat_zone.enabled
        async with db_locks.hold_advisory_lock(db_session, TICK_LOCK_KEY) as acquired:
            if not acquired:
                return CombatZoneTickStats(skipped="locked")

            try:
                await self._drain_unavailable(db_session, current, global_disabled=disabled)
                returned = await self._advance_returns(db_session, current)
                arrived = 0 if disabled else await self._advance_arrivals(db_session, current)

                # Snapshot live matches before pairing so a match created now gets a
                # full stance window instead of losing its first round immediately.
                matches = list(await combat_zone_crud.list_active_matches(db_session))
                paired = 0
                resolved = 0
                if disabled:
                    for match in matches:
                        await self._finish_match(db_session, match, None, "draw", current)
                        resolved += 1
                else:
                    paired = await self._pair_queued(db_session, current)
                    for match in matches:
                        if await self._resolve_round(db_session, match, current, seconds):
                            resolved += 1

                pending = await self._pending_count(db_session)
                await db_session.commit()
            except Exception:
                NotificationService.discard_deferred_notifications(db_session)
                await db_session.rollback()
                raise
            await NotificationService.deliver_deferred_notifications(db_session)
            return CombatZoneTickStats(
                matches=resolved,
                paired=paired,
                arrived=arrived,
                returned=returned,
                pending=pending,
                skipped="disabled" if disabled and pending else None,
            )

    async def create_match(
        self, db_session: AsyncSession, first: CombatZoneParty, second: CombatZoneParty, now: datetime
    ) -> CombatZoneMatch | None:
        """Pair two queued parties, snapshotting both participants."""
        locked_first = await combat_zone_crud.get_party_for_update(db_session, first.id)
        locked_second = await combat_zone_crud.get_party_for_update(db_session, second.id)
        if (
            locked_first is None
            or locked_second is None
            or locked_first.status != CombatZonePartyStatus.QUEUED
            or locked_second.status != CombatZonePartyStatus.QUEUED
            or locked_first.vault_id == locked_second.vault_id
        ):
            return None

        dweller_a = await combat_zone_crud.get_dweller_for_update(db_session, locked_first.dweller_id)
        dweller_b = await combat_zone_crud.get_dweller_for_update(db_session, locked_second.dweller_id)
        vault_a = await vault_crud.get_or_none(db_session, locked_first.vault_id)
        vault_b = await vault_crud.get_or_none(db_session, locked_second.vault_id)
        if dweller_a is None or dweller_b is None:
            return None
        if dweller_a.is_dead or dweller_b.is_dead or dweller_a.is_deleted or dweller_b.is_deleted:
            return None
        if vault_a is None or vault_b is None:
            return None

        config = game_config.combat_zone
        first, second = locked_first, locked_second
        first.status = CombatZonePartyStatus.IN_MATCH
        second.status = CombatZonePartyStatus.IN_MATCH
        first.arrives_at = None
        second.arrives_at = None
        first.stance_updated_at = now
        second.stance_updated_at = now

        match = CombatZoneMatch(
            party_a_id=first.id,
            party_b_id=second.id,
            party_a_dweller_id=dweller_a.id,
            party_b_dweller_id=dweller_b.id,
            party_a_name=dweller_a.display_name[:64],
            party_b_name=dweller_b.display_name[:64],
            party_a_vault_number=vault_a.number,
            party_b_vault_number=vault_b.number,
            party_a_level=dweller_a.level,
            party_b_level=dweller_b.level,
            party_a_power=combat_power(dweller_a),
            party_b_power=combat_power(dweller_b),
            party_a_age_group=dweller_a.age_group.value,
            party_b_age_group=dweller_b.age_group.value,
            party_a_race=(dweller_a.visual_attributes or {}).get("race"),
            party_b_race=(dweller_b.visual_attributes or {}).get("race"),
            status=CombatZoneMatchStatus.ACTIVE,
            next_attack_party="A",
            round_seq=1,
            pot_caps=first.escrow_caps + second.escrow_caps,
            started_at=now,
            max_ends_at=now + timedelta(seconds=config.match_max_seconds),
        )
        db_session.add_all([first, second, match])
        await db_session.flush()
        await self._add_event(db_session, match, 1, "system", "Parties enter the Combat Zone. The signal goes live.")
        return match

    # -- Movement ----------------------------------------------------------------

    async def _drain_unavailable(self, db_session: AsyncSession, now: datetime, *, global_disabled: bool) -> int:
        """Refund and return travelling or queued parties while the Zone is off."""
        if not global_disabled:
            return 0
        candidates: list[CombatZoneParty] = []
        for status in (CombatZonePartyStatus.TRAVELING, CombatZonePartyStatus.QUEUED):
            candidates.extend(await combat_zone_crud.list_by_status(db_session, status))
        drained = 0
        for candidate in candidates:
            if await self._cancel_party(db_session, candidate.id, now):
                drained += 1
        return drained

    async def _advance_returns(self, db_session: AsyncSession, now: datetime) -> int:
        due = await combat_zone_crud.list_due_parties(db_session, CombatZonePartyStatus.RETURNING, now)
        advanced = 0
        for candidate in due:
            if await self._finalize_return(db_session, candidate.id, now):
                advanced += 1
        return advanced

    async def _advance_arrivals(self, db_session: AsyncSession, now: datetime) -> int:
        due = await combat_zone_crud.list_due_parties(db_session, CombatZonePartyStatus.TRAVELING, now)
        advanced = 0
        for candidate in due:
            party = await combat_zone_crud.get_party_for_update(db_session, candidate.id)
            if party is None or party.status != CombatZonePartyStatus.TRAVELING:
                continue
            party.status = CombatZonePartyStatus.QUEUED
            party.stance = CombatZoneStance.DEFENSIVE
            party.stance_updated_at = now
            db_session.add(party)
            advanced += 1
        await db_session.flush()
        return advanced

    async def _finalize_return(self, db_session: AsyncSession, party_id: UUID4, now: datetime) -> bool:
        party = await combat_zone_crud.get_party_for_update(db_session, party_id)
        if party is None or party.status != CombatZonePartyStatus.RETURNING:
            return False
        dweller = await combat_zone_crud.get_dweller_for_update(db_session, party.dweller_id)
        if (
            dweller is not None
            and not dweller.is_deleted
            and not dweller.is_dead
            and dweller.status == DwellerStatusEnum.FIGHTING
        ):
            await self._restore_dweller_posting(db_session, dweller, party.origin_room_id)
            db_session.add(dweller)

        party.status = CombatZonePartyStatus.HOME
        party.origin_room_id = None
        party.arrives_at = None
        party.stance = CombatZoneStance.DEFENSIVE
        party.stance_updated_at = now
        party.escrow_caps = 0
        db_session.add(party)
        return True

    async def _restore_dweller_posting(
        self, db_session: AsyncSession, dweller: Dweller, origin_room_id: UUID4 | None
    ) -> None:
        """Restore the pre-send room unless another assignment already claimed the dweller."""
        if dweller.room_id is not None:
            room = await combat_zone_crud.get_room(db_session, dweller.room_id)
            dweller.status = determine_status_for_room(room.category if room else None, room.name if room else None)
            return
        if origin_room_id is not None:
            room = await combat_zone_crud.get_room(db_session, origin_room_id)
            if room is not None:
                try:
                    await validate_room_worker_capacity(db_session, room)
                except ResourceConflictException:
                    # Another assignment filled the room while the fighter was away. The
                    # return is not allowed to overfill it; the dweller waits idle instead.
                    dweller.status = DwellerStatusEnum.IDLE
                    return
                dweller.room_id = room.id
                dweller.status = determine_status_for_room(room.category, room.name)
                return
        dweller.status = DwellerStatusEnum.IDLE

    # -- Pairing -----------------------------------------------------------------

    async def _pair_queued(self, db_session: AsyncSession, now: datetime) -> int:
        queued = list(await combat_zone_crud.list_queued(db_session))
        if not queued:
            return 0

        rows = await combat_zone_crud.list_parties_with_owners(db_session, [party.id for party in queued])
        owners = {party.id: dweller for party, dweller, _vault in rows}
        power = {
            party_id: combat_power(dweller)
            for party_id, dweller in owners.items()
            if not dweller.is_deleted and not dweller.is_dead
        }

        for party in queued:
            dweller = owners.get(party.id)
            if dweller is None or dweller.is_deleted or dweller.is_dead:
                await self._cancel_party(db_session, party.id, now)

        if len(queued) < 2:
            return 0

        paired = 0
        for index, first in enumerate(queued):
            if first.status != CombatZonePartyStatus.QUEUED:
                continue
            for candidate in queued[index + 1 :]:
                if candidate.status != CombatZonePartyStatus.QUEUED:
                    continue
                if candidate.vault_id == first.vault_id:
                    continue
                if not self._power_compatible(power.get(first.id, 0), power.get(candidate.id, 0)):
                    continue
                if await self.create_match(db_session, first, candidate, now) is not None:
                    paired += 1
                    break
        return paired

    async def _cancel_party(self, db_session: AsyncSession, party_id: UUID4, now: datetime) -> bool:
        """Return a party that can no longer fight, refunding its fee."""
        party = await combat_zone_crud.get_party_for_update(db_session, party_id)
        if party is None or party.status not in (CombatZonePartyStatus.TRAVELING, CombatZonePartyStatus.QUEUED):
            return False
        if party.escrow_caps:
            await self.credit_vault(db_session, party.vault_id, party.escrow_caps)
            party.escrow_caps = 0
        party.status = CombatZonePartyStatus.RETURNING
        party.arrives_at = now + timedelta(seconds=game_config.combat_zone.travel_seconds)
        party.stance = CombatZoneStance.DEFENSIVE
        party.stance_updated_at = now
        db_session.add(party)
        return True

    @staticmethod
    def _power_compatible(a: float, b: float) -> bool:
        tolerance = game_config.combat_zone.auto_match_power_tolerance
        if tolerance <= 0:
            return a == b
        return abs(a - b) / max(a, b, 1e-9) <= tolerance

    async def _pending_count(self, db_session: AsyncSession) -> int:
        parties = await combat_zone_crud.count_unfinished_parties(db_session)
        matches = await combat_zone_crud.list_active_matches(db_session)
        return parties + len(matches)

    # -- Rounds ------------------------------------------------------------------

    async def _resolve_round(
        self, db_session: AsyncSession, match: CombatZoneMatch, now: datetime, seconds: int
    ) -> bool:
        locked = await combat_zone_crud.get_match_for_update(db_session, match.id)
        if locked is None or locked.status != CombatZoneMatchStatus.ACTIVE:
            return False
        match = locked

        party_a = await combat_zone_crud.get_party_for_update(db_session, match.party_a_id)
        party_b = await combat_zone_crud.get_party_for_update(db_session, match.party_b_id)
        if party_a is None or party_b is None:
            await self._finish_match(db_session, match, None, "draw", now)
            return True

        dweller_a = await combat_zone_crud.get_dweller_for_update(db_session, party_a.dweller_id)
        dweller_b = await combat_zone_crud.get_dweller_for_update(db_session, party_b.dweller_id)

        if dweller_a is None or dweller_a.is_dead or dweller_b is None or dweller_b.is_dead:
            winner = party_a if dweller_b is None or dweller_b.is_dead else party_b
            if (dweller_a is None or dweller_a.is_dead) and (dweller_b is None or dweller_b.is_dead):
                winner = None
            await self._finish_match(db_session, match, winner, "victory" if winner else "draw", now)
            return True

        stance_a = self._effective_stance(party_a, now)
        stance_b = self._effective_stance(party_b, now)
        db_session.add_all([party_a, party_b])

        retreat_a = self._retreating_party(party_a, now)
        retreat_b = self._retreating_party(party_b, now)
        forfeiting = self._retreat_forfeit(retreat_a, retreat_b)
        if forfeiting is not None:
            winner = party_b if forfeiting is party_a else party_a
            await self._add_event(
                db_session,
                match,
                match.round_seq,
                "system",
                f"{forfeiting.stance.value.title()} order stands too long — {winner.stance.value} takes the pot.",
            )
            await self._finish_match(db_session, match, winner, "retreat", now)
            return True

        if match.max_ends_at is not None and now >= match.max_ends_at:
            winner = self._hp_winner(party_a, dweller_a, party_b, dweller_b)
            await self._finish_match(db_session, match, winner, "timeout", now)
            return True

        attacker_is_a = match.next_attack_party == "A"
        attacker_party, attacker = (party_a, dweller_a) if attacker_is_a else (party_b, dweller_b)
        defender, defender_stance = (dweller_b, stance_b) if attacker_is_a else (dweller_a, stance_a)
        attacker_stance = stance_a if attacker_is_a else stance_b

        attacker_participant = participant_from_dweller(attacker)
        defender_participant = participant_from_dweller(defender)
        carry = dict(match.carry or {})
        resolved = resolve_attacks(
            [attacker_participant],
            [defender_participant],
            seconds,
            set(),
            carry,
            damage_multiplier=STANCE_MULTIPLIERS[attacker_stance][0] * STANCE_MULTIPLIERS[defender_stance][1],
        )
        match.carry = carry
        defender.health = defender_participant.health
        db_session.add_all([defender, match])
        if resolved:
            for attack in resolved:
                await self._add_event(
                    db_session,
                    match,
                    match.round_seq,
                    "hit",
                    " ".join(attack.messages),
                    action=attack.action.model_dump(mode="json"),
                )
        else:
            await self._add_event(
                db_session,
                match,
                match.round_seq,
                "system",
                "No whole damage lands; the fighters circle.",
            )

        if defender.health <= 0:
            await self._finish_match(db_session, match, attacker_party, "victory", now)
            return True

        if match.max_ends_at is not None and now >= match.max_ends_at:
            winner = self._hp_winner(party_a, dweller_a, party_b, dweller_b)
            await self._finish_match(db_session, match, winner, "timeout", now)
            return True

        match.next_attack_party = "B" if attacker_is_a else "A"
        match.round_seq += 1
        db_session.add(match)
        return True

    @staticmethod
    def _effective_stance(party: CombatZoneParty, now: datetime) -> CombatZoneStance:
        """Silence defaults to DEFENSIVE; only an explicit retreat forfeits."""
        if party.stance == CombatZoneStance.RETREAT:
            return CombatZoneStance.RETREAT
        grace = game_config.combat_zone.disconnect_grace_seconds
        if now - _aware(party.stance_updated_at) > timedelta(seconds=grace):
            if party.stance != CombatZoneStance.DEFENSIVE:
                party.stance = CombatZoneStance.DEFENSIVE
                party.stance_updated_at = now
            return CombatZoneStance.DEFENSIVE
        return party.stance

    @staticmethod
    def _retreating_party(party: CombatZoneParty, now: datetime) -> CombatZoneParty | None:
        if party.stance != CombatZoneStance.RETREAT:
            return None
        forfeit = timedelta(seconds=game_config.combat_zone.retreat_forfeit_seconds)
        return party if now - _aware(party.stance_updated_at) >= forfeit else None

    @staticmethod
    def _retreat_forfeit(
        retreat_a: CombatZoneParty | None, retreat_b: CombatZoneParty | None
    ) -> CombatZoneParty | None:
        """Choose the forfeiting side deterministically when both retreats are due.

        The order that has stood longer forfeits first; the UUID breaks an exact timestamp
        tie so seat order and tick cadence cannot decide the winner.
        """
        if retreat_a is None or retreat_b is None:
            return retreat_a or retreat_b
        return min((retreat_a, retreat_b), key=lambda party: (_aware(party.stance_updated_at), str(party.id)))

    @staticmethod
    def _hp_winner(
        party_a: CombatZoneParty, dweller_a: Dweller, party_b: CombatZoneParty, dweller_b: Dweller
    ) -> CombatZoneParty | None:
        if dweller_a.health == dweller_b.health:
            return None
        return party_a if dweller_a.health > dweller_b.health else party_b

    # -- Settlement --------------------------------------------------------------

    async def _finish_match(
        self,
        db_session: AsyncSession,
        match: CombatZoneMatch,
        winner: CombatZoneParty | None,
        reason: str,
        now: datetime,
    ) -> None:
        """Terminal transition; idempotent because a finished match returns immediately."""
        locked = await combat_zone_crud.get_match_for_update(db_session, match.id)
        if locked is None or locked.status != CombatZoneMatchStatus.ACTIVE:
            return
        match = locked

        config = game_config.combat_zone
        party_a = await combat_zone_crud.get_party_for_update(db_session, match.party_a_id)
        party_b = await combat_zone_crud.get_party_for_update(db_session, match.party_b_id)
        parties = [party for party in (party_a, party_b) if party is not None]

        dwellers: dict[UUID4, Dweller] = {}
        for party in parties:
            dweller = await combat_zone_crud.get_dweller_for_update(db_session, party.dweller_id)
            if dweller is not None:
                dwellers[party.id] = dweller

        dweller_a = dwellers.get(party_a.id) if party_a is not None else None
        dweller_b = dwellers.get(party_b.id) if party_b is not None else None
        if dweller_a is not None:
            match.party_a_health = dweller_a.health
            match.party_a_max_health = dweller_a.effective_max_health
        if dweller_b is not None:
            match.party_b_health = dweller_b.health
            match.party_b_max_health = dweller_b.effective_max_health

        match.party_a_stance = party_a.stance.value if party_a is not None else None
        match.party_b_stance = party_b.stance.value if party_b is not None else None

        credited: dict[UUID4, int] = {}
        if winner is not None:
            credited[winner.id] = await self.credit_vault(db_session, winner.vault_id, match.pot_caps)
        else:
            for party in parties:
                if party.escrow_caps:
                    credited[party.id] = await self.credit_vault(db_session, party.vault_id, party.escrow_caps)

        for party in parties:
            party.escrow_caps = 0
            party.status = CombatZonePartyStatus.RETURNING
            party.stance = CombatZoneStance.DEFENSIVE
            party.stance_updated_at = now
            party.arrives_at = now + timedelta(seconds=config.travel_seconds)
            db_session.add(party)
            dweller = dwellers.get(party.id)
            if dweller is not None and not dweller.is_deleted:
                # Non-lethal: both leave the Zone at a viable floor, so a bout cannot
                # directly seed a death in the next incident.
                max_health = dweller.effective_max_health
                floor = max(1, (max_health * config.return_health_pct + 99) // 100)
                dweller.health = max(floor, min(dweller.health, max_health))
                db_session.add(dweller)

        match.party_a_credited_caps = credited.get(party_a.id, 0) if party_a is not None else None
        match.party_b_credited_caps = credited.get(party_b.id, 0) if party_b is not None else None
        match.status = CombatZoneMatchStatus.FINISHED
        match.winner_party_id = winner.id if winner is not None else None
        match.finish_reason = reason
        match.finished_at = now
        match.carry = None
        db_session.add(match)

        await self._notify_participants(db_session, match, party_a, party_b, winner, credited)

        if winner is not None:
            message = f"Match over ({reason}). The {credited.get(winner.id, 0)} cap pot goes to the winner."
        else:
            refund_a = credited.get(party_a.id, 0) if party_a is not None else 0
            refund_b = credited.get(party_b.id, 0) if party_b is not None else 0
            message = f"Match over ({reason}). Refunds: {refund_a} + {refund_b} caps."
        await self._add_event(db_session, match, match.round_seq, "finish", message)

    async def _notify_participants(
        self,
        db_session: AsyncSession,
        match: CombatZoneMatch,
        party_a: CombatZoneParty | None,
        party_b: CombatZoneParty | None,
        winner: CombatZoneParty | None,
        credited: dict[UUID4, int],
    ) -> None:
        for party, other_number in (
            (party_a, match.party_b_vault_number),
            (party_b, match.party_a_vault_number),
        ):
            if party is None:
                continue
            vault = await vault_crud.get_or_none(db_session, party.vault_id)
            if vault is None or vault.user_id is None:
                continue
            if winner is None:
                notification_type = NotificationType.COMBAT_DEFEAT
                title = "The Combat Zone: draw"
                message = (
                    f"Your bout against Vault {other_number:03} ended in a draw; "
                    f"{credited.get(party.id, 0)} caps were returned."
                )
            elif winner.id == party.id:
                notification_type = NotificationType.COMBAT_VICTORY
                title = "The Combat Zone: victory"
                message = f"You defeated Vault {other_number:03} and collected {credited.get(party.id, 0)} caps."
            else:
                notification_type = NotificationType.COMBAT_DEFEAT
                title = "The Combat Zone: defeat"
                message = f"Vault {other_number:03} won the bout; your entry fee was lost."
            await NotificationService.create_and_send(
                db_session,
                user_id=vault.user_id,
                notification_type=notification_type,
                title=title,
                message=message,
                vault_id=party.vault_id,
                meta_data={"combat_zone_match_id": str(match.id)},
                commit=False,
            )

    async def credit_vault(self, db_session: AsyncSession, vault_id: UUID4, amount: int) -> int:
        if amount <= 0:
            return 0
        vault = await vault_crud.get_for_update(db_session, vault_id)
        if vault is None:
            logger.warning("Combat Zone payout skipped: vault %s no longer exists", vault_id)
            return 0
        before = vault.bottle_caps
        vault.bottle_caps = min(before + amount, 999_999)
        db_session.add(vault)
        return vault.bottle_caps - before

    async def _add_event(
        self,
        db_session: AsyncSession,
        match: CombatZoneMatch,
        round_seq: int,
        kind: str,
        message: str,
        action: dict[str, object] | None = None,
    ) -> None:
        await db_session.flush()
        next_sequence = await combat_zone_crud.next_event_sequence(db_session, match.id)
        db_session.add(
            CombatZoneEvent(
                match_id=match.id,
                sequence=next_sequence,
                round_seq=round_seq,
                kind=kind,
                message=message[:200],
                action=action,
            )
        )


combat_zone_engine = CombatZoneTickEngine()
