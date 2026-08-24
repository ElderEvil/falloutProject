"""Tests for AISettings CRUD (single-row get_single/upsert)."""

import pytest

from app.crud.ai_settings import ai_settings as ai_settings_crud

pytestmark = pytest.mark.asyncio


class TestAISettingsCRUD:
    async def test_get_single_returns_none_when_empty(self, async_session) -> None:
        assert await ai_settings_crud.get_single(async_session) is None

    async def test_upsert_creates_first_row(self, async_session) -> None:
        result = await ai_settings_crud.upsert(async_session, {"provider": "lmstudio", "model": "llama-3"})
        assert result.id is not None
        assert result.provider == "lmstudio"
        assert result.model == "llama-3"
        assert result.base_url is None
        assert result.gateway_route is None

    async def test_get_single_returns_row_after_upsert(self, async_session) -> None:
        await ai_settings_crud.upsert(async_session, {"provider": "ollama"})
        row = await ai_settings_crud.get_single(async_session)
        assert row is not None
        assert row.provider == "ollama"

    async def test_upsert_updates_existing_row(self, async_session) -> None:
        first = await ai_settings_crud.upsert(async_session, {"provider": "ollama", "model": "llama2"})
        updated = await ai_settings_crud.upsert(
            async_session, {"provider": "lmstudio", "model": "qwen", "base_url": "http://x:1234/v1"}
        )
        assert updated.id == first.id
        assert updated.provider == "lmstudio"
        assert updated.model == "qwen"
        assert updated.base_url == "http://x:1234/v1"

    async def test_upsert_partial_update(self, async_session) -> None:
        await ai_settings_crud.upsert(async_session, {"provider": "ollama", "model": "llama2"})
        updated = await ai_settings_crud.upsert(async_session, {"model": "mistral"})
        assert updated.provider == "ollama"
        assert updated.model == "mistral"

    async def test_upsert_empty_dict_keeps_existing(self, async_session) -> None:
        await ai_settings_crud.upsert(async_session, {"provider": "openai", "model": "gpt-4o"})
        updated = await ai_settings_crud.upsert(async_session, {})
        assert updated.provider == "openai"
        assert updated.model == "gpt-4o"

    async def test_single_row_enforced(self, async_session) -> None:
        await ai_settings_crud.upsert(async_session, {"provider": "ollama"})
        await ai_settings_crud.upsert(async_session, {"provider": "lmstudio"})
        from sqlmodel import select

        from app.models.ai_settings import AISettings

        result = await async_session.execute(select(AISettings))
        assert len(result.scalars().all()) == 1
