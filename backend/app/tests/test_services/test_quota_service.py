"""Tests for QuotaService."""

import pytest
from sqlmodel.ext.asyncio.session import AsyncSession

from app import crud
from app.models.llm_interaction import LLMInteraction
from app.schemas.user import UserCreate
from app.services.quota_service import quota_service


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
        parameters=None,
        response=None,
        usage="test",
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


@pytest.mark.parametrize(("allowed", "warning"), [(True, False), (True, True), (False, False), (False, True)])
def test_quota_enforcement_keeps_http_headers_at_api_boundary(allowed: bool, warning: bool) -> None:
    from starlette.requests import Request

    from app.services.quota_service import QuotaCheckResult
    from app.utils.exceptions import QuotaExceededException
    from main import domain_exception_handler

    result = QuotaCheckResult(allowed=allowed, remaining=0, limit=100, percentage=100, warning=warning, used=100)
    if allowed:
        assert result.ensure_allowed() is None
        return
    with pytest.raises(QuotaExceededException) as caught:
        result.ensure_allowed()
    assert caught.value.headers is None
    assert str(caught.value) == "Monthly token quota exceeded. You have used 100 of 100 tokens."
    response = domain_exception_handler(Request({"type": "http"}), caught.value)
    assert response.status_code == 429
    assert response.headers["X-Quota-Remaining"] == "0"
    assert response.headers.get("X-Quota-Warning") == ("true" if warning else None)


async def test_quota_raw_session_owns_usage_transaction(db_connection, async_session):
    from datetime import datetime
    from unittest.mock import AsyncMock

    from sqlalchemy import event
    from sqlalchemy.dialects import postgresql
    from sqlalchemy.ext.asyncio import AsyncSession as RawAsyncSession

    from app.models.user import User

    statements = []
    async with RawAsyncSession(
        bind=db_connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
    ) as db:
        user = User(
            username="quota-raw", email="quota-raw@example.com", hashed_password="unused", monthly_token_limit=100
        )
        db.add(user)
        await db.commit()
        user_id = user.id
        db.add(
            LLMInteraction(
                parameters=None,
                response=None,
                usage="test",
                user_id=user_id,
                total_tokens=99,
                created_at=datetime(2000, 1, 1),
            )
        )
        await db.commit()
        event.listen(
            db.sync_session,
            "do_orm_execute",
            lambda state: statements.append(str(state.statement.compile(dialect=postgresql.dialect()))),
        )
        await quota_service.record_usage(user_id, 80, db, AsyncMock())
        quota = await quota_service.check_quota(user_id, db)
        assert (quota.used, quota.remaining, quota.warning) == (80, 20, True)
        assert any("FOR UPDATE" in statement for statement in statements)
        await db.rollback()
        assert (await quota_service.check_quota(user_id, db)).used == 0
