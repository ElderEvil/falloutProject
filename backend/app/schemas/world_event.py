"""Read models for server-wide co-op world events."""

from typing import Any
from uuid import UUID

from sqlmodel import Field, SQLModel

from app.core.enums import WorldEventStatus
from app.utils.serialize_types import OptionalUTCDateTimeJSON


class WorldEventRead(SQLModel):
    """Global progress plus this vault's standing for the current or latest world event.

    Every event field is optional so an empty table yields a well-formed "no event" body
    instead of an error; ``event_id``/``kind``/``title``/``description`` stay stable once an
    event exists, including after it completes (the claim UI keeps reading it).
    """

    event_id: UUID | None = None
    kind: str | None = None
    title: str | None = None
    description: str | None = None
    target_amount: int = 0
    progress_amount: int = 0
    participant_count: int = 0
    contribution: int = 0
    personal_min: int = 0
    can_claim: bool = False
    status: WorldEventStatus | None = None
    starts_at: OptionalUTCDateTimeJSON = None
    ends_at: OptionalUTCDateTimeJSON = None
    extended_at: OptionalUTCDateTimeJSON = None
    reward: list[dict[str, Any]] = Field(default_factory=list)


class WorldEventClaimRead(SQLModel):
    """Outcome of a successful one-time world event reward claim."""

    event_id: UUID
    claimed: bool = True
    contribution: int = 0
    rewards: list[dict[str, Any]] = Field(default_factory=list)
