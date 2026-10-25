"""Arena service — experimental battle playground.

Dwellers are parked in an Arena room, the player picks two of them as
fighters (dweller-vs-dweller mode), then presses FIGHT: a 3-2-1 countdown
elapses before the first combat tick. Combat power mirrors the incident combat
math, with normal damage and alternating team turns. The first to reach
zero HP loses; the winner gains happiness and XP, the loser loses happiness
and is left standing at 1 HP. The room is marked done and stays stopped until
the fighter selection changes, which resets it for a new match.

This is an experimental feature on branch `experiment/arena`.
"""

import logging
import random
from datetime import UTC, datetime, timedelta

from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core import db_locks
from app.core.enums import ArenaMode, DwellerStatusEnum
from app.core.game_config import game_config
from app.crud import dweller as crud_dweller
from app.crud import room as room_crud
from app.crud import vault as vault_crud
from app.crud.arena_match_event import arena_match_event_crud
from app.crud.arena_state import arena_state_crud
from app.models.arena_match_event import ArenaMatchEvent
from app.models.arena_state import ArenaState
from app.models.dweller import Dweller
from app.models.room import Room
from app.schemas.arena import (
    ArenaMatchEventOut,
    ArenaRoomState,
    ArenaRosterEntry,
)
from app.schemas.arena import (
    ArenaState as ArenaStateOut,
)
from app.schemas.combat import CombatAction, CombatImpact
from app.services.catalog_service import list_arena_creatures
from app.services.combat.arena_participants import (
    ArenaParticipant,
    catalog_participants,
    charge_per_second,
    dweller_participants,
    participant_out,
    persist_creature_hp,
)
from app.services.combat.weapon_skill_service import MAX_CHARGE, attack_effect, combat_body, weapon_skill
from app.services.game_tick.tick_results import ArenaEventStats, ArenaRoomStats, ArenaStats
from app.services.leveling_service import leveling_service
from app.services.notification_service import NotificationService
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)

HAPPINESS_WIN = 10
HAPPINESS_LOSE = 10
MODE_UNLOCK_TIERS = {ArenaMode.DUEL: 1, ArenaMode.BRAWL: 2, ArenaMode.HUNT: 3}
TEAM_LABELS = {ArenaMode.BRAWL: ("Team A", "Team B"), ArenaMode.HUNT: ("Dwellers", "Creatures")}
FIGHTER_SLOT_FIELDS = ("fighter_a_id", "fighter_b_id", "fighter_c_id", "fighter_d_id")


