"""Tests for resilient prompt and provider provenance lookups."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.prompt import Prompt
from app.services.prompt_service import (
    DEFAULT_PROMPTS,
    compute_instructions_hash,
    create_prompt_version,
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
    session.exec = AsyncMock(side_effect=RuntimeError("database unavailable"))
    return session


@pytest.mark.asyncio
async def test_creating_a_prompt_version_replaces_the_active_row_and_invalidates_cache(async_session) -> None:
    """Prompt changes are append-only and immediately visible to new agent calls."""
    original = Prompt(prompt_name="chat", description="v1", prompt_template="original")
    async_session.add(original)
    await async_session.commit()
    invalidate("chat")
    await get_instructions(async_session, "chat")

    created = await create_prompt_version(async_session, "chat", "replacement", description="v2")

    assert created.version == 2
    assert created.is_active is True
    assert original.is_active is False
    instructions, prompt_id, _ = await get_instructions(async_session, "chat")
    assert instructions == "replacement"
    assert prompt_id == created.id


@pytest.mark.asyncio
async def test_creating_a_prompt_version_rejects_format_fields(async_session) -> None:
    """Runtime instructions do not interpolate user-provided template fields."""
    async_session.add(Prompt(prompt_name="chat", description="v1", prompt_template="original"))
    await async_session.commit()

    with pytest.raises(ValueError, match="placeholders"):
        await create_prompt_version(async_session, "chat", "Hello {name}")
