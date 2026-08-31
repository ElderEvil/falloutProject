"""Tests for Prompt registry versioning: (name, version) uniqueness and single active row."""

import pytest
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.prompt import Prompt


async def _add_prompt(session: AsyncSession, **overrides) -> Prompt:
    prompt = Prompt(
        prompt_name=overrides.get("prompt_name", "backstory"),
        description=overrides.get("description", "test prompt"),
        prompt_template=overrides.get("prompt_template", "template {name}"),
        version=overrides.get("version", 1),
        is_active=overrides.get("is_active", True),
    )
    session.add(prompt)
    await session.commit()
    return prompt


@pytest.mark.asyncio
async def test_defaults_are_version_one_and_active(async_session: AsyncSession) -> None:
    prompt = await _add_prompt(async_session)

    assert prompt.version == 1
    assert prompt.is_active is True


@pytest.mark.asyncio
async def test_duplicate_name_and_version_rejected(async_session: AsyncSession) -> None:
    await _add_prompt(async_session, prompt_name="backstory", version=1)

    with pytest.raises(IntegrityError):
        await _add_prompt(async_session, prompt_name="backstory", version=1)


@pytest.mark.asyncio
async def test_same_name_new_version_allowed_after_deactivation(async_session: AsyncSession) -> None:
    v1 = await _add_prompt(async_session, prompt_name="backstory", version=1)
    v1.is_active = False
    await async_session.commit()

    v2 = await _add_prompt(async_session, prompt_name="backstory", version=2)

    assert v2.is_active is True


@pytest.mark.asyncio
async def test_second_active_row_same_name_rejected(async_session: AsyncSession) -> None:
    await _add_prompt(async_session, prompt_name="backstory", version=1, is_active=True)

    with pytest.raises(IntegrityError):
        await _add_prompt(async_session, prompt_name="backstory", version=2, is_active=True)


@pytest.mark.asyncio
async def test_inactive_row_same_name_allowed(async_session: AsyncSession) -> None:
    await _add_prompt(async_session, prompt_name="backstory", version=1, is_active=True)

    inactive = await _add_prompt(async_session, prompt_name="backstory", version=2, is_active=False)

    assert inactive.is_active is False


@pytest.mark.asyncio
async def test_activation_swap_keeps_single_active_row(async_session: AsyncSession) -> None:
    v1 = await _add_prompt(async_session, prompt_name="backstory", version=1, is_active=True)
    v2 = await _add_prompt(async_session, prompt_name="backstory", version=2, is_active=False)

    v1.is_active = False
    await async_session.commit()
    v2.is_active = True
    await async_session.commit()

    assert v2.is_active is True
