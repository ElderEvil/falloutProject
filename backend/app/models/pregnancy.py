from datetime import datetime
from typing import TYPE_CHECKING
from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, Relationship, SQLModel

from app.core.enums import PregnancyStatusEnum
from app.models.base import BaseUUIDModel, TimeStampMixin
from app.utils.time import as_utc, utcnow
from app.utils.types import UTCDateTime

if TYPE_CHECKING:
    from app.models.dweller import Dweller


class PregnancyBase(SQLModel):
    mother_id: UUID = Field(sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="CASCADE"), index=True))
    father_id: UUID = Field(sa_column=sa.Column(sa.UUID, sa.ForeignKey("dweller.id", ondelete="CASCADE"), index=True))
    conceived_at: datetime = Field(sa_type=UTCDateTime, default_factory=utcnow)
    due_at: datetime = Field(sa_type=UTCDateTime)
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
        return as_utc(utcnow()) >= as_utc(self.due_at) and self.status == PregnancyStatusEnum.PREGNANT

    @property
    def progress_percentage(self) -> float:
        """Calculate pregnancy progress as a percentage (0-100)."""
        if self.status != PregnancyStatusEnum.PREGNANT:
            return 100.0

        conceived_at = as_utc(self.conceived_at)
        total_duration = (as_utc(self.due_at) - conceived_at).total_seconds()
        elapsed = (as_utc(utcnow()) - conceived_at).total_seconds()

        if total_duration <= 0:
            return 100.0

        return min(100.0, (elapsed / total_duration) * 100)

    @property
    def time_remaining_seconds(self) -> int:
        """Calculate remaining time until birth in seconds."""
        if self.status != PregnancyStatusEnum.PREGNANT:
            return 0

        remaining = (as_utc(self.due_at) - as_utc(utcnow())).total_seconds()
        return max(0, int(remaining))
