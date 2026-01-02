from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from pydantic import UUID4
from sqlmodel import Field, Relationship, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.schemas.common import PregnancyStatusEnum

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class PregnancyBase(SQLModel):
    mother_id: UUID4 = Field(sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="CASCADE")))
    father_id: UUID4 = Field(sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="CASCADE")))
    conceived_at: datetime = Field(default_factory=datetime.utcnow)
    due_at: datetime = Field()
    status: PregnancyStatusEnum = Field(default=PregnancyStatusEnum.PREGNANT)


class Pregnancy(BaseUUIDModel, PregnancyBase, TimeStampMixin, table=True):
    """Tracks active pregnancies in the vault."""

    mother: "Dweller" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Pregnancy.mother_id]",
            "primaryjoin": "Pregnancy.mother_id==Dweller.id",
        }
    )
    father: "Dweller" = Relationship(
        sa_relationship_kwargs={
            "foreign_keys": "[Pregnancy.father_id]",
            "primaryjoin": "Pregnancy.father_id==Dweller.id",
        }
    )

    def __str__(self):
        return f"Pregnancy({self.status}): Mother={self.mother_id}, Father={self.father_id}"

    @property
    def is_due(self) -> bool:
        """Check if the pregnancy is due for delivery."""
        due_at = self.due_at.replace(tzinfo=None) if self.due_at.tzinfo else self.due_at
        return datetime.utcnow() >= due_at and self.status == PregnancyStatusEnum.PREGNANT

    @property
    def progress_percentage(self) -> float:
        """Calculate pregnancy progress as a percentage (0-100)."""
        if self.status != PregnancyStatusEnum.PREGNANT:
            return 100.0

        total_duration = (self.due_at - self.conceived_at).total_seconds()
        elapsed = (datetime.utcnow() - self.conceived_at).total_seconds()

        if total_duration <= 0:
            return 100.0

        return min(100.0, (elapsed / total_duration) * 100)

    @property
    def time_remaining_seconds(self) -> int:
        """Calculate remaining time until birth in seconds."""
        if self.status != PregnancyStatusEnum.PREGNANT:
            return 0

        remaining = (self.due_at - datetime.utcnow()).total_seconds()
        return max(0, int(remaining))
