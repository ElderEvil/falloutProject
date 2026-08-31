"""Tests for AISettingsService — effective resolution, update_profile, apply, reconfigure."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import settings
from app.crud.ai_settings import ai_settings as ai_settings_crud
from app.models.ai_settings import AISettings
from app.services.ai_service import AIService
from app.services.ai_settings_service import ai_settings_service
from app.utils.exceptions import ValidationException

pytestmark = pytest.mark.asyncio


def _make_profile(
    provider: str | None = None,
    model: str | None = None,
    base_url: str | None = None,
    gateway_route: str | None = None,
) -> AISettings:
    return AISettings(
        provider=provider,
        model=model,
        base_url=base_url,
        gateway_route=gateway_route,
    )


class TestEffectiveResolution:
    async def test_empty_profile_falls_back_to_env(self) -> None:
        eff = ai_settings_service._resolve_effective(None)
        assert eff.provider == settings.AI_PROVIDER
        assert eff.model == settings.AI_MODEL

    async def test_profile_provider_overrides_env(self) -> None:
        profile = _make_profile(provider="lmstudio", model="local-model")
        eff = ai_settings_service._resolve_effective(profile)
        assert eff.provider == "lmstudio"
        assert eff.model == "local-model"

    async def test_profile_base_url_overrides_env(self) -> None:
        profile = _make_profile(provider="ollama", base_url="http://custom:11434/v1")
        eff = ai_settings_service._resolve_effective(profile)
        assert eff.base_url == "http://custom:11434/v1"

    async def test_profile_base_url_none_falls_back_to_env_for_provider(self) -> None:
        profile = _make_profile(provider="lmstudio")
        eff = ai_settings_service._resolve_effective(profile)
        assert eff.base_url == settings.LMSTUDIO_BASE_URL

    async def test_profile_gateway_route_overrides_env(self) -> None:
        profile = _make_profile(gateway_route="custom-route")
        eff = ai_settings_service._resolve_effective(profile)
        assert eff.gateway_route == "custom-route"

    async def test_profile_partial_override(self) -> None:
        profile = _make_profile(provider="anthropic")
        eff = ai_settings_service._resolve_effective(profile)
        assert eff.provider == "anthropic"
        assert eff.model == settings.AI_MODEL

    async def test_effective_mode_lmstudio(self) -> None:
        profile = _make_profile(provider="lmstudio")
        with (
            patch.object(settings, "PYDANTIC_AI_GATEWAY_API_KEY", None),
            patch.object(settings, "OPENAI_API_KEY", None),
            patch.object(settings, "ANTHROPIC_API_KEY", None),
            patch.object(settings, "AI_PROVIDER", "openai"),
        ):
            eff = ai_settings_service._resolve_effective(profile)
            assert eff.mode == "lmstudio"


class TestGetEffective:
    async def test_get_effective_no_profile(self, async_session) -> None:
        result = await ai_settings_service.get_effective(async_session)
        assert result.profile is None
        assert result.effective.provider == settings.AI_PROVIDER

    async def test_get_effective_with_profile(self, async_session) -> None:
        await ai_settings_crud.upsert(async_session, {"provider": "lmstudio", "model": "test-model"})
        result = await ai_settings_service.get_effective(async_session)
        assert result.profile is not None
        assert result.profile.provider == "lmstudio"
        assert result.effective.provider == "lmstudio"
        assert result.effective.model == "test-model"


class TestUpdateProfile:
    async def test_update_creates_profile(self, async_session) -> None:
        from app.schemas.ai_settings import AISettingsUpdate

        result = await ai_settings_service.update_profile(
            async_session,
            update=AISettingsUpdate(provider="ollama", model="llama2"),
        )
        assert result.profile is not None
        assert result.profile.provider == "ollama"

    async def test_update_rejects_invalid_provider(self, async_session) -> None:
        from app.schemas.ai_settings import AISettingsUpdate

        with pytest.raises(ValidationException, match="Invalid provider"):
            await ai_settings_service.update_profile(
                async_session,
                update=AISettingsUpdate(provider="invalid_provider"),
            )

    async def test_update_accepts_lmstudio(self, async_session) -> None:
        from app.schemas.ai_settings import AISettingsUpdate

        result = await ai_settings_service.update_profile(
            async_session,
            update=AISettingsUpdate(provider="lmstudio", model="qwen", base_url="http://localhost:1234/v1"),
        )
        assert result.profile.provider == "lmstudio"
        assert result.effective.provider == "lmstudio"


class TestApply:
    async def test_apply_calls_reconfigure_and_model_cache_reset(self, async_session) -> None:
        await ai_settings_crud.upsert(async_session, {"provider": "lmstudio", "model": "test"})
        with (
            patch.object(AIService, "reconfigure", return_value=True) as mock_reconfig,
            patch("app.agents.dweller_chat_agent.ModelCache.reset") as mock_cache_reset,
            patch("app.agents.dweller_chat_agent.ModelCache.get_model", return_value=MagicMock()),
        ):
            result = await ai_settings_service.apply(async_session)
            assert result is True
            mock_reconfig.assert_called_once()
            mock_cache_reset.assert_called_once()

    async def test_apply_rebinds_all_agent_models(self, async_session) -> None:
        from app.agents import dweller_agents
        from app.agents.dweller_chat_agent import dweller_chat_agent

        await ai_settings_crud.upsert(async_session, {"provider": "lmstudio", "model": "test"})
        fresh_model = MagicMock()
        with (
            patch.object(AIService, "reconfigure", return_value=True),
            patch("app.agents.dweller_chat_agent.ModelCache.reset"),
            patch("app.agents.dweller_chat_agent.ModelCache.get_model", return_value=fresh_model),
        ):
            await ai_settings_service.apply(async_session)

        assert dweller_chat_agent.model is fresh_model
        for content_agent in (
            dweller_agents.backstory_agent,
            dweller_agents.bio_extension_agent,
            dweller_agents.visual_attributes_agent,
        ):
            assert content_agent.model is fresh_model, f"{content_agent!r} was not rebound"


class TestAIServiceReconfigure:
    def _make_fresh_service(self) -> AIService:
        AIService._instance = None
        with patch.object(AIService, "_initialize_provider", return_value=None):
            return AIService()

    def test_reconfigure_to_lmstudio_sets_model(self) -> None:
        svc = self._make_fresh_service()
        with (
            patch.object(settings, "PYDANTIC_AI_GATEWAY_API_KEY", None),
            patch.object(settings, "OPENAI_API_KEY", None),
            patch.object(settings, "ANTHROPIC_API_KEY", None),
        ):
            mock_model = MagicMock()
            with (
                patch("pydantic_ai.providers.openai.OpenAIProvider", return_value=MagicMock()),
                patch("app.services.ai_service.OpenAIChatModel", return_value=mock_model),
            ):
                result = svc.reconfigure(provider="lmstudio", model="local-model", base_url="http://localhost:1234/v1")
                assert result is True
                assert svc._model is mock_model
                assert svc.is_available() is True

    def test_reconfigure_to_ollama_sets_model(self) -> None:
        svc = self._make_fresh_service()
        with (
            patch.object(settings, "PYDANTIC_AI_GATEWAY_API_KEY", None),
            patch.object(settings, "OPENAI_API_KEY", None),
            patch.object(settings, "ANTHROPIC_API_KEY", None),
        ):
            mock_model = MagicMock()
            with (
                patch("pydantic_ai.providers.ollama.OllamaProvider", return_value=MagicMock()),
                patch("app.services.ai_service.OpenAIChatModel", return_value=mock_model),
            ):
                result = svc.reconfigure(provider="ollama", model="llama2", base_url="http://localhost:11434/v1")
                assert result is True
                assert svc._model is mock_model

    def test_reconfigure_uses_an_isolated_settings_copy(self) -> None:
        svc = self._make_fresh_service()
        original_provider = settings.AI_PROVIDER
        original_model = settings.AI_MODEL
        observed: dict[str, str] = {}

        def initialize(*, config, **_kwargs) -> None:
            observed["global_provider"] = settings.AI_PROVIDER
            observed["profile_provider"] = config.AI_PROVIDER

        with patch.object(svc, "_initialize_provider", side_effect=initialize):
            svc.reconfigure(provider="lmstudio", model="test", base_url="http://x:1234/v1")

        assert observed == {"global_provider": original_provider, "profile_provider": "lmstudio"}
        assert original_provider == settings.AI_PROVIDER
        assert original_model == settings.AI_MODEL

    def test_reconfigure_returns_false_on_exception(self) -> None:
        svc = self._make_fresh_service()
        with (
            patch.object(settings, "PYDANTIC_AI_GATEWAY_API_KEY", None),
            patch.object(settings, "OPENAI_API_KEY", None),
            patch.object(settings, "ANTHROPIC_API_KEY", None),
            patch("app.services.ai_service.OpenAIChatModel", side_effect=Exception("init failed")),
        ):
            result = svc.reconfigure(provider="lmstudio", model="test", base_url="http://x:1234/v1")
            assert result is False
            assert svc._model is None

    def test_reconfigure_no_args_uses_env_defaults(self) -> None:
        svc = self._make_fresh_service()
        with patch.object(AIService, "_initialize_provider") as mock_init:
            svc.reconfigure()
            mock_init.assert_called_once()
