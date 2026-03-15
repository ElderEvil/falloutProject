"""Tests for QuotaService."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app import crud
from app.models.llm_interaction import LLMInteraction
from app.schemas.user import UserCreate
from app.services.quota_service import quota_service


@pytest.mark.asyncio
async def test_check_quota_admin_bypass_allowed(async_session: AsyncSession) -> None:
    """Test that admin users (is_superuser=True) bypass quota checks."""
    # Create admin user
    user_in = UserCreate(
        username="admin_user",
        email="admin@example.com",
        password="adminpass123",
        is_superuser=True,
    )
    user = await crud.user.create(async_session, obj_in=user_in)

    # Create high token usage for admin (exceeds normal quota)
    interaction = LLMInteraction(
        user_id=user.id,
        total_tokens=1000000,  # 1M tokens - way over normal quota
        prompt_tokens=500000,
        completion_tokens=500000,
    )
    async_session.add(interaction)
    await async_session.commit()

    # Check quota - admin should be allowed
    result = await quota_service.check_quota(user.id, async_session)

    assert result.allowed is True
    assert result.remaining == 500000  # DEFAULT_QUOTA_LIMIT
    assert result.limit == 500000  # DEFAULT_QUOTA_LIMIT
    assert result.percentage == 0.0
    assert result.warning is False
    assert result.used == 0  # Admin returns 0 for used


@pytest.mark.asyncio
async def test_check_quota_normal_user_allowed(async_session: AsyncSession) -> None:
    """Test that normal users are allowed when under quota."""
    # Create normal user with default quota (500000)
    user_in = UserCreate(
        username="normal_user",
        email="normal@example.com",
        password="normalpass123",
        is_superuser=False,
    )
    user = await crud.user.create(async_session, obj_in=user_in)

    # Create moderate token usage (under 500K default quota)
    interaction = LLMInteraction(
        user_id=user.id,
        total_tokens=100000,  # 100K tokens - under 500K default limit
        prompt_tokens=50000,
        completion_tokens=50000,
    )
    async_session.add(interaction)
    await async_session.commit()

    # Check quota - normal user should be allowed
    result = await quota_service.check_quota(user.id, async_session)

    assert result.allowed is True
    assert result.remaining == 400000  # 500K limit - 100K used
    assert result.limit == 500000
    assert result.percentage == 20.0
    assert result.warning is False  # 20% < 80% threshold
    assert result.used == 100000


@pytest.mark.asyncio
async def test_check_quota_normal_user_exceeded(async_session: AsyncSession) -> None:
    """Test that normal users are blocked when quota exceeded."""
    # Create normal user with default quota (500000)
    user_in = UserCreate(
        username="limited_user",
        email="limited@example.com",
        password="limitedpass123",
        is_superuser=False,
    )
    user = await crud.user.create(async_session, obj_in=user_in)

    # Create high token usage (exceeds 500K default quota)
    interaction = LLMInteraction(
        user_id=user.id,
        total_tokens=600000,  # 600K tokens - over 500K limit
        prompt_tokens=300000,
        completion_tokens=300000,
    )
    async_session.add(interaction)
    await async_session.commit()

    # Check quota - normal user should be blocked
    result = await quota_service.check_quota(user.id, async_session)

    assert result.allowed is False
    assert result.remaining == 0
    assert result.limit == 500000
    assert result.percentage == 120.0
    assert result.warning is True  # Over 80% threshold
    assert result.used == 600000


@pytest.mark.asyncio
async def test_check_quota_admin_with_no_usage(async_session: AsyncSession) -> None:
    """Test admin user with no token usage."""
    # Create admin user
    user_in = UserCreate(
        username="admin_no_usage",
        email="admin_nousage@example.com",
        password="adminpass123",
        is_superuser=True,
    )
    user = await crud.user.create(async_session, obj_in=user_in)

    # Check quota - admin should be allowed with default values
    result = await quota_service.check_quota(user.id, async_session)

    assert result.allowed is True
    assert result.remaining == 500000
    assert result.limit == 500000
    assert result.percentage == 0.0
    assert result.warning is False
    assert result.used == 0


@pytest.mark.asyncio
async def test_check_quota_normal_user_warning_threshold(async_session: AsyncSession) -> None:
    """Test that normal users get warning when near quota threshold (80%)."""
    # Create normal user with default quota (500000)
    user_in = UserCreate(
        username="warning_user",
        email="warning@example.com",
        password="warningpass123",
        is_superuser=False,
    )
    user = await crud.user.create(async_session, obj_in=user_in)

    # Create usage at exactly 80% threshold (400K of 500K)
    interaction = LLMInteraction(
        user_id=user.id,
        total_tokens=400000,  # 80% of 500K
        prompt_tokens=200000,
        completion_tokens=200000,
    )
    async_session.add(interaction)
    await async_session.commit()

    # Check quota - should have warning=True
    result = await quota_service.check_quota(user.id, async_session)

    assert result.allowed is True  # Still under limit
    assert result.warning is True  # At 80% threshold
    assert result.percentage == 80.0
    assert result.remaining == 100000
    assert result.used == 400000
