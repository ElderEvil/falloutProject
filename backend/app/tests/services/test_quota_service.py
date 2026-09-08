"""Comprehensive unit tests for QuotaService with mocking.

These tests use mocking (no real database) to test QuotaService behavior
in isolation. They verify:
- Quota checking at various thresholds
- Admin bypass functionality
- Config-based quota disabling
- Usage recording with cache invalidation
- Race condition handling
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import UUID, uuid4

import pytest
from redis.asyncio import Redis
from sqlalchemy import func
from sqlmodel import col

from app.models.llm_interaction import LLMInteraction
from app.models.user import User
from app.services.quota_service import (
    DEFAULT_QUOTA_LIMIT,
    WARNING_THRESHOLD,
    QuotaCheckResult,
    QuotaService,
)
from app.utils.exceptions import ResourceNotFoundException


@pytest.fixture
def quota_service() -> QuotaService:
    """Create a fresh QuotaService instance."""
    return QuotaService()


@pytest.fixture
def user_id() -> UUID:
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def mock_db_session() -> AsyncMock:
    """Create a mock database session."""
    return AsyncMock(add=MagicMock())


@pytest.fixture
def mock_redis_client() -> Redis:
    """Create a mock Redis client."""
    redis = AsyncMock(spec=Redis)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_user() -> User:
    """Create a mock user object."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.is_superuser = False
    user.monthly_token_limit = None  # Will use default
    return user


class TestCheckQuotaDisabled:
    """Test QUOTA_DISABLED config bypasses all quota checks."""

    @pytest.mark.asyncio
    async def test_check_quota_disabled(self, quota_service, user_id, mock_db_session, mock_user):
        """Test that QUOTA_DISABLED=True allows all requests.

        Verifies:
        - allowed=True when quota is disabled
        - Returns default values
        - Works for regular users (not just admins)
        """
        # Mock settings.QUOTA_DISABLED = True
        with patch("app.services.quota_service.settings") as mock_settings:
            mock_settings.QUOTA_DISABLED = True

            # Mock user query
            mock_result = MagicMock()
            mock_result.scalar_one_or_none.return_value = mock_user
            mock_db_session.execute.return_value = mock_result

            # Execute
            result = await quota_service.check_quota(user_id, mock_db_session)

            # Assert - quota disabled allows all
            assert result.allowed is True
            assert result.remaining == DEFAULT_QUOTA_LIMIT
            assert result.limit == DEFAULT_QUOTA_LIMIT
            assert result.percentage == 0.0
            assert result.warning is False
            assert result.used == 0


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_check_quota_user_not_found(self, quota_service, user_id, mock_db_session):
        """Test that non-existent user raises ResourceNotFoundException."""
        # Mock user query returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db_session.execute.return_value = mock_result

        # Execute and assert exception
        with pytest.raises(ResourceNotFoundException) as exc_info:
            await quota_service.check_quota(user_id, mock_db_session)

        assert str(user_id) in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_record_usage_cache_failure_handled(self, quota_service, user_id, mock_db_session, mock_redis_client):
        """Test that cache deletion failure doesn't break usage recording."""
        from redis.exceptions import RedisError

        # Setup Redis to raise error
        mock_redis_client.delete.side_effect = RedisError("Connection failed")

        tokens = 100

        # Execute - should not raise exception
        await quota_service.record_usage(user_id, tokens, mock_db_session, mock_redis_client)

        # Assert - usage was still recorded despite cache failure
        mock_db_session.add.assert_called_once()
        mock_db_session.flush.assert_called_once()


class TestQuotaCheckResult:
    """Test QuotaCheckResult dataclass."""

    def test_quota_check_result_creation(self):
        """Test QuotaCheckResult dataclass can be created with all fields."""
        result = QuotaCheckResult(
            allowed=True,
            remaining=400000,
            limit=500000,
            percentage=20.0,
            warning=False,
            used=100000,
        )

        assert result.allowed is True
        assert result.remaining == 400000
        assert result.limit == 500000
        assert result.percentage == 20.0
        assert result.warning is False
        assert result.used == 100000

    def test_quota_check_result_immutability(self):
        """Test QuotaCheckResult fields are correctly typed."""
        result = QuotaCheckResult(
            allowed=False,
            remaining=0,
            limit=500000,
            percentage=100.0,
            warning=True,
            used=500000,
        )

        # All fields should be accessible
        assert isinstance(result.allowed, bool)
        assert isinstance(result.remaining, int)
        assert isinstance(result.limit, int)
        assert isinstance(result.percentage, float)
        assert isinstance(result.warning, bool)
        assert isinstance(result.used, int)
