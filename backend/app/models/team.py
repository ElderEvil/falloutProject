"""Reusable team roster primitive: a named squad of dwellers for one purpose.

A ``Team`` serves exactly one purpose — a quest, an incident, a standing
hazard team, or an exploration dispatch — enforced by ``ck_team_one_purpose``.
Quest teams are one per ``(vault_id, quest_id)`` (``uq_team_vault_quest``);
incident teams are one per ``(vault_id, incident_id)`` (``uq_team_vault_incident``)
and cascade with their incident; hazard teams are one per ``(vault_id, hazard_team)``
(``uq_team_vault_hazard``) and hold the earned fire/radiation rosters; dispatch
teams are one per ``(vault_id, exploration_id)`` (``uq_team_vault_exploration``).
"""

from typing import TYPE_CHECKING, Optional

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, Relationship

from app.core.enums import HazardTeam
from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.dweller import Dweller
    from app.models.incident import Incident
    from app.models.quest import Quest
    from app.models.vault import Vault

#: Shared membership-status vocabulary for every team purpose, homed here.
#: Quest/incident lifecycle: a member is ``assigned``, then ``in_progress``,
#: ``completed``, or ``failed``. Hazard teams use ``active`` (holds a slot) and
#: ``reserve`` (bench).
ACTIVE_STATUS = "active"
RESERVE_STATUS = "reserve"


class Team(BaseUUIDModel, TimeStampMixin, table=True):
    """A roster of dwellers gathered for one quest, incident, hazard team, or dispatch."""

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
    hazard_team: HazardTeam | None = Field(
        default=None,
        index=True,
        description="Standing hazard team this roster holds, when hazard-purposed",
    )
    # ADR: dispatch parties reuse the Team roster instead of a JSON party list.
    # One party mechanism for every purpose (quest/incident/hazard/dispatch)
    # keeps slot order (slot_number 1..N, anchor first) and the existing schema
    # guards (one dweller per slot, one team per exploration) for free. Cost:
    # the anchor is tracked twice (exploration.dweller_id + team slot 1), a team
    # row exists per dispatch even for solo runs, and the team is deleted at
    # finalize.
    # Deliberately a plain UUID, NOT a foreign key: a real FK would create a
    # team -> exploration -> team cycle that breaks SQLModel.metadata.create_all
    # on SQLite (the test suite's schema builder). Integrity is app-enforced —
    # the team is created with the exploration in one transaction and deleted at
    # finalize — plus the uq_team_vault_exploration unique constraint.
    exploration_id: UUID4 | None = Field(
        default=None,
        index=True,
        description="Exploration this team is dispatched on, when exploration-purposed",
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

    # One team per (vault, quest), per (vault, incident), per (vault, hazard),
    # and per (vault, exploration); exactly one purpose.
    __table_args__ = (
        sa.UniqueConstraint("vault_id", "quest_id", name="uq_team_vault_quest"),
        sa.UniqueConstraint("vault_id", "incident_id", name="uq_team_vault_incident"),
        sa.UniqueConstraint("vault_id", "hazard_team", name="uq_team_vault_hazard"),
        sa.UniqueConstraint("vault_id", "exploration_id", name="uq_team_vault_exploration"),
        sa.CheckConstraint(
            "(CASE WHEN quest_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN incident_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN hazard_team IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN exploration_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_team_one_purpose",
        ),
    )


class TeamMember(BaseUUIDModel, TimeStampMixin, table=True):
    """One dweller's slot on a team roster.

    ``slot_number`` is purpose-scoped: for hazard teams it mirrors placement —
    1-3 for ``active`` members (assigned in seniority order by ``created_at``),
    ``NULL`` for ``reserve`` bench members. For incident teams it is always
    ``NULL`` ("no fixed slot", see ``crud/team.py:add_incident_team_members``).
    Quest teams use it for the party slot.
    """

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
    status: str = Field(
        default="assigned",
        description="assigned, in_progress, completed, failed (quest/incident); active, reserve (hazard)",
    )

    # Relationships
    team: "Team" = Relationship(back_populates="members")
    dweller: "Dweller" = Relationship(back_populates="team_memberships")

    # One dweller per team, and one dweller per slot.
    __table_args__ = (
        sa.UniqueConstraint("team_id", "dweller_id", name="uq_team_member_dweller"),
        sa.UniqueConstraint("team_id", "slot_number", name="uq_team_member_slot"),
    )
