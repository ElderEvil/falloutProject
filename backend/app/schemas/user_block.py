"""Schemas for user blocking (A2 identity)."""

from datetime import datetime

from pydantic import UUID4, BaseModel


class UserBlockRead(BaseModel):
    """Wire shape for a block row plus the blocked user's public handle."""

    id: UUID4
    blocked_id: UUID4
    blocked_username: str
    created_at: datetime | None
