"""Player connections and blocking endpoints (A1 + A2 identity).

Thin routes: parse params → call the service → let ``DomainError`` map to HTTP.
Discovery is by exact username only; no listing or email is ever exposed here.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Response
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser
from app.db.session import get_async_session
from app.schemas.connection import ConnectionCreate, ConnectionRead
from app.schemas.user_block import UserBlockRead
from app.services.player_connection_service import player_connection_service

router = APIRouter(tags=["Player Connections"])

DbSession = Annotated[AsyncSession, Depends(get_async_session)]


@router.post("/connections", response_model=ConnectionRead, status_code=201)
async def invite_by_username(
    payload: ConnectionCreate,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> ConnectionRead:
    """Invite a player by their exact public username."""
    return await player_connection_service.invite(db_session, user=user, username=payload.username)


@router.post("/connections/{connection_id}/accept", response_model=ConnectionRead)
async def accept_connection(
    connection_id: UUID4,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> ConnectionRead:
    """Accept a pending invite (addressee only)."""
    return await player_connection_service.accept(db_session, user=user, connection_id=connection_id)


@router.post("/connections/{connection_id}/decline", status_code=204)
async def decline_connection(
    connection_id: UUID4,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> Response:
    """Decline a pending invite; safe to retry."""
    await player_connection_service.decline(db_session, user=user, connection_id=connection_id)
    return Response(status_code=204)


@router.delete("/connections/{connection_id}", status_code=204)
async def revoke_connection(
    connection_id: UUID4,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> Response:
    """Revoke a pending invite or sever an accepted connection."""
    await player_connection_service.revoke(db_session, user=user, connection_id=connection_id)
    return Response(status_code=204)


@router.get("/connections", response_model=list[ConnectionRead])
async def list_connections(
    user: CurrentActiveUser,
    db_session: DbSession,
) -> list[ConnectionRead]:
    """Accepted and pending connections, as requester and addressee."""
    return await player_connection_service.list_connections(db_session, user=user)


@router.post("/blocks/{user_id}", response_model=UserBlockRead, status_code=201)
async def block_user(
    user_id: UUID4,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> UserBlockRead:
    """Block a user; bilateral and immediate from the first message on."""
    return await player_connection_service.block(db_session, user=user, user_id=user_id)


@router.delete("/blocks/{user_id}", status_code=204)
async def unblock_user(
    user_id: UUID4,
    user: CurrentActiveUser,
    db_session: DbSession,
) -> Response:
    """Remove a block; safe to retry."""
    await player_connection_service.unblock(db_session, user=user, user_id=user_id)
    return Response(status_code=204)


@router.get("/blocks", response_model=list[UserBlockRead])
async def list_blocks(
    user: CurrentActiveUser,
    db_session: DbSession,
) -> list[UserBlockRead]:
    """The blocker's own block list."""
    return await player_connection_service.list_blocks(db_session, user=user)
