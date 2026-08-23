"""Arena request/response schemas."""

from pydantic import UUID4, BaseModel


class ArenaFightersRequest(BaseModel):
    """Fighter slot selection payload."""

    fighter_a_id: UUID4 | None = None
    fighter_b_id: UUID4 | None = None


class ArenaFighter(BaseModel):
    """A single selected fighter with live HP and combat power."""

    id: str
    name: str
    level: int
    health: int
    max_health: int
    power: float


class ArenaRosterEntry(BaseModel):
    """An adult dweller assigned to the arena room, available to pick."""

    id: str
    name: str
    level: int
    health: int
    max_health: int


class ArenaMatchEventOut(BaseModel):
    """One battle journal line."""

    id: str
    round_seq: int
    kind: str
    message: str


class ArenaRoomState(BaseModel):
    """Full arena room state: fighters, roster, match flags, and journal."""

    room_id: str
    room_name: str
    tier: int
    fighter_a_id: str | None
    fighter_b_id: str | None
    fighters: list[ArenaFighter]
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
