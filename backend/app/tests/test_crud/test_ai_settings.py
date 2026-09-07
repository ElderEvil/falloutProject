"""Tests for AISettings CRUD (single-row get_single/upsert)."""

import pytest

from app.crud.ai_settings import ai_settings as ai_settings_crud

pytestmark = pytest.mark.asyncio


class TestAISettingsCRUD:
    async def test_upsert_adopts_existing_row_on_pk_collision(self, async_session) -> None:
        from sqlmodel import select

        from app.crud.ai_settings import SINGLETON_ROW_ID
        from app.models.ai_settings import AISettings

        seeded = AISettings(id=SINGLETON_ROW_ID, provider="ollama", model="llama2")
        async_session.add(seeded)
        await async_session.commit()
        async_session.expunge(seeded)

        original = ai_settings_crud.get_single
        calls = {"n": 0}

        async def _miss(db_session):
            calls["n"] += 1
            if calls["n"] == 1:
                return None
            return await original(db_session)

        ai_settings_crud.get_single = _miss
        try:
            result = await ai_settings_crud.upsert(async_session, {"provider": "lmstudio", "model": "qwen"})
        finally:
            ai_settings_crud.get_single = original

        rows = (await async_session.execute(select(AISettings))).scalars().all()
        assert len(rows) == 1
        assert rows[0].id == SINGLETON_ROW_ID
        assert result.provider == "lmstudio"
        assert result.model == "qwen"
