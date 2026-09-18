"""Standing hazard-team roster."""

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field

from app.core.enums import HazardTeam
from app.models.base import BaseUUIDModel, TimeStampMixin

ACTIVE_STATUS = "active"
RESERVE_STATUS = "reserve"


class HazardTeamMember(BaseUUIDModel, TimeStampMixin, table=True):
    """A dweller who earned a place on a hazard team.

    ``active`` members hold the team's slots; ``reserve`` members qualified but
    wait for one to free up. A dweller may hold a place on both teams —
    qualification is per hazard — but never twice on the same team.
    """

    __tablename__ = "hazard_team_member"

    vault_id: UUID4 = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")
    team: HazardTeam = Field(index=True)
    status: str = Field(default=ACTIVE_STATUS, description="active or reserve")

    __table_args__ = (sa.UniqueConstraint("vault_id", "team", "dweller_id", name="uq_hazard_team_dweller"),)
