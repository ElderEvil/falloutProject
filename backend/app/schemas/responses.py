"""Shared generic response schemas for common API patterns."""

from typing import Any

from pydantic import BaseModel

#: OpenAPI response declaration for an operation whose wire body is always JSON
#: ``null`` -- a 200 action acknowledgement with no payload. Clients already
#: receive ``null``; this states that contract instead of leaving the response
#: schema empty. Not a Pydantic model because nothing can serialize a top-level
#: ``null`` through ``response_model`` without changing the body.
NULL_BODY_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {"content": {"application/json": {"schema": {"anyOf": [{"type": "null"}]}}}}
}


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


class RelationshipActionResponse(BaseModel):
    """Response for relationship actions."""

    message: str


class BreedStatsResponse(BaseModel):
    """Response for breeding processing."""

    message: str
    stats: dict
