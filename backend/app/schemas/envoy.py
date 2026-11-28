"""Wire models for the Envoy Terminal: signals, filings and the effective knobs."""

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.enums import DiplomaticFilingKind, DiplomaticFilingStatus, VaultRelationStatus
from app.utils.serialize_types import OptionalUTCDateTimeJSON, UTCDateTimeJSON


class EnvoySignalRead(BaseModel):
    """One live vault on the atlas with this vault's relation to it."""

    vault_id: UUID
    number: int
    owner_username: str
    status: VaultRelationStatus
    standing: int
    distance: float | None = Field(
        default=None, description="Registry units between vault slots; null when this vault has no slot"
    )
    can_hail: bool = Field(description="In radio range, not locked, and still unmet")
    incoming_hail: bool = Field(description="A hail from that vault is waiting for an answer")
    met_at: OptionalUTCDateTimeJSON = None
    locked_until: OptionalUTCDateTimeJSON = None


class EnvoyFilingRead(BaseModel):
    """One filing with its terms and answer."""

    filing_id: UUID
    kind: DiplomaticFilingKind
    status: DiplomaticFilingStatus
    from_vault_id: UUID
    to_vault_id: UUID
    terms: dict[str, Any]
    incoming: bool = Field(description="True when this vault is the recipient")
    created_at: OptionalUTCDateTimeJSON = None
    expires_at: UTCDateTimeJSON
    responded_at: OptionalUTCDateTimeJSON = None


class EnvoyHailCreate(BaseModel):
    """Open a line to one vault in radio range."""

    target_vault_id: UUID


class EnvoyFilingRespond(BaseModel):
    """Answer a filing: accepted opens the standoff, refused locks the line."""

    accept: bool


class EnvoyConfigRead(BaseModel):
    """The effective diplomacy knobs, so the terminal renders the server's actual rule."""

    enabled: bool
    trade_gate: Literal["standoff", "accord", "compact"]
    hail_radius: float
    filing_ttl_hours: int
    refusal_lock_hours: int
    repropose_hours: int
    ceasefire_days: int
    war_upkeep_per_level: int
    footing_penalty_pct: int
    fatigue_start_days: int
    fatigue_ramp_days: int
    arbitration_day: int
    accord_upkeep: int
    compact_upkeep: int
    unjust_war_multiplier: int
    stake_pct: int
    stake_min: int
    stake_max: int
