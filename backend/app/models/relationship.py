from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.schemas.common import RelationshipTypeEnum

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class RelationshipBase(SQLModel):
    dweller_1_id: UUID4 = Field(sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="CASCADE")))
    dweller_2_id: UUID4 = Field(sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="CASCADE")))
    relationship_type: RelationshipTypeEnum = Field(default=RelationshipTypeEnum.ACQUAINTANCE)
    affinity: int = Field(default=0, ge=0, le=100)


class Relationship(BaseUUIDModel, RelationshipBase, TimeStampMixin, table=True):
    """Tracks relationships between two dwellers."""

    dweller_1: "Dweller" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Relationship.dweller_1_id]",
            "primaryjoin": "Relationship.dweller_1_id==Dweller.id",
        }
    )
    dweller_2: "Dweller" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Relationship.dweller_2_id]",
            "primaryjoin": "Relationship.dweller_2_id==Dweller.id",
        }
    )

    def __str__(self):
        return f"Relationship({self.relationship_type}): {self.dweller_1_id} <-> {self.dweller_2_id}"
