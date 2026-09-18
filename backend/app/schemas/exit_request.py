"""Schemas for dwellers who ask to leave the vault."""

from datetime import datetime

from pydantic import UUID4, BaseModel, Field


class ExitRequestRead(BaseModel):
    """A dweller waiting on the vault's answer."""

    dweller_id: UUID4
    dweller_name: str
    thumbnail_url: str | None = None
    level: int
    happiness: int
    requested_at: datetime | None = None


class ExitRequestListResponse(BaseModel):
    """Every dweller currently waiting on an answer."""

    requests: list[ExitRequestRead] = Field(default_factory=list)


class ExitDecisionResponse(BaseModel):
    """Outcome of granting or refusing one exit request."""

    dweller_id: UUID4
    dweller_name: str
    granted: bool
    happiness: int
    epitaph: str | None = None
