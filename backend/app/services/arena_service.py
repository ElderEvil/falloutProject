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
import threading
from datetime import datetime, timedelta

from pydantic import UUID4
from sqlalchemy.orm import selectinload
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.models.arena_match_event import ArenaMatchEvent
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.common import AgeGroupEnum
from app.utils.combat import combat_power
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

MIN_FIGHTERS = 2
HAPPINESS_WIN = 10
HAPPINESS_LOSE = 10


def _eligible_fighter_conditions(room_id: UUID4, *, require_alive: bool = True):
    conditions = [
        Dweller.room_id == room_id,
        Dweller.is_adult,
        Dweller.age_group == AgeGroupEnum.ADULT,
    ]
    if require_alive:
        conditions.append(Dweller.health > 0)
    return conditions


class ArenaService:
    """Process arena fights for vaults."""

    def __init__(self) -> None:
        # room_id -> next journal round sequence (in-memory; events are cleared
        # on match reset, so a restart just renumbers, which is cosmetic).
        self._round_seq: dict[str, int] = {}
        # (room_id, dweller_id) -> fractional damage carried between ticks so a
        # 8.7 vs 8.0 power difference shows up instead of truncating both to 8.
        self._damage_carry: dict[tuple[str, str], float] = {}
        # Serializes fast-tick execution: dramatiq runs the actor on several
        # worker threads, and without this they'd fight the same room in
        # parallel (double rewards, mangled journal round numbers).
        self._tick_lock = threading.Lock()

    async def set_fighters(
        self,
        db_session: AsyncSession,
        room_id: UUID4,
        fighter_a_id: UUID4 | None,
        fighter_b_id: UUID4 | None,
    ) -> Room:
        """Pick which assigned dwellers fight (dweller-vs-dweller mode).

        Each provided fighter must be an adult assigned to the room. Changing
        the selection resets any previous match: flags cleared, journal wiped,
        fighters healed.
        """
        room = await db_session.get(Room, room_id)
        if room is None or room.category != "arena":
            raise ValidationException(detail="Arena room not found")

        selected_ids = [fid for fid in (fighter_a_id, fighter_b_id) if fid is not None]
        if selected_ids:
            result = await db_session.execute(
                select(Dweller).where(Dweller.id.in_(selected_ids), *_eligible_fighter_conditions(room.id))
            )
            fighters = list(result.scalars().all())
            if len(fighters) != len(selected_ids):
                raise ValidationException(detail="Both fighters must be adult dwellers assigned to the Arena")
        else:
            fighters = []

        room.arena_fighter_a_id = fighter_a_id
        room.arena_fighter_b_id = fighter_b_id
        room.arena_last_fight_at = None
        room.arena_fight_started_at = None
        self._round_seq.clear()
        self._damage_carry.clear()

        stale_events = await db_session.execute(select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == room.id))
        for event in stale_events.scalars().all():
            await db_session.delete(event)

        for fighter in fighters:
            fighter.health = fighter.max_health
            db_session.add(fighter)

        db_session.add(room)
        await db_session.commit()
        return room

    async def get_fighters(self, db_session: AsyncSession, room: Room) -> list[Dweller]:
        """Return the selected fighters in A/B order, or [] if not fully set."""
        ids = [fid for fid in (room.arena_fighter_a_id, room.arena_fighter_b_id) if fid is not None]
        if len(ids) < MIN_FIGHTERS:
            return []

        result = await db_session.execute(
            select(Dweller)
            .options(selectinload(Dweller.weapon))
            .where(Dweller.id.in_(ids), *_eligible_fighter_conditions(room.id))
        )
        by_id = {str(f.id): f for f in result.scalars().all()}
        ordered = [by_id.get(str(room.arena_fighter_a_id)), by_id.get(str(room.arena_fighter_b_id))]
        if None in ordered:
            return []
        return ordered  # type: ignore[return-value]

    async def get_roster(self, db_session: AsyncSession, room: Room) -> list[Dweller]:
        """Return the adult dwellers assigned to the room, oldest first."""
        result = await db_session.execute(
            select(Dweller)
            .where(*_eligible_fighter_conditions(room.id))
            .order_by(Dweller.created_at)
        )
        return list(result.scalars().all())

    async def clear_journal(self, db_session: AsyncSession, room_id: UUID4) -> int:
        """Delete all journal events for an arena room. Returns how many were removed."""
        result = await db_session.execute(select(ArenaMatchEvent).where(ArenaMatchEvent.room_id == room_id))
        events = list(result.scalars().all())
        for event in events:
            await db_session.delete(event)
        await db_session.commit()
        return len(events)

    async def clear_fighter_slots_for_dweller(self, db_session: AsyncSession, dweller_id: UUID4) -> None:
        """Null any arena fighter slot that still references a dweller who left the room."""
        result = await db_session.execute(
            select(Room).where(
                Room.category == "arena",
                (Room.arena_fighter_a_id == dweller_id) | (Room.arena_fighter_b_id == dweller_id),
            )
        )
        changed = False
        for room in result.scalars().all():
            if room.arena_fighter_a_id == dweller_id:
                room.arena_fighter_a_id = None
                changed = True
            if room.arena_fighter_b_id == dweller_id:
                room.arena_fighter_b_id = None
                changed = True
            db_session.add(room)
        if changed:
            await db_session.commit()

    async def start_fight(self, db_session: AsyncSession, room_id: UUID4) -> Room:
        """Arm a match for an arena room: both fighter slots set, not done.

        The first combat tick lands after the countdown grace period.
        """
        room = await db_session.get(Room, room_id)
        if room is None or room.category != "arena":
            raise ValidationException(detail="Arena room not found")
        if room.arena_last_fight_at is not None:
            raise ValidationException(detail="Match is over - pick fighters again to start a new one")
        if room.arena_fight_started_at is not None:
            raise ValidationException(detail="Match already started")

        fighters = await self.get_fighters(db_session, room)
        if len(fighters) < MIN_FIGHTERS:
            raise ValidationException(detail="Arena needs two adult fighters selected")

        room.arena_fight_started_at = datetime.utcnow()
        db_session.add(room)
        await db_session.commit()
        return room

    async def process_arena_fights(
        self,
        db_session: AsyncSession,
        vault_id: UUID4,
        seconds_passed: int,
    ) -> dict:
        """Run one fight round per Arena room in a single vault."""
        rooms = await self._get_arena_rooms(db_session, vault_id)
        return await self._process_rooms(db_session, rooms, seconds_passed)

    async def process_arena_ticks(
        self,
        db_session: AsyncSession,
        seconds_passed: int,
    ) -> dict:
        """Run one fight round for every fight-ready Arena room across all vaults.

        Called on its own fast cadence by the ``arena_tick`` dramatiq actor,
        independent of the 60-second vault round. Serialized so worker threads
        never fight the same room in parallel.
        """
        with self._tick_lock:
            result = await db_session.execute(select(Room).where(Room.category == "arena"))
            rooms = list(result.scalars().all())
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
            fighters = await self.get_fighters(db_session, room)
            if len(fighters) < MIN_FIGHTERS:
                continue

            round_result = await self._run_round(db_session, room, fighters, seconds_passed)
            rounds.append({"room_id": str(room.id), **round_result})

        await db_session.commit()
        return {"arena": {"rooms": len(rooms), "rounds": rounds}}

    async def _get_arena_rooms(self, db_session: AsyncSession, vault_id: UUID4) -> list[Room]:
        result = await db_session.execute(
            select(Room).where(
                Room.vault_id == vault_id,
                Room.category == "arena",
            )
        )
        return list(result.scalars().all())

    async def _run_round(
        self,
        db_session: AsyncSession,
        room: Room,
        fighters: list[Dweller],
        seconds_passed: int,
    ) -> dict:
        first, second = fighters[0], fighters[1]
        power_a = combat_power(first)
        power_b = combat_power(second)

        # Damage dealt by each fighter's own power (20% per second, matching incident
        # math). Fractional damage carries between ticks so near-equal powers
        # stay visibly different instead of both truncating to the same int.
        damage_from_a = power_a / 5 * seconds_passed
        damage_from_b = power_b / 5 * seconds_passed

        first_key = (str(room.id), str(first.id))
        second_key = (str(room.id), str(second.id))

        carried_b = self._damage_carry.get(first_key, 0.0) + damage_from_b
        first_damage = int(carried_b)
        self._damage_carry[first_key] = carried_b - first_damage

        carried_a = self._damage_carry.get(second_key, 0.0) + damage_from_a
        second_damage = int(carried_a)
        self._damage_carry[second_key] = carried_a - second_damage

        first.health = max(0, first.health - first_damage)
        second.health = max(0, second.health - second_damage)
        db_session.add(first)
        db_session.add(second)

        seq = self._round_seq.get(str(room.id), 1)
        if first_damage > 0:
            db_session.add(
                ArenaMatchEvent(
                    room_id=room.id,
                    round_seq=seq,
                    kind="hit",
                    message=f"{second.first_name} hits {first.first_name} for {first_damage}",
                )
            )
        if second_damage > 0:
            db_session.add(
                ArenaMatchEvent(
                    room_id=room.id,
                    round_seq=seq,
                    kind="hit",
                    message=f"{first.first_name} hits {second.first_name} for {second_damage}",
                )
            )
        self._round_seq[str(room.id)] = seq + 1

        if first.health <= 0 and second.health <= 0:
            winner = random.choice([first, second])
            loser = second if winner is first else first
        elif first.health <= 0:
            winner, loser = second, first
        elif second.health <= 0:
            winner, loser = first, second
        else:
            return {
                "status": "ongoing",
                "fighter_a_hp": first.health,
                "fighter_b_hp": second.health,
            }

        # Both fighters stay standing (no death in the arena); the loser is left at
        # 1 HP and the room is marked done so this match never re-runs until the
        # fighter selection changes (set_fighters clears the flag and heals).
        first.health = max(1, first.health)
        second.health = max(1, second.health)
        room.arena_last_fight_at = datetime.utcnow()
        db_session.add(room)
        db_session.add(first)
        db_session.add(second)

        # Happiness swing instead of caps: the winner feels great, the loser is sour.
        winner.happiness = min(100, winner.happiness + HAPPINESS_WIN)
        loser.happiness = max(10, loser.happiness - HAPPINESS_LOSE)
        db_session.add(winner)
        db_session.add(loser)
        await self._award_combat_xp(db_session, winner)

        db_session.add(
            ArenaMatchEvent(
                room_id=room.id,
                round_seq=seq,
                kind="finish",
                message=f"{winner.first_name} defeated {loser.first_name}!",
            )
        )
        db_session.add(
            ArenaMatchEvent(
                room_id=room.id,
                round_seq=seq,
                kind="reward",
                message=(
                    f"{winner.first_name} happiness +{HAPPINESS_WIN}, {loser.first_name} happiness -{HAPPINESS_LOSE}"
                ),
            )
        )

        logger.info(
            "Arena %s: %s defeated %s (happiness %+d/%+d)",
            room.id,
            winner.first_name,
            loser.first_name,
            HAPPINESS_WIN,
            -HAPPINESS_LOSE,
        )

        return {
            "status": "finished",
            "winner_id": str(winner.id),
            "winner": f"{winner.first_name} {winner.last_name}",
            "loser_id": str(loser.id),
            "loser": f"{loser.first_name} {loser.last_name}",
        }

    async def _award_combat_xp(self, db_session: AsyncSession, dweller: Dweller) -> None:
        from app.services.leveling_service import leveling_service

        xp = game_config.combat.xp_per_difficulty * 2
        dweller.experience = max(0, dweller.experience + xp)
        db_session.add(dweller)
        await leveling_service.check_level_up(db_session, dweller)


arena_service = ArenaService()
