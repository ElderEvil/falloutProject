"""Wire models for cross-vault exhibition duels."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import PvpDuelStatus
from app.utils.serialize_types import OptionalUTCDateTimeJSON, UTCDateTimeJSON


class PvpDuelCreate(BaseModel):
    """The posting party: same contract as an expedition dispatch — 1-3 dwellers, no leader."""

    defender_vault_id: UUID | None = None
    dweller_ids: list[UUID] = Field(min_length=1, max_length=3, description="Party of 1-3 dwellers, no leader")


class PvpDuelAccept(BaseModel):
    """The accepting party: same contract, and the same sheet a dispatch would use."""

    dweller_ids: list[UUID] = Field(min_length=1, max_length=3, description="Party of 1-3 dwellers, no leader")


class PvpPartyRead(BaseModel):
    """A side as the board may show it: names and a coarse band, never exact power."""

    vault_name: str
    party_size: int
    member_names: list[str]
    power_band: str


class PvpDuelBoardEntry(BaseModel):
    """One open challenge in the discovery list."""

    duel_id: UUID
    challenger_vault_name: str
    party_size: int
    member_names: list[str]
    power_band: str
    expires_at: UTCDateTimeJSON


class PvpDuelRead(BaseModel):
    """A duel with its frozen parties and (once settled) its journal."""

    duel_id: UUID
    status: PvpDuelStatus
    outcome: str | None = None
    challenger_vault_id: UUID
    defender_vault_id: UUID | None = None
    challenger_party: PvpPartyRead
    defender_party: PvpPartyRead | None = None
    journal: list[dict[str, Any]] | None = None
    created_at: OptionalUTCDateTimeJSON = None
    accepted_at: OptionalUTCDateTimeJSON = None
    expires_at: UTCDateTimeJSON
