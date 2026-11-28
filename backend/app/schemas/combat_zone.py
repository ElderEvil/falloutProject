"""Combat Zone request/response schemas.

Wire models are Pydantic rather than SQLModel: the lobby and match views are
assembled from several rows and expose display fields (vault number, dweller
name, power) that no single table owns.
"""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import CombatZonePartyStatus, CombatZoneStance
from app.schemas.arena import ArenaFighter
from app.schemas.combat import CombatAction


class CombatZoneSendRequest(BaseModel):
    """Send one dweller to the Zone."""

    dweller_id: UUID


class CombatZoneStanceRequest(BaseModel):
    """Change the party's command; applies from the next micro-round."""

    stance: CombatZoneStance


class CombatZonePartyRead(BaseModel):
    """A vault's party as shown on its own dashboard."""

    id: UUID
    vault_id: UUID
    vault_number: int
    dweller_id: UUID | None
    dweller_name: str
    level: int
    health: int
    max_health: int
    power: float
    status: CombatZonePartyStatus
    stance: CombatZoneStance
    arrives_at: datetime | None = None
    escrow_caps: int


class CombatZoneLobbyParty(BaseModel):
    """A queued party as seen on the shared board."""

    party_id: UUID
    vault_number: int
    dweller_name: str
    level: int
    power: float
    stance: CombatZoneStance
    queued_seconds: int


class CombatZoneMatchSummary(BaseModel):
    """One live match on the shared board."""

    match_id: UUID
    vault_a_number: int
    vault_b_number: int
    dweller_a_name: str
    dweller_b_name: str
    pot_caps: int
    round_seq: int
    started_at: datetime | None = None


class CombatZoneLobbyRead(BaseModel):
    """The open board: who is waiting and what is being fought right now."""

    enabled: bool
    server_time: datetime
    entry_fee_caps: int
    travel_seconds: int
    queued: list[CombatZoneLobbyParty]
    active_matches: list[CombatZoneMatchSummary]


class CombatZoneMatchPartyRead(BaseModel):
    """One side of a match: the canonical fighter plus Combat Zone identity and stance."""

    fighter: ArenaFighter
    party_id: UUID
    vault_id: UUID
    vault_number: int
    dweller_id: UUID | None
    stance: CombatZoneStance
    is_winner: bool = False
    credited_caps: int | None = None


class CombatZoneCursor(BaseModel):
    """Authoritative snapshot position for polling and terminal resync."""

    sequence: int
    round_seq: int
    status: str


class CombatZoneEventRead(BaseModel):
    """One journal line with its replay payload."""

    id: UUID
    sequence: int
    round_seq: int
    kind: str
    message: str
    action: CombatAction | None = None
    created_at: datetime | None = None


class CombatZoneMatchRead(BaseModel):
    """Full spectate payload for one match."""

    id: UUID
    status: str
    round_seq: int
    next_attack_party: str
    pot_caps: int
    finish_reason: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    max_ends_at: datetime | None = None
    party_a: CombatZoneMatchPartyRead
    party_b: CombatZoneMatchPartyRead
    events: list[CombatZoneEventRead] = Field(default_factory=list)
    cursor: CombatZoneCursor


class CombatZoneHistoryEntry(BaseModel):
    """A finished bout for the viewing vault; journal stays on the detail read."""

    match_id: UUID
    finish_reason: str | None = None
    pot_caps: int
    round_seq: int
    winner_party_id: UUID | None = None
    party_a: CombatZoneMatchPartyRead
    party_b: CombatZoneMatchPartyRead
    started_at: datetime | None = None
    finished_at: datetime | None = None
