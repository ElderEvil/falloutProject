"""Account-owned direct messages between players (B1 of the multiplayer slice)."""

from datetime import datetime

from pydantic import UUID4
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin


class DirectMessageBase(SQLModel):
    sender_user_id: UUID4 = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    recipient_user_id: UUID4 = Field(foreign_key="user.id", ondelete="CASCADE", index=True)
    body: str = Field(max_length=2000)
    is_request: bool = Field(default=False, index=True)


class DirectMessage(BaseUUIDModel, DirectMessageBase, TimeStampMixin, table=True):
    """One direct message, stored against the account pair (no vault_id).

    ``is_request`` marks an unanswered consent gate: the first message to a
    non-connection is a request, and further flow only unlocks after the
    recipient accepts (creating an ACCEPTED connection).
    """

    __tablename__ = "directmessage"

    read_at: datetime | None = Field(default=None)

    def __str__(self):
        return f"DirectMessage {self.sender_user_id} -> {self.recipient_user_id}"
