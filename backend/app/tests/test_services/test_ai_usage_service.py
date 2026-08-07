from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.ai_usage import AIUsageResponse, AIUsageStats, QuotaInfo
from app.services.ai_usage_service import AIUsageService, ai_usage_service
from app.services.quota_service import DEFAULT_QUOTA_LIMIT


@pytest.mark.asyncio
class TestAIUsageService:
    """Tests for AIUsageService token aggregation and quota reporting."""

    async def test_get_user_usage_with_default_quota(self) -> None:
        """Response uses DEFAULT_QUOTA_LIMIT when user has no custom limit."""
        user_id = uuid4()
        db_session = AsyncMock()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = None
        db_session.execute = AsyncMock(return_value=user_result)

        service = AIUsageService()
        with patch.object(
            service,
            "_aggregate_tokens",
            new_callable=AsyncMock,
            side_effect=[
                AIUsageStats(prompt_tokens=10, completion_tokens=20, total_tokens=30),
                AIUsageStats(prompt_tokens=5, completion_tokens=5, total_tokens=10),
            ],
        ):
            response = await service.get_user_usage(db_session, user_id)

        assert isinstance(response, AIUsageResponse)
        assert response.all_time.total_tokens == 30
        assert response.current_month.total_tokens == 10
        assert response.quota.quota_limit == DEFAULT_QUOTA_LIMIT
        assert response.quota.quota_used == 10
        assert response.quota.quota_remaining == DEFAULT_QUOTA_LIMIT - 10

    async def test_get_user_usage_with_custom_quota(self) -> None:
        """Response respects the user's monthly_token_limit."""
        user_id = uuid4()
        db_session = AsyncMock()

        user = MagicMock()
        user.monthly_token_limit = 100
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        db_session.execute = AsyncMock(return_value=user_result)

        service = AIUsageService()
        with patch.object(
            service,
            "_aggregate_tokens",
            new_callable=AsyncMock,
            side_effect=[
                AIUsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                AIUsageStats(prompt_tokens=80, completion_tokens=10, total_tokens=90),
            ],
        ):
            response = await service.get_user_usage(db_session, user_id)

        assert response.quota.quota_limit == 100
        assert response.quota.quota_used == 90
        assert response.quota.quota_remaining == 10
        assert response.quota.quota_percentage == 90.0
        assert response.quota.quota_warning is True
        assert response.quota.quota_exceeded is False

    async def test_get_user_usage_quota_exceeded(self) -> None:
        """Quota exceeded flag is set when usage reaches 100%."""
        user_id = uuid4()
        db_session = AsyncMock()

        user = MagicMock()
        user.monthly_token_limit = 50
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        db_session.execute = AsyncMock(return_value=user_result)

        service = AIUsageService()
        with patch.object(
            service,
            "_aggregate_tokens",
            new_callable=AsyncMock,
            side_effect=[
                AIUsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                AIUsageStats(prompt_tokens=50, completion_tokens=10, total_tokens=60),
            ],
        ):
            response = await service.get_user_usage(db_session, user_id)

        assert response.quota.quota_exceeded is True
        assert response.quota.quota_remaining == 0

    async def test_get_user_usage_zero_quota(self) -> None:
        """Percentage is 0.0 when quota limit is zero."""
        user_id = uuid4()
        db_session = AsyncMock()

        user = MagicMock()
        user.monthly_token_limit = 0
        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = user
        db_session.execute = AsyncMock(return_value=user_result)

        service = AIUsageService()
        with patch.object(
            service,
            "_aggregate_tokens",
            new_callable=AsyncMock,
            return_value=AIUsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0),
        ):
            response = await service.get_user_usage(db_session, user_id)

        assert response.quota.quota_percentage == 0.0

    async def test_get_user_usage_logs_and_reraises(self) -> None:
        """Unexpected errors are logged and re-raised."""
        user_id = uuid4()
        db_session = AsyncMock()
        db_session.execute = AsyncMock(side_effect=RuntimeError("DB failure"))

        service = AIUsageService()
        with (
            patch("app.services.ai_usage_service.logger.exception") as mock_log,
            pytest.raises(RuntimeError, match="DB failure"),
        ):
            await service.get_user_usage(db_session, user_id)
        mock_log.assert_called_once()

    async def test_aggregate_tokens_with_since(self) -> None:
        """Aggregate query filters by optional since timestamp."""
        user_id = uuid4()
        db_session = AsyncMock()

        row = MagicMock()
        row.prompt_tokens = 1
        row.completion_tokens = 2
        row.total_tokens = 3
        result = MagicMock()
        result.first.return_value = row
        db_session.exec = AsyncMock(return_value=result)

        service = AIUsageService()
        since = datetime(2026, 1, 1)
        stats = await service._aggregate_tokens(db_session, user_id, since=since)

        assert stats.total_tokens == 3
        assert stats.prompt_tokens == 1
        assert stats.completion_tokens == 2
        db_session.exec.assert_awaited_once()

    async def test_aggregate_tokens_no_row(self) -> None:
        """Returns zeros when no interactions exist."""
        user_id = uuid4()
        db_session = AsyncMock()

        result = MagicMock()
        result.first.return_value = None
        db_session.exec = AsyncMock(return_value=result)

        service = AIUsageService()
        stats = await service._aggregate_tokens(db_session, user_id)

        assert stats.total_tokens == 0
        assert stats.prompt_tokens == 0
        assert stats.completion_tokens == 0

    async def test_aggregate_tokens_logs_and_reraises(self) -> None:
        """Aggregation errors are logged and re-raised."""
        user_id = uuid4()
        db_session = AsyncMock()
        db_session.exec = AsyncMock(side_effect=RuntimeError("DB failure"))

        service = AIUsageService()
        with (
            patch("app.services.ai_usage_service.logger.exception") as mock_log,
            pytest.raises(RuntimeError, match="DB failure"),
        ):
            await service._aggregate_tokens(db_session, user_id)
        mock_log.assert_called_once()

    async def test_module_singleton(self) -> None:
        """The module-level ai_usage_service is an AIUsageService instance."""
        assert isinstance(ai_usage_service, AIUsageService)
