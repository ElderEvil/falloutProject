"""Internal team-roster read shapes; quest endpoints keep QuestPartyMemberRead
as their wire contract.
"""

from uuid import UUID

from sqlmodel import SQLModel

from app.utils.serialize_types import OptionalUTCDateTimeJSON


class TeamMemberRead(SQLModel):
    """A team member as returned by team services."""

    id: UUID
    team_id: UUID
    dweller_id: UUID
    slot_number: int | None = None
    status: str
    created_at: OptionalUTCDateTimeJSON = None
    updated_at: OptionalUTCDateTimeJSON = None
