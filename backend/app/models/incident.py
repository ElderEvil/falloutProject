"""Incident models for combat events and vault disasters."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel

from app.core.enums import HazardTeam
from app.models.base import BaseUUIDModel, TimeStampMixin

if TYPE_CHECKING:
    from app.models.team import Team


class IncidentType(StrEnum):
    """Types of incidents that can occur in the vault."""

    RAIDER_ATTACK = "raider_attack"
    RADROACH_INFESTATION = "radroach_infestation"
    MOLE_RAT_ATTACK = "mole_rat_attack"
    DEATHCLAW_ATTACK = "deathclaw_attack"
    FERAL_GHOUL_ATTACK = "feral_ghoul_attack"
    RADSCORPION_ATTACK = "radscorpion_attack"
    FIRE = "fire"


class IncidentStatus(StrEnum):
    """Status of an incident."""

    ACTIVE = "active"
    SPREADING = "spreading"
    RESOLVED = "resolved"
    FAILED = "failed"


class IncidentFamily(StrEnum):
    """Operational family used to present an incident truthfully."""

    HAZARD = "hazard"
    INFESTATION = "infestation"
    INTRUSION = "intrusion"


class IncidentObjective(StrEnum):
    """The single action outcome the player is working toward."""

    CONTAIN = "contain"
    DEFEAT = "defeat"


@dataclass(frozen=True)
class IncidentDefinition:
    family: IncidentFamily
    objective: IncidentObjective
    progress_label: str
    response_label: str
    risk_kind: str


INCIDENT_DEFINITIONS: dict[IncidentType, IncidentDefinition] = {
    IncidentType.FIRE: IncidentDefinition(
        IncidentFamily.HAZARD, IncidentObjective.CONTAIN, "Fire contained", "Send responders", "spread"
    ),
    IncidentType.RADROACH_INFESTATION: IncidentDefinition(
        IncidentFamily.INFESTATION, IncidentObjective.DEFEAT, "Infestation contained", "Send responders", "spread"
    ),
    IncidentType.MOLE_RAT_ATTACK: IncidentDefinition(
        IncidentFamily.INFESTATION, IncidentObjective.DEFEAT, "Infestation contained", "Send responders", "spread"
    ),
    IncidentType.RADSCORPION_ATTACK: IncidentDefinition(
        IncidentFamily.INFESTATION, IncidentObjective.DEFEAT, "Infestation contained", "Send responders", "radiation"
    ),
    IncidentType.RAIDER_ATTACK: IncidentDefinition(
        IncidentFamily.INTRUSION, IncidentObjective.DEFEAT, "Intruders neutralized", "Send defenders", "breach"
    ),
    IncidentType.DEATHCLAW_ATTACK: IncidentDefinition(
        IncidentFamily.INTRUSION, IncidentObjective.DEFEAT, "Intruders neutralized", "Send defenders", "breach"
    ),
    IncidentType.FERAL_GHOUL_ATTACK: IncidentDefinition(
        IncidentFamily.INTRUSION, IncidentObjective.DEFEAT, "Intruders neutralized", "Send defenders", "breach"
    ),
}


def get_incident_definition(incident_type: IncidentType) -> IncidentDefinition:
    """Return the UI and rules contract for an incident type."""
    return INCIDENT_DEFINITIONS[incident_type]


#: Incident types that train a standing hazard team, keyed to the team they feed.
#: Only genuinely contaminating hazards qualify: intruder and infestation combat
#: (raiders, roaches, mole rats, ghouls, deathclaws) earns no team place.
HAZARD_TEAM_INCIDENT_TYPES: dict[HazardTeam, frozenset[IncidentType]] = {
    HazardTeam.FIRE: frozenset({IncidentType.FIRE}),
    HazardTeam.RADIATION: frozenset({IncidentType.RADSCORPION_ATTACK}),
}

#: Reverse lookup: incident type → the team it trains, when it trains one.
_TEAM_BY_INCIDENT_TYPE: dict[IncidentType, HazardTeam] = {
    incident_type: team
    for team, incident_types in HAZARD_TEAM_INCIDENT_TYPES.items()
    for incident_type in incident_types
}


def hazard_team_for(incident_type: IncidentType) -> HazardTeam | None:
    """The team an incident type trains, or None when it is not a contamination hazard."""
    return _TEAM_BY_INCIDENT_TYPE.get(incident_type)


class IncidentBase(SQLModel):
    """Base model for incidents."""

    type: IncidentType = Field(index=True)
    status: IncidentStatus = Field(default=IncidentStatus.ACTIVE, index=True)
    difficulty: int = Field(ge=1, le=10, description="Difficulty level of the incident")
    start_time: datetime = Field(default_factory=datetime.utcnow)
    end_time: datetime | None = Field(default=None)
    duration: int = Field(default=60, ge=10, description="Duration in seconds before auto-spreading")

    # Damage tracking
    damage_dealt: int = Field(default=0, ge=0, description="Total damage dealt to dwellers")
    enemies_defeated: int = Field(default=0, ge=0, description="Number of enemies defeated")
    combat_progress: float = Field(
        default=0.0,
        ge=0.0,
        description="Cumulative fractional enemies defeated (survives int truncation between ticks)",
    )

    # Loot/rewards
    loot: dict | None = Field(default=None, sa_column=sa.Column(JSONB), description="Rewards from incident")
    # Overflow loot awaiting a per-item take/sell decision in the aftermath.
    unclaimed_loot: list[dict] = Field(
        default_factory=list,
        sa_column=sa.Column(JSONB, nullable=False),
    )

    # Spread tracking
    rooms_affected: list[str] = Field(default_factory=list, sa_column=sa.Column(JSONB))
    spread_count: int = Field(default=0, ge=0, description="Number of times incident has spread")


class Incident(BaseUUIDModel, IncidentBase, TimeStampMixin, table=True):
    """Incident model with relationships."""

    vault_id: UUID4 = Field(foreign_key="vault.id", index=True, ondelete="CASCADE")
    room_id: UUID4 = Field(foreign_key="room.id", index=True, ondelete="CASCADE")

    # Relationships
    teams: list["Team"] = Relationship(
        back_populates="incident",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )

    def is_active(self) -> bool:
        """Check if incident is still active."""
        return self.status == IncidentStatus.ACTIVE

    def elapsed_time(self) -> int:
        """Calculate elapsed time since incident started."""
        return int((datetime.utcnow() - self.start_time).total_seconds())

    def should_spread(self) -> bool:
        """Check if incident should spread to adjacent rooms."""
        return self.is_active() and self.elapsed_time() >= self.duration

    def resolve(self, success: bool = True) -> None:
        """Resolve the incident."""
        self.status = IncidentStatus.RESOLVED if success else IncidentStatus.FAILED
        self.end_time = datetime.utcnow()

    def spread_to_room(self, room_id: str) -> None:
        """Mark incident as spreading to a new room."""
        if room_id not in self.rooms_affected:
            self.rooms_affected.append(room_id)
            self.spread_count += 1
            self.status = IncidentStatus.SPREADING


class IncidentParticipant(BaseUUIDModel, TimeStampMixin, table=True):
    """A dweller who stood in an incident as a defender.

    There is no other ledger of participation: responders are re-resolved from
    room occupancy every round, so this row is the only durable record of who
    actually fought. One row per (incident, dweller) so a long incident cannot
    count twice, written inside the round's transaction so a round that fails
    leaves no trace.
    """

    __tablename__ = "incident_participant"

    incident_id: UUID4 = Field(foreign_key="incident.id", index=True, ondelete="CASCADE")
    dweller_id: UUID4 = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")

    __table_args__ = (sa.UniqueConstraint("incident_id", "dweller_id", name="uq_incident_participant"),)