class ArenaService:
    """Process arena fights for vaults."""

    def __init__(self) -> None:
        # room_id -> next journal round sequence (in-memory; events are cleared
        # on match reset, so a restart just renumbers, which is cosmetic).
        self._round_seq: dict[str, int] = {}
        # (room_id, dweller_id) -> fractional damage carried between ticks so a
        # 8.7 vs 8.0 power difference shows up instead of truncating both to 8.
        self._damage_carry: dict[tuple[str, str], float] = {}

    def _clear_room_state(self, room_key: str) -> None:
        self._round_seq.pop(room_key, None)
        self._damage_carry = {key: carry for key, carry in self._damage_carry.items() if key[0] != room_key}

    @staticmethod
    def _reset_match(state: ArenaState) -> None:
        """Clear the match flags and skill queues so the selection stands fresh."""
        state.last_fight_at = None
        state.fight_started_at = None
        state.knocked_out_ids = None
        state.next_attack_team = "A"
        state.skill_charge = None
        state.queued_skill_ids = None

    async def _state(self, db_session: AsyncSession, room: Room) -> ArenaState:
        """Persisted arena state for a room, or a transient default when unconfigured.

        A transient result is never part of the session, so read paths must not
        write to it; write paths call ``arena_state_crud.get_or_create`` instead.
        """
        return await arena_state_crud.get(db_session, room.id) or ArenaState(room_id=room.id)

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
    def _team_slot_ids(state: ArenaState) -> tuple[list[UUID4 | None], list[UUID4 | None]]:
        """Slot ids for (team A, team B); a/b are each side's lead across modes.

        Hunt keeps dwellers on team A (a, optional c) and has no dweller slots on
        team B - the creatures come from ``state.opponents`` instead.
        """
        mode = state.mode or ArenaMode.DUEL
        if mode == ArenaMode.BRAWL:
            return [state.fighter_a_id, state.fighter_c_id], [state.fighter_b_id, state.fighter_d_id]
        if mode == ArenaMode.HUNT:
            return [state.fighter_a_id, state.fighter_c_id], []
        return [state.fighter_a_id], [state.fighter_b_id]

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
                    "is_robot": creature.get("is_robot", False),
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
        team_a_bot_key: str | None = None,
        team_b_bot_key: str | None = None,
    ) -> ArenaState:
        """Pick the fighters that fight, per mode.

        Duel uses the a/b slots; brawl fills all four (a/c vs b/d); hunt pits one or
        two dwellers (a, optional c) against creatures named by ``opponent_keys``.
        Every provided fighter must be an adult assigned to the room. Changing the
        selection resets any previous match: flags cleared and journal wiped.
        Dwellers keep their current health; catalog opponents and support bots reset.
        """
        room = await self._get_arena_room(db_session, room_id, vault_id)
        await arena_state_crud.get_for_update(db_session, room.id)
        self._validate_mode_tier(room, mode)
        if team_a_bot_key is not None:
            raise ValidationException(detail="Team A only supports dweller fighters")
        support_bots = {}
        if team_b_bot_key is not None:
            if mode != ArenaMode.BRAWL:
                raise ValidationException(detail="Training bot partners are only available on Team B in Brawl")
            catalogue = {entry["key"]: entry for entry in self.list_creatures()}
            if not catalogue.get(team_b_bot_key, {}).get("is_robot"):
                raise ValidationException(detail="Choose a training bot for support")
            if fighter_d_id is not None:
                raise ValidationException(detail="The second slot holds either a dweller or a training bot")
            support_bots["B"] = self._hunt_opponents([team_b_bot_key])[0]
        opponents: list[dict] | None = None
        if mode == ArenaMode.HUNT:
            if fighter_b_id is not None or fighter_d_id is not None:
                raise ValidationException(detail="Hunt mode has no dwellers on the creature side")
            if fighter_a_id is None:
                raise ValidationException(detail="Hunt mode needs at least one dweller")
            opponents = self._hunt_opponents(opponent_keys or [])
        elif mode == ArenaMode.DUEL and (fighter_c_id is not None or fighter_d_id is not None):
            raise ValidationException(detail="Duel mode takes exactly two fighters")
        elif mode == ArenaMode.BRAWL:
            leads_selected = fighter_a_id is not None and fighter_b_id is not None
            partners_selected = fighter_c_id is not None and (fighter_d_id is not None or team_b_bot_key)
            if not leads_selected or not partners_selected:
                raise ValidationException(
                    detail="Brawl needs two Team A dwellers, a Team B lead and a dweller or bot partner"
                )

        selected_ids = [fid for fid in (fighter_a_id, fighter_b_id, fighter_c_id, fighter_d_id) if fid is not None]
        if len(set(selected_ids)) != len(selected_ids):
            raise ValidationException(detail="Fighters must be distinct dwellers")

        if selected_ids:
            fighters = list(await crud_dweller.get_arena_fighters(db_session, room.id, ids=selected_ids))
            if len(fighters) != len(selected_ids):
                raise ValidationException(detail="Every fighter must be an adult dweller assigned to the Arena")

        state = await arena_state_crud.get_or_create(db_session, room.id)
        await self._release_fighters(db_session, state)
        state.fighter_a_id = fighter_a_id
        state.fighter_b_id = fighter_b_id
        state.fighter_c_id = fighter_c_id
        state.fighter_d_id = fighter_d_id
        state.mode = mode
        state.opponents = opponents
        state.support_bots = support_bots or None
        self._reset_match(state)
        db_session.add(state)
        self._clear_room_state(str(room.id))

        await arena_match_event_crud.delete_for_room(db_session, room.id)

        await db_session.commit()
        return state

    async def get_teams(
        self, db_session: AsyncSession, room: Room
    ) -> tuple[list[ArenaParticipant], list[ArenaParticipant]]:
        """Return (team A, team B) participants in slot order, or ([], []) if not fully selected.

        Hunt fields the dwellers on team A and builds team B from the persisted
        creature opponents; duel/brawl field dwellers on both sides.
        """
        state = await self._state(db_session, room)
        return await self._teams_from_state(db_session, room, state)

    async def _teams_from_state(
        self, db_session: AsyncSession, room: Room, state: ArenaState
    ) -> tuple[list[ArenaParticipant], list[ArenaParticipant]]:
        mode = state.mode or ArenaMode.DUEL
        a_slots, b_slots = self._team_slot_ids(state)
        slot_ids = [slot for slot in (*a_slots, *b_slots) if slot is not None]
        fighters = await crud_dweller.get_arena_fighters(db_session, room.id, ids=slot_ids) if slot_ids else []
        by_id = {str(f.id): f for f in fighters}

        team_a = dweller_participants(a_slots, by_id)
        team_b = (
            catalog_participants(state.opponents or [])
            if mode == ArenaMode.HUNT
            else dweller_participants(b_slots, by_id)
        )
        # Ignore retired Team A bot selections; incomplete legacy Brawls reset
        # through the normal match-cancellation path until a dweller fills slot C.
        if mode == ArenaMode.BRAWL:
            bot = (state.support_bots or {}).get("B")
            if bot:
                if state.fighter_b_id is None or len(team_b) != 1:
                    return [], []
                team_b.extend(catalog_participants([bot], "B"))
        # Knocked-out dwellers stay on the team (so the selection is not rejected)
        # but fight at 0 HP.
        knocked_out = set(state.knocked_out_ids or [])
        for participant in (*team_a, *team_b):
            if not participant.is_creature and participant.key in knocked_out:
                participant.health = 0

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
    def _can_start(
        team_a: list[ArenaParticipant],
        team_b: list[ArenaParticipant],
        *,
        started: bool,
        match_done: bool,
    ) -> bool:
        """True when an idle room has a complete selection on both sides.

        ``get_teams`` already returns ``([], [])`` unless each side has its full
        complement for the mode, so a non-empty team on each side is the whole check.
        """
        if started or match_done:
            return False
        return bool(team_a) and bool(team_b)

    @staticmethod
    def _event_snapshot(event: ArenaMatchEvent) -> ArenaEventStats:
        return {
            "id": str(event.id),
            "round_seq": event.round_seq,
            "kind": event.kind,
            "actor_id": event.actor_id,
            "action": event.action,
            "message": event.message,
            "created_at": event.created_at.replace(tzinfo=UTC).isoformat() if event.created_at else None,
        }

    async def get_tick_snapshot(self, db_session: AsyncSession, vault_id: UUID4) -> ArenaStats:
        """Repeatable, bounded journal snapshot; only the arena actor advances matches."""
        rooms: dict[str, ArenaRoomStats] = {}
        for room_id, started_at, finished_at, event in await arena_match_event_crud.get_vault_snapshot(
            db_session, vault_id
        ):
            key = str(room_id)
            if key not in rooms:
                rooms[key] = {
                    "room_id": key,
                    "fight_started": started_at is not None,
                    "match_done": finished_at is not None,
                    "events": [],
                }
            if event is not None:
                rooms[key]["events"].append(self._event_snapshot(event))
        return {"rooms": list(rooms.values())}

    async def get_arena_state(self, db_session: AsyncSession, vault_id: UUID4) -> ArenaStateOut:
        """Build the full arena state for a vault: fighters, roster, flags, journal."""
        rooms = await room_crud.get_arena_rooms(db_session, vault_id=vault_id)
        room_states = []
        for room in rooms:
            state = await self._state(db_session, room)
            room_states.append(await self._room_state(db_session, room, state))
        return ArenaStateOut(rooms=room_states)

    async def _room_state(self, db_session: AsyncSession, room: Room, state: ArenaState) -> ArenaRoomState:
        """Assemble the API view for one arena room from its persisted state."""
        mode = state.mode or ArenaMode.DUEL
        available_modes = [choice for choice, tier in MODE_UNLOCK_TIERS.items() if room.tier >= tier]
        mode_unlocked = mode in available_modes
        team_a, team_b = await self._teams_from_state(db_session, room, state)
        roster = await self.get_roster(db_session, room)

        match_done = state.last_fight_at is not None
        started = state.fight_started_at is not None
        countdown_remaining = 0
        if started and not match_done:
            elapsed = (datetime.utcnow() - state.fight_started_at).total_seconds()
            countdown_remaining = max(0, int(game_config.game_loop.arena_countdown_seconds - elapsed))

        events = [
            ArenaMatchEventOut(**self._event_snapshot(e))
            for e in reversed(await arena_match_event_crud.get_recent_by_room(db_session, room.id))
        ]
        winner_name = self._winner_from_events(events, mode, team_a, team_b)

        return ArenaRoomState(
            room_id=str(room.id),
            room_name=room.name,
            tier=room.tier,
            mode=mode.value,
            next_attack_team="A" if state.next_attack_team == "A" else "B",
            available_modes=available_modes,
            fighter_a_id=str(state.fighter_a_id) if state.fighter_a_id else None,
            fighter_b_id=str(state.fighter_b_id) if state.fighter_b_id else None,
            fighters=[participant_out(team[0], state) for team in (team_a, team_b) if team],
            team_a=[participant_out(p, state) for p in team_a],
            team_b=[participant_out(p, state) for p in team_b],
            roster=[
                ArenaRosterEntry(
                    id=str(d.id),
                    name=d.display_name,
                    level=d.level,
                    health=d.health,
                    max_health=d.effective_max_health,
                    image_url=d.image_url,
                    thumbnail_url=d.thumbnail_url,
                    age_group=d.age_group.value if d.age_group else None,
                    race=(d.visual_attributes or {}).get("race"),
                )
                for d in roster
            ],
            fight_ready=mode_unlocked
            and len(roster) >= {ArenaMode.DUEL: 2, ArenaMode.BRAWL: 3, ArenaMode.HUNT: 1}[mode],
            match_done=match_done,
            fight_started=started,
            countdown_remaining=countdown_remaining,
            can_start=mode_unlocked and self._can_start(team_a, team_b, started=started, match_done=match_done),
            winner_name=winner_name,
            events=events,
        )

    async def clear_journal(self, db_session: AsyncSession, room_id: UUID4, vault_id: UUID4 | None = None) -> int:
        """Delete all journal events for an arena room. Returns how many were removed."""
        room = await self._get_arena_room(db_session, room_id, vault_id)
        count = await arena_match_event_crud.delete_for_room(db_session, room.id)
        await db_session.commit()
        return count

    @staticmethod
    def _fighter_ids(state: ArenaState) -> list[UUID4]:
        return [fid for field in FIGHTER_SLOT_FIELDS if (fid := getattr(state, field))]

    async def _release_fighters(self, db_session: AsyncSession, state: ArenaState) -> None:
        await crud_dweller.set_arena_status(
            db_session, state.room_id, DwellerStatusEnum.IDLE, ids=self._fighter_ids(state)
        )

    async def clear_fighter_slots_for_dweller(
        self, db_session: AsyncSession, dweller_id: UUID4, *, commit: bool = True
    ) -> None:
        """Null any arena fighter slot that still references a dweller who left the room.

        ``commit`` defaults to True for standalone use; pass False when the
        caller wants slot cleanup in the same transaction as a room move.
        """
        changed = False
        for state in await arena_state_crud.get_by_fighter(db_session, dweller_id):
            await self._release_fighters(db_session, state)
            state_changed = False
            for field in FIGHTER_SLOT_FIELDS:
                if getattr(state, field) == dweller_id:
                    setattr(state, field, None)
                    state_changed = True
            if state_changed:
                changed = True
                self._reset_match(state)
                self._clear_room_state(str(state.room_id))
                await arena_match_event_crud.delete_for_room(db_session, state.room_id)
            db_session.add(state)
        if changed:
            await db_session.flush()
            if commit:
                await db_session.commit()

    async def stop_fight(self, db_session: AsyncSession, room_id: UUID4, vault_id: UUID4 | None = None) -> Room:
        """Cancel an active match without rewards; fighters keep their current health."""
        room = await self._get_arena_room(db_session, room_id, vault_id)
        state = await arena_state_crud.get_for_update(db_session, room.id)
        if state is None or state.fight_started_at is None or state.last_fight_at is not None:
            raise ValidationException(detail="No active match to stop")
        await self._release_fighters(db_session, state)
        self._reset_match(state)
        self._clear_room_state(str(room.id))
        await arena_match_event_crud.delete_for_room(db_session, room.id)
        db_session.add(state)
        await db_session.commit()
        return room

    async def start_fight(self, db_session: AsyncSession, room_id: UUID4, vault_id: UUID4 | None = None) -> Room:
        """Arm a match for an arena room: a full team on each side, not done.

        The first combat tick lands after the countdown grace period.
        """
        room = await self._get_arena_room(db_session, room_id, vault_id)
        state = await arena_state_crud.get_for_update(db_session, room.id) or ArenaState(room_id=room.id)
        mode = state.mode or ArenaMode.DUEL
        self._validate_mode_tier(room, mode)
        if state.last_fight_at is not None:
            raise ValidationException(detail="Match is over - pick fighters again to start a new one")
        if state.fight_started_at is not None:
            raise ValidationException(detail="Match already started")

        size = self._required_team_size(mode)
        team_a, team_b = await self._teams_from_state(db_session, room, state)
        if not team_a or not team_b:
            if mode == ArenaMode.HUNT:
                raise ValidationException(detail="Hunt needs one or two dwellers and at least one creature")
            word = "two" if size == 1 else "four"
            raise ValidationException(detail=f"Arena needs {word} adult fighters selected")

        state = await arena_state_crud.get_or_create(db_session, room.id)
        state.next_attack_team = "A"
        state.fight_started_at = datetime.utcnow()
        db_session.add(state)
        await crud_dweller.set_arena_status(
            db_session, room.id, DwellerStatusEnum.FIGHTING, ids=self._fighter_ids(state)
        )
        await db_session.commit()
        return room

    async def queue_skill(self, db_session: AsyncSession, room_id: UUID4, fighter_id: UUID4, vault_id: UUID4) -> None:
        """Reserve a charged attack for the fighter's next team turn under the room lock."""
        room = await self._get_arena_room(db_session, room_id, vault_id)
        state = await arena_state_crud.get_for_update(db_session, room.id)
        if state is None or state.fight_started_at is None or state.last_fight_at is not None:
            raise ValidationException(detail="Skills require an active match")
        self._validate_mode_tier(room, state.mode or ArenaMode.DUEL)
        elapsed = (datetime.utcnow() - state.fight_started_at).total_seconds()
        if elapsed < game_config.game_loop.arena_countdown_seconds:
            raise ValidationException(detail="Wait for the countdown to finish")
        teams = await self._teams_from_state(db_session, room, state)
        key = str(fighter_id)
        fighter = next((p for team in teams for p in team if p.key == key), None)
        if fighter is None or fighter.dweller is None or fighter.health <= 0:
            raise ValidationException(detail="Choose a standing dweller in this match")
        charge = dict(state.skill_charge or {})
        queued = list(state.queued_skill_ids or [])
        if key in queued or charge.get(key, 0) < MAX_CHARGE:
            raise ValidationException(detail="Skill is not charged or is already queued")
        charge[key] = 0
        state.skill_charge = charge
        state.queued_skill_ids = [*queued, key]
        db_session.add(state)
        await db_session.commit()

    def _resolve_attacks(
        self,
        db_session: AsyncSession,
        room: Room,
        state: ArenaState,
        attackers: list[ArenaParticipant],
        defenders: list[ArenaParticipant],
        seconds_passed: int,
        seq: int,
    ) -> None:
        """Each fighter chooses a distinct standing enemy while numbers allow.

        Team slot order keeps pairs stable until a knockout. If only one enemy
        remains, surviving attackers share that target. A queued skill is an
        extra attack before the ordinary hit; area skills hit multiple enemies.
        """
        standing_attackers = [p for p in attackers if p.health > 0]
        standing_defenders = [p for p in defenders if p.health > 0]
        if not standing_defenders:
            return
        queued = set(state.queued_skill_ids or [])
        for index, attacker in enumerate(standing_attackers):
            chosen = standing_defenders[index % len(standing_defenders)]
            living = [p for p in standing_defenders if p.health > 0]
            if not living:
                break
            skill = weapon_skill(attacker.dweller) if attacker.key in queued and attacker.dweller else None
            actions = (skill, None) if skill else (None,)
            for attack_skill in actions:
                living = [p for p in standing_defenders if p.health > 0]
                if not living:
                    break
                multiplier = attack_skill.multiplier if attack_skill else 1.0
                # Re-evaluate for each action: a skill may knock out the original target.
                targets = living if attack_skill and attack_skill.area else [chosen if chosen.health > 0 else living[0]]
                damage = self._team_damage([attacker], seconds_passed) * multiplier
                impacts: list[CombatImpact] = []
                journal: list[ArenaMatchEvent] = []
                for target in targets:
                    before = target.health
                    self._apply_team_damage(
                        str(room.id), [target], damage, seconds_passed=seconds_passed, cap_multiplier=multiplier
                    )
                    dealt = before - target.health
                    if dealt > 0 or attack_skill:
                        impacts.append(
                            CombatImpact(
                                target_id=target.key,
                                body=combat_body(target.dweller),
                                damage=dealt,
                                health_before=before,
                                health_after=target.health,
                            )
                        )
                        action = f"uses {attack_skill.name} on" if attack_skill else "hits"
                        journal.append(
                            ArenaMatchEvent(
                                room_id=room.id,
                                round_seq=seq,
                                kind="skill" if attack_skill else "hit",
                                actor_id=attacker.key,
                                message=f"{attacker.short_name} {action} {target.short_name} for {dealt}",
                            )
                        )
                if journal:
                    # Preserve per-target journal lines, but play an area skill once.
                    journal[0].action = CombatAction(
                        actor_id=attacker.key,
                        actor_body=combat_body(attacker.dweller),
                        effect=attack_effect(attacker.dweller, attack_skill),
                        skill=attack_skill.name if attack_skill else None,
                        skill_icon=attack_skill.icon if attack_skill else None,
                        targets=impacts,
                    ).model_dump()
                    db_session.add_all(journal)
            if skill:
                queued.discard(attacker.key)
        state.queued_skill_ids = sorted(queued) or None

    @staticmethod
    def _locked_out() -> dict:
        """Another worker holds the arena tick lock, so this one fights no rounds."""
        return {"arena": {"rooms": 0, "rounds": []}}

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
            result = await self._process_rooms(db_session, rooms, seconds_passed)
            # Drain deferred notifications only after the commit: they describe committed state.
            await db_session.commit()
            await NotificationService.deliver_deferred_notifications(db_session)
            return result

    async def _process_rooms(
        self,
        db_session: AsyncSession,
        rooms: list[Room],
        seconds_passed: int,
    ) -> dict:
        rounds = []
        now = datetime.utcnow()
        for room in rooms:
            state = await arena_state_crud.get_for_update(db_session, room.id) or ArenaState(room_id=room.id)
            if state.last_fight_at is not None or state.fight_started_at is None:
                await crud_dweller.set_arena_status(db_session, room.id, DwellerStatusEnum.IDLE)
                continue
            if now - state.fight_started_at < timedelta(seconds=game_config.game_loop.arena_countdown_seconds):
                continue
            state = await arena_state_crud.get_or_create(db_session, room.id)
            mode = state.mode or ArenaMode.DUEL
            team_a, team_b = await self._teams_from_state(db_session, room, state)
            if not team_a or not team_b:
                await self._release_fighters(db_session, state)
                self._reset_match(state)
                db_session.add(state)
                self._clear_room_state(str(room.id))
                continue

            round_result = await self._resolve_round(db_session, room, team_a, team_b, seconds_passed, state=state)
            persist_creature_hp(state, team_a, team_b)
            db_session.add(state)
            rounds.append({"room_id": str(room.id), **round_result})

        return {"arena": {"rooms": len(rooms), "rounds": rounds}}

    @staticmethod
    def _team_damage(team: list[ArenaParticipant], seconds_passed: int) -> float:
        """Damage per tick from standing attackers only; knocked-out members deal none."""
        return sum(member.power for member in team if member.health > 0) / 5 * max(0, seconds_passed)

    def _apply_team_damage(
        self,
        room_key: str,
        defenders: list[ArenaParticipant],
        damage: float,
        *,
        seconds_passed: int | None = None,
        cap_multiplier: float = 1.0,
    ) -> list[tuple[ArenaParticipant, int]]:
        hits: list[tuple[ArenaParticipant, int]] = []
        pool = damage
        for defender in sorted((member for member in defenders if member.health > 0), key=lambda member: member.health):
            carry_key = (room_key, defender.key)
            # Skills scale both one ordinary attack and its training damage cap,
            # so a charged strike stays a modest burst even with strong weapons.
            capped = (
                min(pool, defender.max_health * 0.05 * max(0, seconds_passed) * cap_multiplier)
                if seconds_passed is not None
                else pool
            )
            carried = self._damage_carry.get(carry_key, 0.0) + capped
            total = int(carried)
            self._damage_carry[carry_key] = carried - total
            before = defender.health
            defender.health = max(0, defender.health - total)
            hits.append((defender, total))
            spill = total - min(total, before)
            if defender.health == 0:
                spill += max(0, pool - capped)
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

    async def _resolve_round(
        self,
        db_session: AsyncSession,
        room: Room,
        team_a: list[ArenaParticipant],
        team_b: list[ArenaParticipant],
        seconds_passed: int,
        *,
        state: ArenaState | None = None,
    ) -> dict:
        # One team attacks each tick. Damage keeps the slower Arena rate and
        # training cap; the defending team can only retaliate on its own turn.
        room_key = str(room.id)
        state = state or await arena_state_crud.get_or_create(db_session, room.id)
        side = state.next_attack_team
        attackers, defenders = (team_a, team_b) if side == "A" else (team_b, team_a)
        seq = self._round_seq.get(room_key, 1)
        db_session.add(
            ArenaMatchEvent(
                room_id=room.id,
                round_seq=seq,
                kind="turn",
                message=f"Team {side} attacks",
            )
        )
        self._resolve_attacks(db_session, room, state, attackers, defenders, seconds_passed, seq)
        state.next_attack_team = "B" if side == "A" else "A"

        knocked_out = set(state.knocked_out_ids or [])
        for participant in (*team_a, *team_b):
            if participant.dweller is None:
                continue
            if participant.health <= 0:
                # Non-lethal arena KO: floor the dweller at 1 HP and record the KO so
                # the fighter stays down without the health tick killing them.
                knocked_out.add(participant.key)
                participant.dweller.health = 1
            else:
                participant.dweller.health = participant.health
            db_session.add(participant.dweller)

        self._round_seq[room_key] = seq + 1

        a_defeated = self._team_defeated(team_a)
        b_defeated = self._team_defeated(team_b)
        if not a_defeated and not b_defeated:
            state.skill_charge = {
                p.key: min(
                    MAX_CHARGE,
                    (state.skill_charge or {}).get(p.key, 0) + max(0, seconds_passed) * charge_per_second(p),
                )
                for p in (*team_a, *team_b)
                if p.dweller is not None and p.health > 0
            }
            standing_ids = {p.key for p in (*team_a, *team_b) if p.health > 0}
            state.queued_skill_ids = [key for key in (state.queued_skill_ids or []) if key in standing_ids] or None
            state.knocked_out_ids = sorted(knocked_out) or None
            db_session.add(state)
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
        # Creatures may sit at 0. The match is marked done so it never re-runs until the
        # fighter selection changes (set_fighters clears the match flags and KOs).
        for participant in (*team_a, *team_b):
            if not participant.is_creature:
                participant.health = max(1, participant.health)
                if participant.dweller is not None:
                    participant.dweller.health = participant.health
        self._clear_room_state(room_key)

        winner = self._representative(winner_team)
        loser = self._representative(loser_team)
        labels = TEAM_LABELS.get(state.mode or ArenaMode.DUEL)
        winner_label = labels[0 if winner_team is team_a else 1] if labels else winner.short_name
        loser_label = labels[0 if loser_team is team_a else 1] if labels else loser.short_name
        state.skill_charge = None
        state.queued_skill_ids = None
        state.last_fight_at = datetime.utcnow()
        state.knocked_out_ids = None
        await self._release_fighters(db_session, state)
        db_session.add(state)

        # Happiness swing instead of caps: the winning team feels great, the losing one is sour.
        for participant in winner_team:
            if participant.dweller is not None:
                participant.dweller.happiness = min(100, participant.dweller.happiness + HAPPINESS_WIN)
                db_session.add(participant.dweller)
        for participant in loser_team:
            if participant.dweller is not None:
                participant.dweller.happiness = max(10, participant.dweller.happiness - HAPPINESS_LOSE)
                db_session.add(participant.dweller)
        winning_dwellers = [participant.dweller for participant in winner_team if participant.dweller is not None]
        reward_messages = []
        if winning_dwellers:
            xp = game_config.combat.xp_per_difficulty * 2
            remainder = 0
            if state.mode == ArenaMode.HUNT:
                pool = int(
                    sum(participant.power for participant in loser_team)
                    / game_config.combat.base_raider_power
                    * game_config.combat.xp_per_difficulty
                )
                xp, remainder = divmod(pool, len(winning_dwellers))
            for index, dweller in enumerate(winning_dwellers):
                awarded = xp + (index < remainder)
                await self._award_combat_xp(db_session, dweller, awarded)
                reward_messages.append(f"{dweller.first_name} +{awarded} XP")

        reward_messages.extend(
            f"{' & '.join(p.short_name for p in team if p.dweller)} happiness {change:+d}"
            for team, change in [(winner_team, HAPPINESS_WIN), (loser_team, -HAPPINESS_LOSE)]
            if any(p.dweller for p in team)
        )

        await self._grant_arena_morale(db_session, room)

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
                message=", ".join(reward_messages),
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

    async def _award_combat_xp(self, db_session: AsyncSession, dweller: Dweller, xp: int) -> None:
        """Award a participant's XP share and settle any resulting level-ups."""
        dweller.experience = max(0, dweller.experience + xp)
        db_session.add(dweller)
        leveled_up, levels_gained = await leveling_service.check_level_up(db_session, dweller)
        if leveled_up:
            await leveling_service.settle_level_up(
                db_session, dweller, old_level=dweller.level - levels_gained, levels_gained=levels_gained
            )

    async def _grant_arena_morale(self, db_session: AsyncSession, room: Room) -> bool:
        """Lift every living vault resident's happiness once per cooldown window.

        Mirrors the exit-request refusal path: a vault-scoped lock serializes the
        cooldown check-and-stamp, the bulk target is ``get_living_in_vault``
        (fighters included — they are living residents too), and the award lands
        in the caller's transaction. Returns whether the bonus was granted.
        """
        bonus = game_config.combat.arena_morale_bonus
        if bonus <= 0:
            return False
        vault = await vault_crud.get(db_session, room.vault_id)
        if vault is None:
            return False
        if not await db_locks.try_advisory_xact_lock(db_session, f"arena-morale:{vault.id}"):
            return False
        now = datetime.now(UTC).replace(tzinfo=None)
        cooldown = timedelta(seconds=game_config.combat.arena_morale_cooldown_seconds)
        if vault.arena_morale_awarded_at is not None and now - vault.arena_morale_awarded_at < cooldown:
            return False
        for member in await crud_dweller.get_living_in_vault(db_session, vault.id):
            member.happiness = min(100, member.happiness + bonus)
            db_session.add(member)
        vault.arena_morale_awarded_at = now
        db_session.add(vault)
        if vault.user_id is not None:
            await NotificationService.notify_arena_morale_boost(
                db_session, vault.user_id, vault.id, room_id=room.id, commit=False
            )
        return True


arena_service = ArenaService()
