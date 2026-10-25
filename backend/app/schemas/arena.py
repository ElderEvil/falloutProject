"""Arena request/response schemas."""

from datetime import datetime
from typing import Literal

from pydantic import UUID4, BaseModel, Field

from app.core.enums import ArenaMode
from app.schemas.combat import CombatAction, CombatSkillIcon


class ArenaFightersRequest(BaseModel):
    """Fighter slot selection payload."""

    mode: ArenaMode = ArenaMode.DUEL
    fighter_a_id: UUID4 | None = None
    fighter_b_id: UUID4 | None = None
    fighter_c_id: UUID4 | None = None
    fighter_d_id: UUID4 | None = None
    opponent_keys: list[str] = Field(default_factory=list)
    team_a_bot_key: str | None = None
    team_b_bot_key: str | None = None


class ArenaCreature(BaseModel):
    """A selectable hunt opponent from the creature catalog."""

    key: str
    name: str
    power: float
    max_hp: int
    is_robot: bool = False


class ArenaActiveSkill(BaseModel):
    """Weapon-derived manual attack and its match-local charge."""

    name: str
    icon: CombatSkillIcon = "unarmed"
    description: str
    charge: int = Field(ge=0, le=100)
    queued: bool


class ArenaSkillRequest(BaseModel):
    """Select a participating dweller to use their active skill."""

    fighter_id: UUID4


class ArenaSkillQueued(BaseModel):
    """The attack will resolve on the fighter's next team turn."""

    room_id: str
    fighter_id: str


class ArenaFighter(BaseModel):
    """A single selected fighter with live HP and combat power."""

    id: str
    name: str
    level: int
    health: int
    max_health: int
    power: float
    active_skill: ArenaActiveSkill | None = None
    is_creature: bool = False
    is_robot: bool = False
    image_url: str | None = None
    thumbnail_url: str | None = None
    age_group: str | None = None
    race: str | None = None


class ArenaRosterEntry(BaseModel):
    """An adult dweller assigned to the arena room, available to pick."""

    id: str
    name: str
    level: int
    health: int
    max_health: int
    image_url: str | None = None
    thumbnail_url: str | None = None
    age_group: str | None = None
    race: str | None = None


class ArenaMatchEventOut(BaseModel):
    """One battle journal line."""

    id: str
    round_seq: int
    kind: str
    message: str
    actor_id: str | None = None
    action: CombatAction | None = None
    created_at: datetime | None = None


class ArenaRoomState(BaseModel):
    """Full arena room state: fighters, roster, match flags, and journal."""

    room_id: str
    room_name: str
    tier: int
    mode: str
    available_modes: list[ArenaMode]
    next_attack_team: Literal["A", "B"] = "A"
    fighter_a_id: str | None
    fighter_b_id: str | None
    fighters: list[ArenaFighter]
    team_a: list[ArenaFighter]
    team_b: list[ArenaFighter]
    roster: list[ArenaRosterEntry]
    fight_ready: bool
    match_done: bool
    fight_started: bool
    countdown_remaining: int
    can_start: bool
    winner_name: str | None
    events: list[ArenaMatchEventOut]


class ArenaState(BaseModel):
    """All arena rooms in a vault."""

    rooms: list[ArenaRoomState]


class ArenaFightersResponse(BaseModel):
    """Updated fighter slot selection for one arena room."""

    room_id: str
    fighter_a_id: str | None
    fighter_b_id: str | None


class ArenaEventsCleared(BaseModel):
    """Journal clear result."""

    room_id: str
    cleared: int


class ArenaFightStarted(BaseModel):
    """Result of arming an arena match."""

    room_id: str
    started: bool


class ArenaFightStopped(BaseModel):
    """Result of cancelling an active arena match."""

    room_id: str
    stopped: bool
