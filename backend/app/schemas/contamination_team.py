"""Contamination team roster schemas."""

from pydantic import UUID4
from sqlmodel import SQLModel

from app.core.enums import HazardTeam


class HazardTeamMemberRead(SQLModel):
    dweller_id: UUID4
    status: str
    name: str
    level: int


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
