from datetime import datetime
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.utils.types import UTCDateTime


class ConversationBase(SQLModel):
    vault_id: UUID = Field(foreign_key="vault.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    dweller_id: UUID = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")
    summary: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    summary_through_message_id: UUID | None = Field(default=None, foreign_key="chatmessage.id")


class Conversation(BaseUUIDModel, ConversationBase, TimeStampMixin, table=True):
    """The single continuous thread between one user and one dweller."""

    __tablename__ = "conversation"
    __table_args__ = (sa.UniqueConstraint("user_id", "dweller_id", name="uq_conversation_user_dweller"),)

    last_message_at: datetime | None = Field(default=None, sa_type=UTCDateTime, index=True)
    message_count: int = Field(default=0, ge=0)

    #: Serialised pydantic-ai ``Conversation`` (messages + usage + id): the model-facing thread.
    context: dict | None = Field(default=None, sa_column=sa.Column(JSONB))
