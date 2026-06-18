"""Shared generic response schemas for common API patterns."""

from pydantic import BaseModel


class MessageResponse(BaseModel):
    """Generic message response."""

    msg: str


class CountResponse(BaseModel):
    """Generic count response."""

    count: int


class MarkReadResponse(BaseModel):
    """Response for marking items as read."""

    marked_read: int


class AssignedResponse(BaseModel):
    """Response for assignment operations."""

    assigned: int
    message: str


class JunkListResponse(BaseModel):
    """Response containing a list of junk items."""

    junk: list


class RadioModeResponse(BaseModel):
    """Response for radio mode change."""

    message: str
    radio_mode: str


class RadioSpeedupResponse(BaseModel):
    """Response for radio speedup change."""

    message: str
    room_id: str
    speedup: float


class RelationshipActionResponse(BaseModel):
    """Response for relationship actions."""

    message: str


class BreedStatsResponse(BaseModel):
    """Response for breeding processing."""

    message: str
    stats: dict
