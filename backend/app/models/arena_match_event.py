"""Arena match event model - battle journal entries for arena fights."""

from pydantic import UUID4
from sqlmodel import Field

from app.models.base import BaseUUIDModel, TimeStampMixin


class ArenaMatchEvent(BaseUUIDModel, TimeStampMixin, table=True):
    """One line in the arena battle journal."""

    __tablename__ = "arena_match_event"

    room_id: UUID4 = Field(foreign_key="room.id", index=True, ondelete="CASCADE")
    round_seq: int = Field(default=1, ge=1)
    kind: str = Field(index=True, description="'hit' | 'finish' | 'reward'")
    message: str = Field(max_length=200)
