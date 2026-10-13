"""Schemas for account-owned direct messages (B1)."""

from datetime import datetime

from pydantic import UUID4, BaseModel, Field, field_validator


class DirectMessageSend(BaseModel):
    """Body of a direct message; the first message to a non-connection is a request."""

    body: str = Field(min_length=1, max_length=2000)

    @field_validator("body")
    @classmethod
    def body_not_blank(cls, value: str) -> str:
        body = value.strip()
        if not body:
            raise ValueError("Message body must not be blank.")
        return body


class DirectMessageRead(BaseModel):
    """Wire shape of a stored message. ``read_at`` is intentionally NOT exposed."""

    id: UUID4
    sender_user_id: UUID4
    recipient_user_id: UUID4
    body: str
    is_request: bool
    created_at: datetime | None


class DirectMessageSummary(BaseModel):
    """One conversation in the list: counterpart + last message + unread count."""

    counterpart_user_id: UUID4
    counterpart_username: str
    last_message: DirectMessageRead
    unread_count: int
    has_pending_request: bool
