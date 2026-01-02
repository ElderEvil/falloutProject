"""Pydantic schemas for relationship management."""

from pydantic import UUID4, ConfigDict
from sqlmodel import SQLModel

from app.models.relationship import RelationshipBase
from app.schemas.common import RelationshipTypeEnum


class RelationshipCreate(SQLModel):
    """Schema for creating a new relationship."""

    dweller_1_id: UUID4
    dweller_2_id: UUID4


class RelationshipUpdate(SQLModel):
    """Schema for updating a relationship."""

    relationship_type: RelationshipTypeEnum | None = None
    affinity: int | None = None

    model_config = ConfigDict(use_enum_values=True)


class RelationshipRead(RelationshipBase):
    """Schema for reading a relationship."""

    id: UUID4

    model_config = ConfigDict(from_attributes=True, use_enum_values=True)


class CompatibilityScore(SQLModel):
    """Compatibility score between two dwellers."""

    dweller_1_id: UUID4
    dweller_2_id: UUID4
    score: float  # 0.0 - 1.0
    special_score: float
    happiness_score: float
    level_score: float
    proximity_score: float


class RelationshipAction(SQLModel):
    """Action to perform on a relationship."""

    action: str  # 'romance', 'partner', 'break_up'
