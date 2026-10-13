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
from app.services.exploration.data_loader import list_arena_creatures
from app.utils.combat import combat_power
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

HAPPINESS_WIN = 10
HAPPINESS_LOSE = 10
MODE_UNLOCK_TIERS = {ArenaMode.DUEL: 1, ArenaMode.BRAWL: 2, ArenaMode.HUNT: 3}
TEAM_LABELS = {ArenaMode.BRAWL: ("Team A", "Team B"), ArenaMode.HUNT: ("Dwellers", "Creatures")}


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
        name=dweller.display_name,
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

    @staticmethod
    def _validate_mode_tier(room: Room, mode: ArenaMode) -> None:
        required_tier = MODE_UNLOCK_TIERS[mode]
        if room.tier < required_tier:
            raise ValidationException(detail=f"{mode.value.capitalize()} requires Arena tier {required_tier}")

    async def _get_arena_room(self, db_session: AsyncSession, room_id: UUID4, vault_id: UUID4 | None = None) -> Room:
        rooms = await room_crud.get_arena_rooms(db_session, room_id=room_id, vault_id=vault_id)
        if not rooms:
            raise ValidationException(detail="Arena room not found")
        return rooms[0]

    @staticmethod
    def _team_slot_ids(room: Room) -> tuple[list[UUID4 | None], list[UUID4 | None]]:
        """Slot ids for (team A, team B); a/b are each side's lead across modes.

        Hunt keeps dwellers on team A (a, optional c) and has no dweller slots on
        team B - the creatures come from ``room.arena_opponents`` instead.
        """
        mode = room.arena_mode or ArenaMode.DUEL
        if mode == ArenaMode.BRAWL:
            return [room.arena_fighter_a_id, room.fighter_c_id], [room.arena_fighter_b_id, room.fighter_d_id]
        if mode == ArenaMode.HUNT:
            return [room.arena_fighter_a_id, room.fighter_c_id], []
        return [room.arena_fighter_a_id], [room.arena_fighter_b_id]

    @staticmethod
    def _required_team_size(mode: ArenaMode) -> int:
        return 2 if mode == ArenaMode.BRAWL else 1

    @staticmethod
    def _hunt_opponents(keys: list[str]) -> list[dict]:
        """Build persisted creature opponents from catalog keys (hp initialised to max_hp)."""
        if not 1 <= len(keys) <= 2:
            raise ValidationException(detail="Hunt mode needs one or two opponents")
        catalogue = {creature["key"]: creature for creature in list_arena_creatures()}
        opponents = []
        for key in keys:
            creature = catalogue.get(key)
            if creature is None:
                raise ValidationException(detail="Unknown hunt opponent")
            opponents.append(
                {
                    "key": creature["key"],
                    "name": creature["name"],
                    "power": creature["power"],
                    "max_hp": creature["max_hp"],
                    "hp": creature["max_hp"],
                }
            )
        return opponents

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
        opponent_keys: list[str] | None = None,
    ) -> Room:
        """Pick the fighters that fight, per mode.

        Duel uses the a/b slots; brawl fills all four (a/c vs b/d); hunt pits one or
        two dwellers (a, optional c) against creatures named by ``opponent_keys``.
        Every provided fighter must be an adult assigned to the room. Changing the
        selection resets any previous match: flags cleared, journal wiped, fighters
        healed.
        """
        room = await self._get_arena_room(db_session, room_id, vault_id)
        self._validate_mode_tier(room, mode)
        opponents: list[dict] | None = None
        if mode == ArenaMode.HUNT:
            if fighter_b_id is not None or fighter_d_id is not None:
                raise ValidationException(detail="Hunt mode has no dwellers on the creature side")
            if fighter_a_id is None:
                raise ValidationException(detail="Hunt mode needs at least one dweller")
            opponents = self._hunt_opponents(opponent_keys or [])
        elif mode == ArenaMode.DUEL and (fighter_c_id is not None or fighter_d_id is not None):
            raise ValidationException(detail="Duel mode takes exactly two fighters")
        elif mode == ArenaMode.BRAWL and None in (fighter_a_id, fighter_b_id, fighter_c_id, fighter_d_id):
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
        room.arena_opponents = opponents
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

    @staticmethod
    def _dweller_participants(slots: list[UUID4 | None], by_id: dict[str, Dweller]) -> list[ArenaParticipant]:
        participants = []
        for slot in slots:
            if slot is None:
                continue
            member = by_id.get(str(slot))
            if member is None:
                return []
            participants.append(participant_from_dweller(member))
        return participants

    @staticmethod
    def _creature_participants(room: Room) -> list[ArenaParticipant]:
        return [
            ArenaParticipant(
                key=f"{opponent['key']}#{index}",
                name=opponent["name"],
                short_name=opponent["name"],
                power=float(opponent["power"]),
                health=int(opponent["hp"]),
                max_health=int(opponent["max_hp"]),
                is_creature=True,
            )
            for index, opponent in enumerate(room.arena_opponents or [])
        ]

    @staticmethod
    def _persist_creature_hp(room: Room, creatures: list[ArenaParticipant]) -> None:
        """Write resolved creature HP back into ``room.arena_opponents`` so it survives ticks."""
        opponents = room.arena_opponents or []
        if len(opponents) != len(creatures):
            return
        room.arena_opponents = [
            {**opponent, "hp": creature.health} for opponent, creature in zip(opponents, creatures, strict=True)
        ]

    async def get_teams(
        self, db_session: AsyncSession, room: Room
    ) -> tuple[list[ArenaParticipant], list[ArenaParticipant]]:
        """Return (team A, team B) participants in slot order, or ([], []) if not fully selected.

        Hunt fields the dwellers on team A and builds team B from the persisted
        creature opponents; duel/brawl field dwellers on both sides.
        """
        mode = room.arena_mode or ArenaMode.DUEL
        a_slots, b_slots = self._team_slot_ids(room)
        slot_ids = [slot for slot in (*a_slots, *b_slots) if slot is not None]
        fighters = await crud_dweller.get_arena_fighters(db_session, room.id, ids=slot_ids) if slot_ids else []
        by_id = {str(f.id): f for f in fighters}

        team_a = self._dweller_participants(a_slots, by_id)
        team_b = (
            self._creature_participants(room) if mode == ArenaMode.HUNT else self._dweller_participants(b_slots, by_id)
        )

        if mode == ArenaMode.HUNT:
            if not 1 <= len(team_a) <= 2 or not 1 <= len(team_b) <= 2:
                return [], []
        elif len(team_a) != self._required_team_size(mode) or len(team_b) != self._required_team_size(mode):
            return [], []
        return team_a, team_b

    async def get_roster(self, db_session: AsyncSession, room: Room) -> list[Dweller]:
        """Return the adult dwellers assigned to the room, oldest first."""
        return list(await crud_dweller.get_arena_roster(db_session, room.id))

    @staticmethod
    def list_creatures() -> list[dict]:
        """Selectable hunt opponents (key, name, power, max_hp) from the enemy catalog."""
        return list_arena_creatures()

    @staticmethod
    def _winner_from_events(
        events: list[ArenaMatchEventOut],
        mode: ArenaMode,
        team_a: list[ArenaParticipant],
        team_b: list[ArenaParticipant],
    ) -> str | None:
        """Credit the full winning side, including unambiguous legacy representative results."""
        for event in reversed(events):
            if event.kind == "finish":
                winner = event.message.split(" defeated ")[0]
                if mode not in TEAM_LABELS:
                    return winner
                teams = list(zip(TEAM_LABELS[mode], (team_a, team_b), strict=True))
                matched = [team for label, team in teams if label == winner]
                if not matched:
                    matched = [team for _, team in teams if any(winner in (p.name, p.short_name) for p in team)]
                return " & ".join(p.name for p in matched[0]) if len(matched) == 1 else winner
        return None

    @staticmethod
    def _participant_out(participant: ArenaParticipant) -> ArenaFighter:
        return ArenaFighter(
            id=participant.key,
            name=participant.name,
            level=participant.dweller.level if participant.dweller else 0,
            health=participant.health,
            max_health=participant.max_health,
            power=participant.power,
            is_creature=participant.is_creature,
            image_url=participant.dweller.image_url if participant.dweller else None,
            thumbnail_url=participant.dweller.thumbnail_url if participant.dweller else None,
        )

    @staticmethod
    def _can_start(
        mode: ArenaMode,
        team_a: list[ArenaParticipant],
        team_b: list[ArenaParticipant],
        *,
        started: bool,
        match_done: bool,
    ) -> bool:
        if started or match_done:
            return False
        if mode == ArenaMode.HUNT:
            return 1 <= len(team_a) <= 2 and 1 <= len(team_b) <= 2
        size = 2 if mode == ArenaMode.BRAWL else 1
        return len(team_a) >= size and len(team_b) >= size

    async def get_arena_state(self, db_session: AsyncSession, vault_id: UUID4) -> ArenaState:
        """Build the full arena state for a vault: fighters, roster, flags, journal."""
        rooms = await room_crud.get_arena_rooms(db_session, vault_id=vault_id)

        countdown = game_config.game_loop.arena_countdown_seconds
        state = []
        for room in rooms:
            mode = room.arena_mode or ArenaMode.DUEL
            available_modes = [choice for choice, tier in MODE_UNLOCK_TIERS.items() if room.tier >= tier]
            mode_unlocked = mode in available_modes
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
            winner_name = self._winner_from_events(events, mode, team_a, team_b)

            state.append(
                ArenaRoomState(
                    room_id=str(room.id),
                    room_name=room.name,
                    tier=room.tier,
                    mode=mode.value,
                    available_modes=available_modes,
                    fighter_a_id=str(room.arena_fighter_a_id) if room.arena_fighter_a_id else None,
                    fighter_b_id=str(room.arena_fighter_b_id) if room.arena_fighter_b_id else None,
                    fighters=[self._participant_out(team[0]) for team in (team_a, team_b) if team],
                    team_a=[self._participant_out(p) for p in team_a],
                    team_b=[self._participant_out(p) for p in team_b],
                    roster=[
                        ArenaRosterEntry(
                            id=str(d.id),
                            name=d.display_name,
                            level=d.level,
                            health=d.health,
                            max_health=d.effective_max_health,
                            image_url=d.image_url,
                            thumbnail_url=d.thumbnail_url,
                        )
                        for d in roster
                    ],
                    fight_ready=mode_unlocked
                    and (len(roster) >= 1 if mode == ArenaMode.HUNT else len(roster) >= size * 2),
                    match_done=match_done,
                    fight_started=started,
                    countdown_remaining=countdown_remaining,
                    can_start=mode_unlocked
                    and self._can_start(mode, team_a, team_b, started=started, match_done=match_done),
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
        self._validate_mode_tier(room, room.arena_mode or ArenaMode.DUEL)
        if room.arena_last_fight_at is not None:
            raise ValidationException(detail="Match is over - pick fighters again to start a new one")
        if room.arena_fight_started_at is not None:
            raise ValidationException(detail="Match already started")

        mode = room.arena_mode or ArenaMode.DUEL
        size = self._required_team_size(mode)
        team_a, team_b = await self.get_teams(db_session, room)
        if not team_a or not team_b:
            if mode == ArenaMode.HUNT:
                raise ValidationException(detail="Hunt needs one or two dwellers and at least one creature")
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
            mode = room.arena_mode or ArenaMode.DUEL
            team_a, team_b = await self.get_teams(db_session, room)
            if not team_a or not team_b:
                continue

            round_result = await self._resolve_round(db_session, room, team_a, team_b, seconds_passed)
            if mode == ArenaMode.HUNT:
                self._persist_creature_hp(room, team_b)
                db_session.add(room)
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
        labels = TEAM_LABELS.get(room.arena_mode or ArenaMode.DUEL)
        winner_label = labels[0 if winner_team is team_a else 1] if labels else winner.short_name
        loser_label = labels[0 if loser_team is team_a else 1] if labels else loser.short_name
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
                message=f"{winner_label} defeated {loser_label}!",
            )
        )
        db_session.add(
            ArenaMatchEvent(
                room_id=room.id,
                round_seq=seq,
                kind="reward",
                message=", ".join(
                    f"{' & '.join(p.short_name for p in team if p.dweller)} happiness {change:+d}"
                    for team, change in [(winner_team, HAPPINESS_WIN), (loser_team, -HAPPINESS_LOSE)]
                    if any(p.dweller for p in team)
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
