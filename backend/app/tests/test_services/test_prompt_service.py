"""Tests for resilient prompt and provider provenance lookups."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.prompt_service import (
    DEFAULT_PROMPTS,
    compute_instructions_hash,
    get_instructions,
    get_provider_model_snapshot,
    invalidate,
)


def _failing_session() -> MagicMock:
    session = MagicMock()
    savepoint = MagicMock()
    savepoint.__aenter__ = AsyncMock(return_value=savepoint)
    savepoint.__aexit__ = AsyncMock(return_value=False)
    session.begin_nested.return_value = savepoint
    session.execute = AsyncMock(side_effect=RuntimeError("database unavailable"))
    return session


@pytest.mark.asyncio
async def test_prompt_lookup_fallback_is_scoped_to_a_savepoint() -> None:
    """A failed prompt lookup must not prevent later work in the request transaction."""
    invalidate("chat")
    session = _failing_session()

    instructions, prompt_id, instructions_hash = await get_instructions(session, "chat")

    assert instructions == DEFAULT_PROMPTS["chat"]
    assert prompt_id is None
    assert instructions_hash == compute_instructions_hash(DEFAULT_PROMPTS["chat"])
    session.begin_nested.assert_called_once_with()
    session.exec = AsyncMock()
    await session.exec(MagicMock())
    session.exec.assert_awaited_once()


@pytest.mark.asyncio
async def test_provider_snapshot_fallback_is_scoped_to_a_savepoint() -> None:
    """A failed profile lookup must preserve the outer transaction for persistence."""
    session = _failing_session()

    provider, model = await get_provider_model_snapshot(session)

    assert isinstance(provider, str)
    assert isinstance(model, str)
    session.begin_nested.assert_called_once_with()
    session.exec = AsyncMock()
    await session.exec(MagicMock())
    session.exec.assert_awaited_once()
