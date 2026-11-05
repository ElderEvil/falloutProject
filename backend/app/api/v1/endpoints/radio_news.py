"""Vault Radio Hour — broadcast news endpoints."""

import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentActiveUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.vault import Vault
from app.services.broadcast_service import get_or_create_daily, regenerate

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Vault Radio Hour"])


def _vault_stats_from_db(vault: Vault) -> dict:
    """Extract vault statistics for script rendering."""
    return {
        "number": vault.number,
        "bottle_caps": vault.bottle_caps,
        "happiness": vault.happiness,
        "power": vault.power,
        "power_max": vault.power_max,
        "food": vault.food,
        "food_max": vault.food_max,
        "water": vault.water,
        "water_max": vault.water_max,
        "population_max": vault.population_max,
    }


@router.get("/vaults/{vault_id}/radio-news", response_model=dict)
async def get_vault_radio_news(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Get today's broadcast for a vault, generating it on first call of the UTC day.

    Returns today's broadcast, generating it on first call.
    Response: {id, title, script, audio_url, trigger, created_at}
    If TTS is down: {id, title, script, audio_url: null, ...} with the script.

    Raises:
        HTTPException 403: If user doesn't have access to this vault.
    """
    vault = await get_user_vault_or_403(vault_id, user, db_session)
    vault_data = _vault_stats_from_db(vault)

    try:
        return await get_or_create_daily(db_session, vault_id, vault_data=vault_data)
    except Exception as e:
        # Never 500 the endpoint — fall back to script-only
        logger.warning("Broadcast generation failed: %s", e, exc_info=True)
        # Build a minimal script-only response
        title = "Vault Radio News — Daily Brief"
        script = (
            f"Today's broadcast from Vault {vault_data.get('number', '???')} is unavailable. Please try again later."
        )
        return {
            "id": None,
            "title": title,
            "script": script,
            "audio_url": None,
            "trigger": "daily",
            "created_at": None,
        }


@router.post("/vaults/{vault_id}/radio-news/regenerate", response_model=dict)
async def regenerate_vault_radio_news(
    vault_id: UUID4,
    user: CurrentActiveUser,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
) -> dict:
    """Manually re-render a broadcast, rate-limited to 3/UTC day/vault.

    Raises:
        HTTPException 403: If user doesn't have access.
        HTTPException 429: Rate limit exceeded.
    """
    vault = await get_user_vault_or_403(vault_id, user, db_session)
    vault_data = _vault_stats_from_db(vault)

    try:
        return await regenerate(db_session, vault_id, vault_data=vault_data)
    except Exception as e:
        logger.warning("Broadcast regeneration failed: %s", e, exc_info=True)
        if "limit reached" in str(e).lower():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=str(e),
            ) from e
        # Other failures: fallback to script-only
        title = "Vault Radio News — Daily Brief"
        script = (
            f"Today's broadcast from Vault {vault_data.get('number', '???')} is unavailable. Please try again later."
        )
        return {
            "id": None,
            "title": title,
            "script": script,
            "audio_url": None,
            "trigger": "manual",
            "created_at": None,
        }
