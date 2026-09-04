"""Durable, concise journal entries for vault incidents."""

from uuid import uuid4

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import TimeStampMixin


class IncidentEvent(TimeStampMixin, table=True):
    """A meaningful incident lifecycle transition, not a per-tick trace."""

    __tablename__ = "incident_event"

    id: UUID4 = Field(default_factory=uuid4, primary_key=True, nullable=False)
    incident_id: UUID4 = Field(foreign_key="incident.id", index=True, ondelete="CASCADE")
    kind: str = Field(index=True, max_length=32)
    message: str = Field(max_length=200)
    data: dict | None = Field(default=None, sa_column=sa.Column(JSONB))
