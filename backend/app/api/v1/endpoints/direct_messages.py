"""Direct message endpoints (B1): sending, requests, threads, conversation list.

Thin routes: parse params → call the service → let ``DomainError`` map to HTTP.
Delivery over the Redis-backed WebSocket manager happens inside the service.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.db.session import get_async_session
from app.schemas.connection import ConnectionRead
from app.schemas.direct_message import DirectMessageRead, DirectMessageSend, DirectMessageSummary
from app.services.direct_message_service import direct_message_service

router = APIRouter(prefix="/messages", tags=["Direct Messages"])

DbSession = Annotated[AsyncSession, Depends(get_async_session)]


@router.post("/{user_id}", response_model=DirectMessageRead, status_code=201)
async def send_direct_message(
    user_id: UUID4,
    payload: DirectMessageSend,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> DirectMessageRead:
    """Send a direct message to a connection, or a request to a non-connection."""
    return await direct_message_service.send_message(db_session, sender=user, recipient_id=user_id, body=payload.body)


@router.post("/{user_id}/accept", response_model=ConnectionRead)
async def accept_message_request(
    user_id: UUID4,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> ConnectionRead:
    """Accept an open message request, promoting the sender to a connection."""
    return await direct_message_service.accept_request(db_session, user=user, requester_id=user_id)


@router.post("/{user_id}/decline", status_code=204)
async def decline_message_request(
    user_id: UUID4,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> Response:
    """Discard an open message request; safe to retry."""
    await direct_message_service.decline_request(db_session, user=user, requester_id=user_id)
    return Response(status_code=204)


@router.get("/{user_id}", response_model=list[DirectMessageRead])
async def get_direct_message_thread(
    user_id: UUID4,
    user: CurrentActiveUser,
    db_session: DbSession,
    limit: int = 50,
    offset: int = 0,
) -> list[DirectMessageRead]:
    """The chronological thread between the current user and another player."""
    return await direct_message_service.get_thread(db_session, user=user, other_id=user_id, limit=limit, offset=offset)


@router.get("", response_model=list[DirectMessageSummary])
async def list_direct_message_conversations(
    user: CurrentActiveUser,
    db_session: DbSession,
    limit: int = 50,
) -> list[DirectMessageSummary]:
    """Conversation list with last message, unread count, and pending-request flag."""
    return await direct_message_service.list_conversations(db_session, user=user, limit=limit)
