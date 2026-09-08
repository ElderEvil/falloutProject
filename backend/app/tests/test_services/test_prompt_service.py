"""Tests for resilient prompt and provider provenance lookups."""

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


async def test_prompt_registry_supports_raw_sessions_and_failed_lookup(db_connection, async_session):
    from unittest.mock import patch

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import AsyncSession

    async with AsyncSession(bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint") as db:
        db.add(Prompt(prompt_name="chat", description="original", prompt_template="original"))
        await db.commit()
        invalidate("chat")
        created = await create_prompt_version(db, "chat", "replacement")
        assert (await get_instructions(db, "chat"))[:2] == ("replacement", created.id)
        invalidate("chat")

        async def broken_lookup(*args):
            await db.execute(text("SELECT * FROM missing_prompt_table"))

        with patch("app.services.prompt_service.prompt_crud.get_active", new=broken_lookup):
            assert (await get_instructions(db, "chat"))[:2] == (DEFAULT_PROMPTS["chat"], None)
        assert (await get_instructions(db, "chat"))[:2] == ("replacement", created.id)

        from app.crud.prompt import prompt as prompt_crud

        replace_active = prompt_crud.replace_active

        async def fail_after_activation(*args):
            await replace_active(*args)
            raise RuntimeError("write failed")

        with (
            patch.object(prompt_crud, "replace_active", new=fail_after_activation),
            pytest.raises(RuntimeError, match="write failed"),
        ):
            await create_prompt_version(db, "chat", "not saved")
        active = await prompt_crud.get_active(db, "chat")
        assert active is not None
        assert active.prompt_template == "replacement"
        invalidate("chat")
