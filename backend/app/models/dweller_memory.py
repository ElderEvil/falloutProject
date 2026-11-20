"""Dweller memory: durable first-person facts a dweller retains about itself."""

from uuid import UUID

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class DwellerMemoryBase(SQLModel):
    dweller_id: UUID = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")
    fact: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    fact_hash: str = Field(max_length=64)
    source_message_id: UUID | None = Field(default=None, foreign_key="chatmessage.id")


class DwellerMemory(BaseUUIDModel, DwellerMemoryBase, TimeStampMixin, table=True):
    """One durable first-person fact a dweller knows about itself."""

    __tablename__ = "dweller_memory"
    __table_args__ = (sa.UniqueConstraint("dweller_id", "fact_hash", name="uq_memory_fact"),)
