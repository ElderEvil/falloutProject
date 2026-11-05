"""Vault Radio Hour — broadcast news endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.services.broadcast_service import get_or_create_daily, regenerate, vault_stats_from_db
from app.utils.exceptions import BroadcastRateLimitException

router = APIRouter(tags=["Vault Radio Hour"])


@router.get("/vaults/{vault_id}/radio-news", response_model=dict)
async def get_vault_radio_news(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Return today's broadcast, generating it once if none exists for the UTC day."""
    vault = await get_user_vault_or_403(vault_id, user, db_session)
    return await get_or_create_daily(db_session, vault_id, vault_data=vault_stats_from_db(vault))


@router.post("/vaults/{vault_id}/radio-news/regenerate", response_model=dict)
async def regenerate_vault_radio_news(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Render a new manual broadcast, rate-limited to three per UTC day."""
    vault = await get_user_vault_or_403(vault_id, user, db_session)
    try:
        return await regenerate(db_session, vault_id, vault_data=vault_stats_from_db(vault))
    except BroadcastRateLimitException as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=exc.detail,
        ) from exc
