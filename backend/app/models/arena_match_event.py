"""Arena match event model - battle journal entries for arena fights."""

from uuid import uuid4

import sqlalchemy as sa
from pydantic import UUID4
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

from app.models.base import TimeStampMixin


class ArenaMatchEvent(TimeStampMixin, table=True):
    """One line in the arena battle journal."""

    __tablename__ = "arena_match_event"

    id: UUID4 = Field(default_factory=uuid4, primary_key=True, nullable=False)
    room_id: UUID4 = Field(foreign_key="room.id", index=True, ondelete="CASCADE")
    round_seq: int = Field(default=1, ge=1)
    kind: str = Field(index=True, description="'hit' | 'finish' | 'reward'")
    actor_id: str | None = Field(default=None, max_length=64)
    action: dict | None = Field(default=None, sa_column=sa.Column(JSONB, nullable=True))
    message: str = Field(max_length=200)
