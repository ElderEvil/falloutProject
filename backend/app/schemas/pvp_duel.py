"""Wire models for cross-vault exhibition duels."""

from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import PvpDuelStatus
from app.utils.serialize_types import OptionalUTCDateTimeJSON, UTCDateTimeJSON


class PvpDuelCreate(BaseModel):
    """A challenge post; ids omitted means the vault's five strongest post for it."""

    defender_vault_id: UUID | None = None
    dweller_ids: list[UUID] | None = Field(default=None, max_length=5)


class PvpDuelAccept(BaseModel):
    """The accepting party; ignored when the post already pre-selected a defender."""

    dweller_ids: list[UUID] | None = Field(default=None, max_length=5)


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
