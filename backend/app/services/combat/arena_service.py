"""Arena service — experimental battle playground.

Dwellers are parked in an Arena room, the player picks two of them as
fighters (dweller-vs-dweller mode), then presses FIGHT: a 3-2-1 countdown
elapses before the first combat tick. Combat power mirrors the incident combat
math; each fighter takes damage from the other's power. The first to reach
zero HP loses; the winner gains happiness and XP, the loser loses happiness
and is left standing at 1 HP. The room is marked done and stays stopped until
the fighter selection changes, which resets it for a new match.

This is an experimental feature on branch `experiment/arena`.
"""

import logging
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import db_locks
from app.core.enums import ArenaMode
from app.core.game_config import game_config
from app.crud import dweller as crud_dweller
from app.crud import room as room_crud
from app.crud.arena_match_event import arena_match_event_crud
from app.models.arena_match_event import ArenaMatchEvent
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.arena import (
    ArenaFighter,
    ArenaMatchEventOut,
    ArenaRoomState,
    ArenaRosterEntry,
    ArenaState,
)
from app.utils.combat import combat_power
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

HAPPINESS_WIN = 10
HAPPINESS_LOSE = 10


@dataclass
class ArenaParticipant:
    key: str
    name: str
    short_name: str
    power: float
    health: int
    max_health: int
    is_creature: bool = False
    dweller: Dweller | None = None


def participant_from_dweller(dweller: Dweller) -> ArenaParticipant:
    return ArenaParticipant(
        key=str(dweller.id),
        name=f"{dweller.first_name} {dweller.last_name}",
        short_name=dweller.first_name,
        power=combat_power(dweller),
        health=dweller.health,
        max_health=dweller.effective_max_health,
        dweller=dweller,
    )


