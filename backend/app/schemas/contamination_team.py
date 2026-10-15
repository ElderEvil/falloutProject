"""Contamination team roster schemas."""

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.core.enums import HazardTeam


class HazardTeamMemberRead(SQLModel):
    dweller_id: UUID4
    status: str
    name: str
    level: int
    service_count: int = Field(default=0, description="Distinct incidents of this team's hazard the dweller has fought")
    outfit_name: str | None = Field(
        default=None, description="Name of the currently equipped outfit, or null when the dweller is bare"
    )
    has_matching_gear: bool = Field(
        default=False,
        description="Wearing this team's named matching suit; false does NOT mean zero protection",
    )
    hazard_resist: float = Field(
        default=0.0, description="Share (0.0-1.0) of this team's hazard the current outfit removes"
    )


class HazardTeamRosterRead(SQLModel):
    team: HazardTeam
    active: list[HazardTeamMemberRead]
    reserve: list[HazardTeamMemberRead]


class HazardTeamPlaceUpdate(SQLModel):
    """Manual Active/Reserve move for one hazard-team member."""

    active: bool


class ContaminationTeamRead(SQLModel):
    vault_id: UUID4
    teams: list[HazardTeamRosterRead]
