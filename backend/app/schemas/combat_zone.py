"""Combat Zone request/response schemas.

Wire models are Pydantic rather than SQLModel: the lobby and match views are
assembled from several rows and expose display fields (vault number, dweller
name, power) that no single table owns.
"""

from datetime import datetime

from pydantic import UUID4, BaseModel, Field

from app.core.enums import CombatZonePartyStatus, CombatZoneStance


class CombatZoneSendRequest(BaseModel):
    """Send one dweller to the Zone."""

    dweller_id: UUID4


class CombatZoneStanceRequest(BaseModel):
    """Change the party's command; applies from the next micro-round."""

    stance: CombatZoneStance


class CombatZonePartyRead(BaseModel):
    """A vault's party as shown on its own dashboard."""

    id: UUID4
    vault_id: UUID4
    vault_number: int
    dweller_id: UUID4 | None
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

    party_id: UUID4
    vault_number: int
    dweller_name: str
    level: int
    power: float
    stance: CombatZoneStance
    queued_seconds: int


class CombatZoneMatchSummary(BaseModel):
    """One live match on the shared board."""

    match_id: UUID4
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
    """One side of a match with its live state."""

    party_id: UUID4
    vault_id: UUID4
    vault_number: int
    dweller_id: UUID4 | None
    dweller_name: str
    level: int
    health: int
    max_health: int
    power: float
    stance: CombatZoneStance
    is_winner: bool = False


class CombatZoneEventRead(BaseModel):
    """One journal line."""

    id: UUID4
    round_seq: int
    kind: str
    message: str
    created_at: datetime | None = None


class CombatZoneMatchRead(BaseModel):
    """Full spectate payload for one match."""

    id: UUID4
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


class CombatZoneVaultToggleRequest(BaseModel):
    """Admin switch for one vault; the global flag remains the master switch."""

    enabled: bool


class CombatZoneVaultToggleRead(BaseModel):
    vault_id: UUID4
    enabled: bool
