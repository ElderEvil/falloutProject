"""Reusable team roster primitive: a named squad of dwellers for one purpose.

A ``Team`` serves exactly one purpose — a quest or an incident — enforced by
``ck_team_one_purpose``. Quest teams are one per ``(vault_id, quest_id)``
(``uq_team_vault_quest``); incident teams are one per ``(vault_id, incident_id)``
(``uq_team_vault_incident``) and cascade with their incident.
"""

from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, Relationship

from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.incident import Incident
    from app.models.quest import Quest
    from app.models.vault import Vault


class Team(BaseUUIDModel, TimeStampMixin, table=True):
    """A roster of dwellers gathered for one quest or incident."""

    __tablename__ = "team"

    vault_id: UUID4 = Field(
        foreign_key="vault.id",
        index=True,
        ondelete="CASCADE",
        description="Vault the team belongs to",
    )
    quest_id: UUID4 | None = Field(
        default=None,
        foreign_key="quest.id",
        index=True,
        ondelete="CASCADE",
        description="Quest this team is assigned to, when quest-purposed",
    )
    incident_id: UUID4 | None = Field(
        default=None,
        foreign_key="incident.id",
        index=True,
        ondelete="CASCADE",
        description="Incident this team is assigned to, when incident-purposed",
    )
    name: str | None = Field(default=None, max_length=64, description="Optional display name")

    # Relationships
    vault: "Vault" = Relationship(back_populates="teams")
    quest: Optional["Quest"] = Relationship(back_populates="teams")
    incident: Optional["Incident"] = Relationship(back_populates="teams")
    members: list["TeamMember"] = Relationship(
        back_populates="team",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    # One team per (vault, quest) and per (vault, incident); exactly one purpose.
    __table_args__ = (
        sa.UniqueConstraint("vault_id", "quest_id", name="uq_team_vault_quest"),
        sa.UniqueConstraint("vault_id", "incident_id", name="uq_team_vault_incident"),
        sa.CheckConstraint(
            "(CASE WHEN quest_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN incident_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_team_one_purpose",
        ),
    )


class TeamMember(BaseUUIDModel, TimeStampMixin, table=True):
    """One dweller's slot on a team roster."""

    __tablename__ = "team_member"

    team_id: UUID4 = Field(
        foreign_key="team.id",
        index=True,
        ondelete="CASCADE",
        description="Team this member belongs to",
    )
    dweller_id: UUID4 = Field(
        foreign_key="dweller.id",
        index=True,
        ondelete="CASCADE",
        description="Dweller filling this slot",
    )
    slot_number: int | None = Field(default=None, description="Team slot 1-3")
    status: str = Field(default="assigned", description="assigned, in_progress, completed, failed")

    # Relationships
    team: "Team" = Relationship(back_populates="members")
    dweller: "Dweller" = Relationship(back_populates="team_memberships")

    # One dweller per team, and one dweller per slot.
    __table_args__ = (
        sa.UniqueConstraint("team_id", "dweller_id", name="uq_team_member_dweller"),
        sa.UniqueConstraint("team_id", "slot_number", name="uq_team_member_slot"),
    )
