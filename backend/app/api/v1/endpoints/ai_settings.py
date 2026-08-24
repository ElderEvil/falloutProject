"""AI Settings admin endpoints (GET/PUT the DB-backed AI provider profile)."""

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentSuperuser
from app.db.session import get_async_session
from app.schemas.ai_settings import AISettingsRead, AISettingsUpdate
from app.services.ai_settings_service import ai_settings_service

router = APIRouter(prefix="/ai-settings", tags=["AI Settings"])


@router.get("/", response_model=AISettingsRead)
async def get_ai_settings(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    _: CurrentSuperuser,
) -> AISettingsRead:
    """Get the current AI settings profile and effective (resolved) values."""
    return await ai_settings_service.get_effective(db_session)


@router.put("/", response_model=AISettingsRead)
async def update_ai_settings(
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    update: AISettingsUpdate,
    _: CurrentSuperuser,
) -> AISettingsRead:
    """Update the AI settings profile and apply it (reconfigure AIService + reset ModelCache)."""
    result = await ai_settings_service.update_profile(db_session, update)
    await ai_settings_service.apply(db_session)
    return result