class ArenaService:
    """Process arena fights for vaults."""

    def __init__(self) -> None:
        # room_id -> next journal round sequence (in-memory; events are cleared
        # on match reset, so a restart just renumbers, which is cosmetic).
        self._round_seq: dict[str, int] = {}
        # (room_id, dweller_id) -> fractional damage carried between ticks so a
        # 8.7 vs 8.0 power difference shows up instead of truncating both to 8.
        self._damage_carry: dict[tuple[str, str], float] = {}

    async def _get_arena_room(self, db_session: AsyncSession, room_id: UUID4, vault_id: UUID4 | None = None) -> Room:
        rooms = await room_crud.get_arena_rooms(db_session, room_id=room_id, vault_id=vault_id)
        if not rooms:
            raise ValidationException(detail="Arena room not found")
        return rooms[0]

    @staticmethod
    def _team_slot_ids(room: Room) -> tuple[list[UUID4 | None], list[UUID4 | None]]:
        """Slot ids for (team A, team B); a/b are each side's lead across modes."""
        if (room.arena_mode or ArenaMode.DUEL) == ArenaMode.BRAWL:
            return [room.arena_fighter_a_id, room.fighter_c_id], [room.arena_fighter_b_id, room.fighter_d_id]
        return [room.arena_fighter_a_id], [room.arena_fighter_b_id]

    @staticmethod
    def _required_team_size(mode: ArenaMode) -> int:
        return 2 if mode == ArenaMode.BRAWL else 1

    async def set_fighters(
        self,
        db_session: AsyncSession,
        room_id: UUID4,
        fighter_a_id: UUID4 | None,
        fighter_b_id: UUID4 | None,
        vault_id: UUID4 | None = None,
        *,
        mode: ArenaMode = ArenaMode.DUEL,
        fighter_c_id: UUID4 | None = None,
        fighter_d_id: UUID4 | None = None,
    ) -> Room:
        """Pick the dwellers that fight, per mode.

        Duel uses the a/b slots only; brawl fills all four (a/c vs b/d); hunt is
        not available yet. Every provided fighter must be an adult assigned to
        the room. Changing the selection resets any previous match: flags
        cleared, journal wiped, fighters healed.
        """
        room = await self._get_arena_room(db_session, room_id, vault_id)

        if mode == ArenaMode.HUNT:
            raise ValidationException(detail="Hunt mode is not available yet")
        if mode == ArenaMode.DUEL and (fighter_c_id is not None or fighter_d_id is not None):
            raise ValidationException(detail="Duel mode takes exactly two fighters")
        if mode == ArenaMode.BRAWL and None in (fighter_a_id, fighter_b_id, fighter_c_id, fighter_d_id):
            raise ValidationException(detail="Brawl mode needs four fighters")

        selected_ids = [fid for fid in (fighter_a_id, fighter_b_id, fighter_c_id, fighter_d_id) if fid is not None]
        if len(set(selected_ids)) != len(selected_ids):
            raise ValidationException(detail="Fighters must be distinct dwellers")

        if selected_ids:
            fighters = list(await crud_dweller.get_arena_fighters(db_session, room.id, ids=selected_ids))
            if len(fighters) != len(selected_ids):
                raise ValidationException(detail="Every fighter must be an adult dweller assigned to the Arena")
        else:
            fighters = []

        room.arena_fighter_a_id = fighter_a_id
        room.arena_fighter_b_id = fighter_b_id
        room.fighter_c_id = fighter_c_id
        room.fighter_d_id = fighter_d_id
        room.arena_mode = mode
        room.arena_last_fight_at = None
        room.arena_fight_started_at = None
        room_key = str(room.id)
        self._round_seq.pop(room_key, None)
        self._damage_carry = {key: carry for key, carry in self._damage_carry.items() if key[0] != room_key}

        await arena_match_event_crud.delete_for_room(db_session, room.id)

        for fighter in fighters:
            fighter.health = fighter.effective_max_health
            db_session.add(fighter)

        db_session.add(room)
        await db_session.commit()
        return room

    async def get_teams(self, db_session: AsyncSession, room: Room) -> tuple[list[Dweller], list[Dweller]]:
        """Return (team A, team B) in slot order, or ([], []) if the match isn't fully selected."""
        mode = room.arena_mode or ArenaMode.DUEL
        a_slots, b_slots = self._team_slot_ids(room)
        slots = [*a_slots, *b_slots]
        if sum(1 for slot in slots if slot is not None) < self._required_team_size(mode) * 2:
            return [], []

        fighters = await crud_dweller.get_arena_fighters(db_session, room.id, ids=[s for s in slots if s is not None])
        by_id = {str(f.id): f for f in fighters}

        def resolve(team_slots: list[UUID4 | None]) -> list[Dweller]:
            members: list[Dweller] = []
            for slot in team_slots:
                member = by_id.get(str(slot))
                if slot is None or member is None:
                    return []
                members.append(member)
            return members

        team_a = resolve(a_slots)
        team_b = resolve(b_slots)
        if not team_a or not team_b:
            return [], []
        return team_a, team_b

    async def get_roster(self, db_session: AsyncSession, room: Room) -> list[Dweller]:
        """Return the adult dwellers assigned to the room, oldest first."""
        return list(await crud_dweller.get_arena_roster(db_session, room.id))

    @staticmethod
    def _winner_from_events(events: list[ArenaMatchEventOut]) -> str | None:
        """Return the match winner from the newest finish event, if any."""
        for event in reversed(events):
            if event.kind == "finish":
                return event.message.split(" defeated ")[0]
        return None

    @staticmethod
    def _fighter_out(dweller: Dweller) -> ArenaFighter:
        return ArenaFighter(
            id=str(dweller.id),
            name=f"{dweller.first_name} {dweller.last_name}",
            level=dweller.level,
            health=dweller.health,
            max_health=dweller.effective_max_health,
            power=combat_power(dweller),
        )

    async def get_arena_state(self, db_session: AsyncSession, vault_id: UUID4) -> ArenaState:
        """Build the full arena state for a vault: fighters, roster, flags, journal."""
        rooms = await room_crud.get_arena_rooms(db_session, vault_id=vault_id)

        countdown = game_config.game_loop.arena_countdown_seconds
        state = []
        for room in rooms:
            mode = room.arena_mode or ArenaMode.DUEL
            size = self._required_team_size(mode)
            team_a, team_b = await self.get_teams(db_session, room)
            roster = await self.get_roster(db_session, room)

            match_done = room.arena_last_fight_at is not None
            started = room.arena_fight_started_at is not None
            countdown_remaining = 0
            if started and not match_done:
                elapsed = (datetime.utcnow() - room.arena_fight_started_at).total_seconds()
                countdown_remaining = max(0, int(countdown - elapsed))

            events = [
                ArenaMatchEventOut(
                    id=str(e.id),
                    round_seq=e.round_seq,
                    kind=e.kind,
                    message=e.message,
                )
                for e in reversed(await arena_match_event_crud.get_recent_by_room(db_session, room.id))
            ]
            winner_name = self._winner_from_events(events)

            state.append(
                ArenaRoomState(
                    room_id=str(room.id),
                    room_name=room.name,
                    tier=room.tier,
                    mode=mode.value,
                    fighter_a_id=str(room.arena_fighter_a_id) if room.arena_fighter_a_id else None,
                    fighter_b_id=str(room.arena_fighter_b_id) if room.arena_fighter_b_id else None,
                    fighters=[self._fighter_out(team[0]) for team in (team_a, team_b) if team],
                    team_a=[self._fighter_out(f) for f in team_a],
                    team_b=[self._fighter_out(f) for f in team_b],
                    roster=[
                        ArenaRosterEntry(
                            id=str(d.id),
                            name=f"{d.first_name} {d.last_name}",
                            level=d.level,
                            health=d.health,
                            max_health=d.effective_max_health,
                        )
                        for d in roster
                    ],
                    fight_ready=len(roster) >= size * 2,
                    match_done=match_done,
                    fight_started=started,
                    countdown_remaining=countdown_remaining,
                    can_start=len(team_a) >= size and len(team_b) >= size and not started and not match_done,
                    winner_name=winner_name,
                    events=events,
                )
            )

        return ArenaState(rooms=state)

    async def clear_journal(self, db_session: AsyncSession, room_id: UUID4, vault_id: UUID4 | None = None) -> int:
        """Delete all journal events for an arena room. Returns how many were removed."""
        room = await self._get_arena_room(db_session, room_id, vault_id)
        count = await arena_match_event_crud.delete_for_room(db_session, room.id)
        await db_session.commit()
        return count

    async def clear_fighter_slots_for_dweller(
        self, db_session: AsyncSession, dweller_id: UUID4, *, commit: bool = True
    ) -> None:
        """Null any arena fighter slot that still references a dweller who left the room.

        ``commit`` defaults to True for standalone use; pass False when the
        caller wants slot cleanup in the same transaction as a room move.
        """
        changed = False
        for room in await room_crud.get_arena_rooms_with_fighter(db_session, dweller_id):
            room_changed = False
            if room.arena_fighter_a_id == dweller_id:
                room.arena_fighter_a_id = None
                room_changed = True
            if room.arena_fighter_b_id == dweller_id:
                room.arena_fighter_b_id = None
                room_changed = True
            if room.fighter_c_id == dweller_id:
                room.fighter_c_id = None
                room_changed = True
            if room.fighter_d_id == dweller_id:
                room.fighter_d_id = None
                room_changed = True
            if room_changed:
                changed = True
                room.arena_last_fight_at = None
                room.arena_fight_started_at = None
                room_key = str(room.id)
                self._round_seq.pop(room_key, None)
                self._damage_carry = {key: carry for key, carry in self._damage_carry.items() if key[0] != room_key}
                await arena_match_event_crud.delete_for_room(db_session, room.id)
            db_session.add(room)
        if changed and commit:
            await db_session.commit()

    async def start_fight(self, db_session: AsyncSession, room_id: UUID4, vault_id: UUID4 | None = None) -> Room:
        """Arm a match for an arena room: a full team on each side, not done.

        The first combat tick lands after the countdown grace period.
        """
        room = await self._get_arena_room(db_session, room_id, vault_id)
        if room.arena_last_fight_at is not None:
            raise ValidationException(detail="Match is over - pick fighters again to start a new one")
        if room.arena_fight_started_at is not None:
            raise ValidationException(detail="Match already started")

        size = self._required_team_size(room.arena_mode or ArenaMode.DUEL)
        team_a, team_b = await self.get_teams(db_session, room)
        if len(team_a) < size or len(team_b) < size:
            word = "two" if size == 1 else "four"
            raise ValidationException(detail=f"Arena needs {word} adult fighters selected")

        room.arena_fight_started_at = datetime.utcnow()
        db_session.add(room)
        await db_session.commit()
        return room

    @staticmethod
    def _locked_out() -> dict:
        """Another worker holds the arena tick lock, so this one fights no rounds."""
        return {"arena": {"rooms": 0, "rounds": []}}

    async def process_arena_fights(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        seconds_passed: int,
    ) -> dict:
        """Run one fight round per Arena room in a single vault."""
        async with db_locks.hold_advisory_lock(db_session, "arena-tick") as acquired:
            if not acquired:
                return self._locked_out()
            rooms = await self._get_arena_rooms(db_session, vault_id)
            return await self._process_rooms(db_session, rooms, seconds_passed)

    async def process_arena_ticks(
        self,
        db_session: AsyncSession,
        seconds_passed: int,
    ) -> dict:
        """Run one fight round for every fight-ready Arena room across all vaults.

        Called on its own fast cadence by the ``arena_tick`` dramatiq actor,
        independent of the 60-second vault round. A cross-process advisory lock
        serializes execution: the worker that loses the race skips the tick
        rather than fighting the same room twice.
        """
        async with db_locks.hold_advisory_lock(db_session, "arena-tick") as acquired:
            if not acquired:
                return self._locked_out()
            rooms = await room_crud.get_arena_rooms(db_session)
            return await self._process_rooms(db_session, rooms, seconds_passed)

    async def _process_rooms(
        self,
        db_session: AsyncSession,
        rooms: list[Room],
        seconds_passed: int,
    ) -> dict:
        rounds = []
        now = datetime.utcnow()
        for room in rooms:
            if room.arena_last_fight_at is not None:
                continue
            if room.arena_fight_started_at is None:
                continue
            if now - room.arena_fight_started_at < timedelta(seconds=game_config.game_loop.arena_countdown_seconds):
                continue
            size = self._required_team_size(room.arena_mode or ArenaMode.DUEL)
            team_a, team_b = await self.get_teams(db_session, room)
            if len(team_a) < size or len(team_b) < size:
                continue

            round_result = await self._resolve_round(
                db_session,
                room,
                [participant_from_dweller(f) for f in team_a],
                [participant_from_dweller(f) for f in team_b],
                seconds_passed,
            )
            rounds.append({"room_id": str(room.id), **round_result})

        await db_session.commit()
        return {"arena": {"rooms": len(rooms), "rounds": rounds}}

    async def _get_arena_rooms(self, db_session: AsyncSession, vault_id: UUID4) -> list[Room]:
        return await room_crud.get_arena_rooms(db_session, vault_id=vault_id)

    @staticmethod
    def _team_damage(team: list[ArenaParticipant], seconds_passed: int) -> float:
        return sum(member.power for member in team) / 5 * seconds_passed

    def _apply_team_damage(
        self,
        room_key: str,
        defenders: list[ArenaParticipant],
        damage: float,
    ) -> list[tuple[ArenaParticipant, int]]:
        hits: list[tuple[ArenaParticipant, int]] = []
        pool = damage
        for defender in sorted((member for member in defenders if member.health > 0), key=lambda member: member.health):
            carry_key = (room_key, defender.key)
            carried = self._damage_carry.get(carry_key, 0.0) + pool
            total = int(carried)
            self._damage_carry[carry_key] = carried - total
            before = defender.health
            defender.health = max(0, defender.health - total)
            hits.append((defender, total))
            spill = total - min(total, before)
            if spill <= 0:
                break
            pool = float(spill)
        return hits

    @staticmethod
    def _team_defeated(team: list[ArenaParticipant]) -> bool:
        return all(member.health <= 0 for member in team)

    @staticmethod
    def _team_hp(team: list[ArenaParticipant]) -> int:
        return sum(member.health for member in team)

    @staticmethod
    def _representative(team: list[ArenaParticipant]) -> ArenaParticipant:
        standing = [member for member in team if member.health > 0] or team
        return max(standing, key=lambda member: member.power)

    def _emit_hit_events(
        self,
        db_session: AsyncSession,
        room: Room,
        seq: int,
        attackers: list[ArenaParticipant],
        hits: list[tuple[ArenaParticipant, int]],
    ) -> None:
        attacker = self._representative(attackers)
        for target, damage in hits:
            if damage > 0:
                db_session.add(
                    ArenaMatchEvent(
                        room_id=room.id,
                        round_seq=seq,
                        kind="hit",
                        message=f"{attacker.short_name} hits {target.short_name} for {damage}",
                    )
                )

    async def _resolve_round(
        self,
        db_session: AsyncSession,
        room: Room,
        team_a: list[ArenaParticipant],
        team_b: list[ArenaParticipant],
        seconds_passed: int,
    ) -> dict:
        # Damage dealt by each team's aggregate power (20% per second, matching incident
        # math). Fractional damage carries per participant between ticks so near-equal
        # powers stay visibly different instead of both truncating to the same int.
        room_key = str(room.id)
        damage_from_a = self._team_damage(team_a, seconds_passed)
        damage_from_b = self._team_damage(team_b, seconds_passed)

        hits_on_b = self._apply_team_damage(room_key, team_b, damage_from_a)
        hits_on_a = self._apply_team_damage(room_key, team_a, damage_from_b)

        for participant in (*team_a, *team_b):
            if participant.dweller is not None:
                participant.dweller.health = participant.health
                db_session.add(participant.dweller)

        seq = self._round_seq.get(room_key, 1)
        self._emit_hit_events(db_session, room, seq, team_b, hits_on_a)
        self._emit_hit_events(db_session, room, seq, team_a, hits_on_b)
        self._round_seq[room_key] = seq + 1

        a_defeated = self._team_defeated(team_a)
        b_defeated = self._team_defeated(team_b)
        if not a_defeated and not b_defeated:
            return {
                "status": "ongoing",
                "fighter_a_hp": self._team_hp(team_a),
                "fighter_b_hp": self._team_hp(team_b),
            }

        if a_defeated and b_defeated:
            winner_team, loser_team = random.choice([(team_a, team_b), (team_b, team_a)])
        elif a_defeated:
            winner_team, loser_team = team_b, team_a
        else:
            winner_team, loser_team = team_a, team_b

        # Dwellers stay standing (no death in the arena): every dweller is left at 1 HP.
        # Creatures may sit at 0. The room is marked done so this match never re-runs
        # until the fighter selection changes (set_fighters clears the flag and heals).
        for participant in (*team_a, *team_b):
            if not participant.is_creature:
                participant.health = max(1, participant.health)
                if participant.dweller is not None:
                    participant.dweller.health = participant.health

        winner = self._representative(winner_team)
        loser = self._representative(loser_team)
        room.arena_last_fight_at = datetime.utcnow()
        db_session.add(room)

        # Happiness swing instead of caps: the winning team feels great, the losing one is sour.
        for participant in winner_team:
            if participant.dweller is not None:
                participant.dweller.happiness = min(100, participant.dweller.happiness + HAPPINESS_WIN)
                db_session.add(participant.dweller)
        for participant in loser_team:
            if participant.dweller is not None:
                participant.dweller.happiness = max(10, participant.dweller.happiness - HAPPINESS_LOSE)
                db_session.add(participant.dweller)
        for participant in winner_team:
            if participant.dweller is not None:
                await self._award_combat_xp(db_session, participant.dweller)

        db_session.add(
            ArenaMatchEvent(
                room_id=room.id,
                round_seq=seq,
                kind="finish",
                message=f"{winner.short_name} defeated {loser.short_name}!",
            )
        )
        db_session.add(
            ArenaMatchEvent(
                room_id=room.id,
                round_seq=seq,
                kind="reward",
                message=(
                    f"{winner.short_name} happiness +{HAPPINESS_WIN}, {loser.short_name} happiness -{HAPPINESS_LOSE}"
                ),
            )
        )

        logger.info(
            "Arena %s: %s defeated %s (happiness %+d/%+d)",
            room.id,
            winner.short_name,
            loser.short_name,
            HAPPINESS_WIN,
            -HAPPINESS_LOSE,
        )

        return {
            "status": "finished",
            "winner_id": winner.key,
            "winner": winner.name,
            "loser_id": loser.key,
            "loser": loser.name,
        }

    async def _award_combat_xp(self, db_session: AsyncSession, dweller: Dweller) -> None:
        from app.services.leveling_service import leveling_service

        xp = game_config.combat.xp_per_difficulty * 2
        dweller.experience = max(0, dweller.experience + xp)
        db_session.add(dweller)
        leveled_up, levels_gained = await leveling_service.check_level_up(db_session, dweller)
        if leveled_up:
            await leveling_service.settle_level_up(
                db_session, dweller, old_level=dweller.level - levels_gained, levels_gained=levels_gained
            )


arena_service = ArenaService()
