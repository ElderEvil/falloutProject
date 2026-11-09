"""Durable, concise journal entries for vault incidents."""

from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import TimeStampMixin


class IncidentEvent(TimeStampMixin, table=True):
    """A meaningful incident lifecycle transition, not a per-tick trace."""

    __tablename__ = "incident_event"

    id: UUID = Field(default_factory=uuid4, primary_key=True, nullable=False)
    incident_id: UUID = Field(foreign_key="incident.id", index=True, ondelete="CASCADE")
    kind: str = Field(index=True, max_length=32)
    message: str = Field(max_length=200)
    data: dict | None = Field(default=None, sa_column=sa.Column(JSONB))
