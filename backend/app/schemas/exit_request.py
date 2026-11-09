"""Schemas for dwellers who ask to leave the vault."""

from uuid import UUID

from pydantic import BaseModel

from app.utils.serialize_types import OptionalUTCDateTimeJSON


class ExitRequestRead(BaseModel):
    """A dweller waiting on the vault's answer."""

    dweller_id: UUID
    dweller_name: str
    thumbnail_url: str | None = None
    level: int
    happiness: int
    requested_at: OptionalUTCDateTimeJSON = None
    refusal_happiness_penalty: int


class ExitDecisionResponse(BaseModel):
    """Outcome of granting or refusing one exit request."""

    dweller_id: UUID
    dweller_name: str
    granted: bool
    happiness: int
    epitaph: str | None = None
