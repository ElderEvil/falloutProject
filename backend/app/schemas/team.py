"""Read shapes for the reusable team roster primitive.

The quest endpoints keep ``QuestPartyMemberRead`` as their wire contract; this
module holds the internal read shape used when a service hands a ``TeamMember``
back to the API layer.
"""

from datetime import datetime

from pydantic import UUID4
from sqlmodel import SQLModel


class TeamMemberRead(SQLModel):
    """A team member as returned by team services."""

    id: UUID4
    team_id: UUID4
    dweller_id: UUID4
    slot_number: int | None = None
    status: str
    created_at: datetime | None = None
    updated_at: datetime | None = None
