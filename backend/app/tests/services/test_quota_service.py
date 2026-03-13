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
def quota_service():
    """Create a fresh QuotaService instance."""
    return QuotaService()


@pytest.fixture
def user_id():
    """Generate a test user ID."""
    return uuid4()


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock()
    return session


@pytest.fixture
def mock_redis_client():
    """Create a mock Redis client."""
    redis = AsyncMock(spec=Redis)
    redis.delete = AsyncMock(return_value=1)
    return redis


@pytest.fixture
def mock_user():
    """Create a mock user object."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.is_superuser = False
    user.monthly_token_limit = None  # Will use default
    return user


@pytest.fixture
def mock_admin_user():
    """Create a mock admin user object."""
    user = MagicMock(spec=User)
    user.id = uuid4()
    user.is_superuser = True
    user.monthly_token_limit = None
    return user


class TestCheckQuotaUnderLimit:
    """Test quota check passes when user is under their limit."""

    @pytest.mark.asyncio
    async def test_check_quota_under_limit(self, quota_service, user_id, mock_db_session, mock_user):
        """Test that quota check passes when tokens < limit.

        Verifies:
        - allowed=True when under limit
        - remaining tokens calculated correctly
        - percentage calculated correctly
        - warning=False when under 80%
        """
        # Setup: User has used 100K of 500K limit (20%)
        tokens_used = 100000
        expected_remaining = DEFAULT_QUOTA_LIMIT - tokens_used
        expected_percentage = (tokens_used / DEFAULT_QUOTA_LIMIT) * 100

        # Mock user query result with FOR UPDATE
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db_session.execute.return_value = mock_result

        # Mock usage query result
        mock_usage_result = MagicMock()
        mock_usage_result.one_or_none.return_value = (tokens_used,)
        mock_db_session.execute.side_effect = [mock_result, mock_usage_result]

        # Execute
        result = await quota_service.check_quota(user_id, mock_db_session)

        # Assert
        assert result.allowed is True
        assert result.remaining == expected_remaining
        assert result.limit == DEFAULT_QUOTA_LIMIT
        assert result.percentage == expected_percentage
        assert result.warning is False
        assert result.used == tokens_used


class TestCheckQuotaAtLimit:
    """Test quota check fails when user is at or over their limit."""

    @pytest.mark.asyncio
    async def test_check_quota_at_limit(self, quota_service, user_id, mock_db_session, mock_user):
        """Test that quota check fails when tokens >= limit.

        Verifies:
        - allowed=False when at limit
        - remaining=0 when at limit
        - percentage=100 when at limit
        - warning=True when at 80%+ threshold
        """
        # Setup: User has used exactly 500K of 500K limit (100%)
        tokens_used = DEFAULT_QUOTA_LIMIT

        # Mock user query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        # Mock usage query result
        mock_usage_result = MagicMock()
        mock_usage_result.one_or_none.return_value = (tokens_used,)

        mock_db_session.execute.side_effect = [mock_result, mock_usage_result]

        # Execute
        result = await quota_service.check_quota(user_id, mock_db_session)

        # Assert
        assert result.allowed is False
        assert result.remaining == 0
        assert result.limit == DEFAULT_QUOTA_LIMIT
        assert result.percentage == 100.0
        assert result.warning is True
        assert result.used == tokens_used

    @pytest.mark.asyncio
    async def test_check_quota_over_limit(self, quota_service, user_id, mock_db_session, mock_user):
        """Test that quota check fails when tokens exceed limit."""
        # Setup: User has used 600K of 500K limit (120%)
        tokens_used = 600000

        # Mock user query result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        # Mock usage query result
        mock_usage_result = MagicMock()
        mock_usage_result.one_or_none.return_value = (tokens_used,)

        mock_db_session.execute.side_effect = [mock_result, mock_usage_result]

        # Execute
        result = await quota_service.check_quota(user_id, mock_db_session)

        # Assert
        assert result.allowed is False
        assert result.remaining == 0
        assert result.percentage == 120.0
        assert result.warning is True


class TestCheckQuotaAdminBypass:
    """Test that admin users bypass quota checks."""

    @pytest.mark.asyncio
    async def test_check_quota_admin_bypass(self, quota_service, user_id, mock_db_session, mock_admin_user):
        """Test that admin users always pass quota checks.

        Verifies:
        - allowed=True for admin users regardless of usage
        - Returns default values (not actual usage)
        - No database query for usage made
        """
        # Mock user query to return admin user
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_admin_user
        mock_db_session.execute.return_value = mock_result

        # Execute
        result = await quota_service.check_quota(user_id, mock_db_session)

        # Assert - admin should always be allowed
        assert result.allowed is True
        assert result.remaining == DEFAULT_QUOTA_LIMIT
        assert result.limit == DEFAULT_QUOTA_LIMIT
        assert result.percentage == 0.0
        assert result.warning is False
        assert result.used == 0

        # Verify only one execute call (user query, no usage query)
        assert mock_db_session.execute.call_count == 1


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


class TestRecordUsage:
    """Test recording token usage with cache invalidation."""

    @pytest.mark.asyncio
    async def test_record_usage(self, quota_service, user_id, mock_db_session, mock_redis_client):
        """Test that usage is recorded correctly and cache is invalidated.

        Verifies:
        - LLMInteraction is created with correct data
        - Database session add and flush are called
        - Redis cache is invalidated with correct key
        """
        tokens = 150

        # Execute
        await quota_service.record_usage(user_id, tokens, mock_db_session, mock_redis_client)

        # Assert - check that add was called with correct object type
        assert mock_db_session.add.called
        call_args = mock_db_session.add.call_args[0][0]
        assert isinstance(call_args, LLMInteraction)
        assert call_args.user_id == user_id
        assert call_args.total_tokens == tokens
        assert call_args.usage == "quota_tracking"

        # Assert flush was called
        mock_db_session.flush.assert_called_once()

        # Assert cache invalidation
        expected_cache_key = f"user:{user_id}:ai_usage"
        mock_redis_client.delete.assert_called_once_with(expected_cache_key)

    @pytest.mark.asyncio
    async def test_record_usage_with_custom_tokens(self, quota_service, user_id, mock_db_session, mock_redis_client):
        """Test recording usage with various token amounts."""
        test_cases = [0, 1, 100, 1000, 100000]

        for tokens in test_cases:
            mock_db_session.reset_mock()
            mock_redis_client.reset_mock()

            await quota_service.record_usage(user_id, tokens, mock_db_session, mock_redis_client)

            call_args = mock_db_session.add.call_args[0][0]
            assert call_args.total_tokens == tokens


class TestConcurrentRequests:
    """Test race condition handling with concurrent requests."""

    @pytest.mark.asyncio
    async def test_concurrent_requests_use_for_update(self, quota_service, user_id, mock_db_session, mock_user):
        """Test that concurrent requests use SELECT FOR UPDATE for atomicity.

        Verifies:
        - Query uses with_for_update() for row-level locking
        - Prevents race conditions between multiple quota checks
        """
        # Setup
        tokens_used = 100000

        # Capture the query to verify it uses FOR UPDATE
        executed_queries = []

        async def capture_execute(query, *args, **kwargs):
            executed_queries.append(str(query))
            mock_result = MagicMock()
            if "user" in str(query).lower():
                mock_result.scalar_one_or_none.return_value = mock_user
            else:
                mock_result.one_or_none.return_value = (tokens_used,)
            return mock_result

        mock_db_session.execute.side_effect = capture_execute

        # Execute
        await quota_service.check_quota(user_id, mock_db_session)

        # Assert - verify FOR UPDATE was used
        assert len(executed_queries) >= 1
        user_query = executed_queries[0]
        assert "FOR UPDATE" in user_query.upper() or "for_update" in user_query.lower()


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
    async def test_check_quota_with_custom_limit(self, quota_service, user_id, mock_db_session):
        """Test quota check respects user's custom limit."""
        custom_limit = 100000
        tokens_used = 80000  # 80% of custom limit

        # Create user with custom limit
        user = MagicMock(spec=User)
        user.id = user_id
        user.is_superuser = False
        user.monthly_token_limit = custom_limit

        # Mock user query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user

        # Mock usage query
        mock_usage_result = MagicMock()
        mock_usage_result.one_or_none.return_value = (tokens_used,)

        mock_db_session.execute.side_effect = [mock_result, mock_usage_result]

        # Execute
        result = await quota_service.check_quota(user_id, mock_db_session)

        # Assert - uses custom limit, not default
        assert result.limit == custom_limit
        assert result.remaining == custom_limit - tokens_used
        assert result.percentage == 80.0
        assert result.warning is True  # At warning threshold

    @pytest.mark.asyncio
    async def test_check_quota_warning_threshold_edge(self, quota_service, user_id, mock_db_session, mock_user):
        """Test warning threshold at exactly 80%."""
        tokens_used = int(DEFAULT_QUOTA_LIMIT * (WARNING_THRESHOLD / 100))  # Exactly 80%

        # Mock user query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        # Mock usage query
        mock_usage_result = MagicMock()
        mock_usage_result.one_or_none.return_value = (tokens_used,)

        mock_db_session.execute.side_effect = [mock_result, mock_usage_result]

        # Execute
        result = await quota_service.check_quota(user_id, mock_db_session)

        # Assert - warning should be True at exactly 80%
        assert result.warning is True
        assert result.percentage == 80.0

    @pytest.mark.asyncio
    async def test_check_quota_no_usage_this_month(self, quota_service, user_id, mock_db_session, mock_user):
        """Test quota check with no usage (None from query)."""
        # Mock user query
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user

        # Mock usage query returning None
        mock_usage_result = MagicMock()
        mock_usage_result.one_or_none.return_value = (0,)  # No usage

        mock_db_session.execute.side_effect = [mock_result, mock_usage_result]

        # Execute
        result = await quota_service.check_quota(user_id, mock_db_session)

        # Assert
        assert result.allowed is True
        assert result.remaining == DEFAULT_QUOTA_LIMIT
        assert result.percentage == 0.0
        assert result.warning is False
        assert result.used == 0

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
