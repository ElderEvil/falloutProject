"""Schemas for player connections (A1)."""

from datetime import datetime

from pydantic import UUID4, BaseModel, Field

from app.core.enums import ConnectionStatus


class ConnectionCreate(BaseModel):
    """Invite payload: the exact public `username` of the addressee."""

    username: str = Field(min_length=3, max_length=32)


class ConnectionRead(BaseModel):
    """Wire shape for a connection row plus the counterpart's public handle."""

    id: UUID4
    requester_id: UUID4
    addressee_id: UUID4
    status: ConnectionStatus
    counterpart_username: str
    created_at: datetime | None
    responded_at: datetime | None
