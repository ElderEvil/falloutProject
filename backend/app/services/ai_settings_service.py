import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import settings
from app.crud.ai_settings import ai_settings as ai_settings_crud
from app.models.ai_settings import AISettings
from app.schemas.ai_settings import (
    AISettingsEffective,
    AISettingsProfile,
    AISettingsRead,
    AISettingsUpdate,
)
from app.services.ai_service import AIService
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)


class AISettingsService:
    """Service for AI provider profile management (DB-backed overrides of .env)."""

    async def get_effective(self, db_session: AsyncSession) -> AISettingsRead:
        profile = await ai_settings_crud.get_single(db_session)
        return AISettingsRead(
            profile=self._to_profile(profile) if profile else None,
            effective=self._resolve_effective(profile),
        )

    async def update_profile(self, db_session: AsyncSession, update: AISettingsUpdate) -> AISettingsRead:
        data = update.model_dump(exclude_unset=True)
        if "provider" in data and data["provider"] is not None:
            from app.schemas.ai_settings import ALLOWED_AI_PROVIDERS

            if data["provider"] not in ALLOWED_AI_PROVIDERS:
                raise ValidationException(
                    detail=f"Invalid provider '{data['provider']}'. Allowed: {', '.join(sorted(ALLOWED_AI_PROVIDERS))}"
                )
        profile = await ai_settings_crud.upsert(db_session, data)
        return AISettingsRead(
            profile=self._to_profile(profile),
            effective=self._resolve_effective(profile),
        )

    async def apply(self, db_session: AsyncSession) -> bool:
        from app.agents.dweller_chat_agent import ModelCache, dweller_chat_agent

        profile = await ai_settings_crud.get_single(db_session)
        eff_provider = settings.effective_ai_provider(profile)
        eff_model = settings.effective_ai_model(profile)
        eff_base_url = settings.effective_ai_base_url(profile)
        eff_route = settings.effective_ai_gateway_route(profile)

        service = AIService()
        result = service.reconfigure(
            provider=eff_provider,
            model=eff_model,
            base_url=eff_base_url,
            gateway_route=eff_route,
        )
        ModelCache.reset()
        dweller_chat_agent.model = ModelCache.get_model()
        return result

    @staticmethod
    def _to_profile(profile: AISettings) -> AISettingsProfile:
        return AISettingsProfile(
            id=profile.id,
            provider=profile.provider,
            model=profile.model,
            base_url=profile.base_url,
            gateway_route=profile.gateway_route,
            updated_at=profile.updated_at,
        )

    @staticmethod
    def _resolve_effective(profile: AISettings | None) -> AISettingsEffective:
        return AISettingsEffective(
            provider=settings.effective_ai_provider(profile),
            model=settings.effective_ai_model(profile),
            base_url=settings.effective_ai_base_url(profile),
            gateway_route=settings.effective_ai_gateway_route(profile),
            mode=settings.effective_ai_mode(profile),
        )


ai_settings_service = AISettingsService()
