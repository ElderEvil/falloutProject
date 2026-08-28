import logging
import time
from dataclasses import dataclass

from pydantic_ai import Agent
from pydantic_ai.exceptions import ModelHTTPError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.config import AIProfileProtocol, settings
from app.crud.ai_settings import ai_settings as ai_settings_crud
from app.models.ai_settings import AISettings
from app.schemas.ai_settings import (
    AISettingsEffective,
    AISettingsProfile,
    AISettingsRead,
    AISettingsTestInput,
    AISettingsTestResult,
    AISettingsUpdate,
)
from app.services.ai_service import AIService, build_test_model
from app.services.chat_service import ChatService
from app.utils.exceptions import ValidationException

logger = logging.getLogger(__name__)


@dataclass
class _EffectiveProfile:
    provider: str | None
    model: str | None
    base_url: str | None
    gateway_route: str | None


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

    async def test_connection(self, db_session: AsyncSession, overrides: AISettingsTestInput) -> AISettingsTestResult:
        data = overrides.model_dump(exclude_unset=True)
        if "provider" in data and data["provider"] is not None:
            from app.schemas.ai_settings import ALLOWED_AI_PROVIDERS

            if data["provider"] not in ALLOWED_AI_PROVIDERS:
                raise ValidationException(
                    detail=f"Invalid provider '{data['provider']}'. Allowed: {', '.join(sorted(ALLOWED_AI_PROVIDERS))}"
                )

        profile = await ai_settings_crud.get_single(db_session)
        effective_profile = self._merge_overrides(profile, overrides)
        effective = self._resolve_effective(effective_profile)

        if effective.mode == "disabled":
            return AISettingsTestResult(
                status="error",
                message="AI provider is disabled. Configure an API key or provider in environment variables.",
            )

        model = build_test_model(
            provider=effective.provider,
            model=effective.model,
            base_url=effective.base_url,
            gateway_route=effective.gateway_route,
            mode=effective.mode,
        )
        if model is None:
            return AISettingsTestResult(
                status="error",
                model=effective.model,
                message=f"Could not initialize {effective.provider} model {effective.model}. Check API keys and base URL.",
            )

        start = time.perf_counter()
        try:
            agent = Agent(model=model)
            await agent.run("Reply with OK")
        except ModelHTTPError as error:
            return AISettingsTestResult(
                status="error",
                latency_ms=int((time.perf_counter() - start) * 1000),
                model=effective.model,
                message=ChatService._extract_provider_reason(error),
            )
        except Exception as error:
            logger.exception("AI connection test failed")
            return AISettingsTestResult(
                status="error",
                latency_ms=int((time.perf_counter() - start) * 1000),
                model=effective.model,
                message=f"AI provider request failed: {error}",
            )

        return AISettingsTestResult(
            status="ok",
            latency_ms=int((time.perf_counter() - start) * 1000),
            model=effective.model,
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
        fresh_model = ModelCache.get_model()
        dweller_chat_agent.model = fresh_model

        from app.agents import dweller_agents

        for content_agent in (
            dweller_agents.backstory_agent,
            dweller_agents.bio_extension_agent,
            dweller_agents.visual_attributes_agent,
        ):
            content_agent.model = fresh_model
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
    def _resolve_effective(profile: AIProfileProtocol | None) -> AISettingsEffective:
        return AISettingsEffective(
            provider=settings.effective_ai_provider(profile),
            model=settings.effective_ai_model(profile),
            base_url=settings.effective_ai_base_url(profile),
            gateway_route=settings.effective_ai_gateway_route(profile),
            mode=settings.effective_ai_mode(profile),
        )

    @staticmethod
    def _merge_overrides(profile: AISettings | None, overrides: AISettingsTestInput) -> AIProfileProtocol | None:
        override_data = overrides.model_dump(exclude_unset=True)
        if profile is None and not override_data:
            return None
        return _EffectiveProfile(
            provider=override_data.get("provider", profile.provider if profile else None),
            model=override_data.get("model", profile.model if profile else None),
            base_url=override_data.get("base_url", profile.base_url if profile else None),
            gateway_route=override_data.get("gateway_route", profile.gateway_route if profile else None),
        )


ai_settings_service = AISettingsService()
