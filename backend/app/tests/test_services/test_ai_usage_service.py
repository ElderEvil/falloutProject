from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.ai_usage import AIOperationStats, AIUsageResponse, AIUsageStats, QuotaInfo
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
        with (
            patch.object(
                service,
                "_aggregate_tokens",
                new_callable=AsyncMock,
                side_effect=[
                    AIUsageStats(prompt_tokens=10, completion_tokens=20, total_tokens=30),
                    AIUsageStats(prompt_tokens=5, completion_tokens=5, total_tokens=10),
                ],
            ),
            patch.object(service, "_aggregate_by_operation", new_callable=AsyncMock, return_value=[]),
        ):
            response = await service.get_user_usage(db_session, user_id)

        assert isinstance(response, AIUsageResponse)
        assert response.all_time.total_tokens == 30
        assert response.current_month.total_tokens == 10
        assert response.quota.quota_limit == DEFAULT_QUOTA_LIMIT
        assert response.quota.quota_used == 10
        assert response.quota.quota_remaining == DEFAULT_QUOTA_LIMIT - 10
        assert response.by_operation == []
        assert response.chat_heavy is False

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
        with (
            patch.object(
                service,
                "_aggregate_tokens",
                new_callable=AsyncMock,
                side_effect=[
                    AIUsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    AIUsageStats(prompt_tokens=80, completion_tokens=10, total_tokens=90),
                ],
            ),
            patch.object(service, "_aggregate_by_operation", new_callable=AsyncMock, return_value=[]),
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
        with (
            patch.object(
                service,
                "_aggregate_tokens",
                new_callable=AsyncMock,
                side_effect=[
                    AIUsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0),
                    AIUsageStats(prompt_tokens=50, completion_tokens=10, total_tokens=60),
                ],
            ),
            patch.object(service, "_aggregate_by_operation", new_callable=AsyncMock, return_value=[]),
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
        with (
            patch.object(
                service,
                "_aggregate_tokens",
                new_callable=AsyncMock,
                return_value=AIUsageStats(prompt_tokens=0, completion_tokens=0, total_tokens=0),
            ),
            patch.object(service, "_aggregate_by_operation", new_callable=AsyncMock, return_value=[]),
        ):
            response = await service.get_user_usage(db_session, user_id)

        assert response.quota.quota_percentage == 0.0

    async def test_get_user_usage_includes_by_operation_and_chat_heavy(self) -> None:
        """Monthly per-operation breakdown is passed through and chat_heavy computed."""
        user_id = uuid4()
        db_session = AsyncMock()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = None
        db_session.execute = AsyncMock(return_value=user_result)

        by_operation = [
            AIOperationStats(
                operation="chat_with_dweller", prompt_tokens=80, completion_tokens=10, total_tokens=90, count=9
            ),
            AIOperationStats(
                operation="generate_backstory", prompt_tokens=5, completion_tokens=5, total_tokens=10, count=1
            ),
        ]
        service = AIUsageService()
        with (
            patch.object(
                service,
                "_aggregate_tokens",
                new_callable=AsyncMock,
                return_value=AIUsageStats(prompt_tokens=85, completion_tokens=15, total_tokens=100),
            ),
            patch.object(
                service, "_aggregate_by_operation", new_callable=AsyncMock, return_value=by_operation
            ) as mock_by_operation,
        ):
            response = await service.get_user_usage(db_session, user_id)

        assert response.by_operation == by_operation
        assert response.chat_heavy is True
        mock_by_operation.assert_awaited_once()

    async def test_get_user_usage_chat_heavy_false_when_mixed(self) -> None:
        """chat_heavy stays False when chat_with_dweller is at or below 80%."""
        user_id = uuid4()
        db_session = AsyncMock()

        user_result = MagicMock()
        user_result.scalar_one_or_none.return_value = None
        db_session.execute = AsyncMock(return_value=user_result)

        by_operation = [
            AIOperationStats(
                operation="chat_with_dweller", prompt_tokens=40, completion_tokens=10, total_tokens=50, count=5
            ),
            AIOperationStats(operation="extend_bio", prompt_tokens=40, completion_tokens=10, total_tokens=50, count=5),
        ]
        service = AIUsageService()
        with (
            patch.object(
                service,
                "_aggregate_tokens",
                new_callable=AsyncMock,
                return_value=AIUsageStats(prompt_tokens=80, completion_tokens=20, total_tokens=100),
            ),
            patch.object(service, "_aggregate_by_operation", new_callable=AsyncMock, return_value=by_operation),
        ):
            response = await service.get_user_usage(db_session, user_id)

        assert response.chat_heavy is False

    def test_chat_heavy_ignores_operational_usage(self) -> None:
        """Quota bookkeeping must not dilute the user-facing chat anomaly signal."""
        by_operation = [
            AIOperationStats(
                operation="chat_with_dweller", prompt_tokens=80, completion_tokens=10, total_tokens=90, count=9
            ),
            AIOperationStats(
                operation="generate_backstory", prompt_tokens=5, completion_tokens=5, total_tokens=10, count=1
            ),
            AIOperationStats(
                operation="quota_tracking",
                prompt_tokens=900,
                completion_tokens=0,
                total_tokens=900,
                count=9,
                is_operational=True,
            ),
        ]

        assert AIUsageService._is_chat_heavy(by_operation) is True

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

    async def test_aggregate_by_operation_maps_rows(self) -> None:
        """Rows map to AIOperationStats; quota_tracking flagged operational."""
        user_id = uuid4()
        db_session = AsyncMock()

        rows = [
            SimpleNamespace(
                operation="chat_with_dweller",
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                interaction_count=2,
            ),
            SimpleNamespace(
                operation="quota_tracking", prompt_tokens=0, completion_tokens=0, total_tokens=5, interaction_count=1
            ),
            SimpleNamespace(
                operation="unknown", prompt_tokens=1, completion_tokens=1, total_tokens=2, interaction_count=1
            ),
        ]
        result = MagicMock()
        result.all.return_value = rows
        db_session.exec = AsyncMock(return_value=result)

        stats = await AIUsageService()._aggregate_by_operation(db_session, user_id)

        assert [s.operation for s in stats] == ["chat_with_dweller", "quota_tracking", "unknown"]
        assert stats[0].prompt_tokens == 10
        assert stats[0].completion_tokens == 20
        assert stats[0].total_tokens == 30
        assert stats[0].count == 2
        assert stats[0].is_operational is False
        assert stats[1].total_tokens == 5
        assert stats[1].is_operational is True
        assert stats[2].operation == "unknown"
        db_session.exec.assert_awaited_once()

    async def test_aggregate_by_operation_empty(self) -> None:
        """Returns an empty list when no interactions exist."""
        user_id = uuid4()
        db_session = AsyncMock()

        result = MagicMock()
        result.all.return_value = []
        db_session.exec = AsyncMock(return_value=result)

        stats = await AIUsageService()._aggregate_by_operation(db_session, user_id)

        assert stats == []
        db_session.exec.assert_awaited_once()

    async def test_aggregate_by_operation_with_since(self) -> None:
        """Per-operation query accepts the optional since filter."""
        user_id = uuid4()
        db_session = AsyncMock()

        result = MagicMock()
        result.all.return_value = []
        db_session.exec = AsyncMock(return_value=result)

        service = AIUsageService()
        stats = await service._aggregate_by_operation(db_session, user_id, since=datetime(2026, 8, 1))

        assert stats == []
        db_session.exec.assert_awaited_once()

    async def test_aggregate_by_operation_logs_and_reraises(self) -> None:
        """Per-operation aggregation errors are logged and re-raised."""
        user_id = uuid4()
        db_session = AsyncMock()
        db_session.exec = AsyncMock(side_effect=RuntimeError("DB failure"))

        service = AIUsageService()
        with (
            patch("app.services.ai_usage_service.logger.exception") as mock_log,
            pytest.raises(RuntimeError, match="DB failure"),
        ):
            await service._aggregate_by_operation(db_session, user_id)
        mock_log.assert_called_once()

    async def test_module_singleton(self) -> None:
        """The module-level ai_usage_service is an AIUsageService instance."""
        assert isinstance(ai_usage_service, AIUsageService)


class TestIsChatHeavy:
    """Threshold logic for the chat_heavy anomaly flag (sync, no DB)."""

    def test_strictly_above_threshold(self) -> None:
        chat = AIOperationStats(operation="chat_with_dweller", total_tokens=81, count=1)
        other = AIOperationStats(operation="generate_backstory", total_tokens=19, count=1)

        assert AIUsageService._is_chat_heavy([chat, other]) is True

    def test_at_threshold_is_not_heavy(self) -> None:
        chat = AIOperationStats(operation="chat_with_dweller", total_tokens=80, count=1)
        other = AIOperationStats(operation="generate_backstory", total_tokens=20, count=1)

        assert AIUsageService._is_chat_heavy([chat, other]) is False

    def test_chat_alone_is_heavy(self) -> None:
        chat = AIOperationStats(operation="chat_with_dweller", total_tokens=10, count=1)

        assert AIUsageService._is_chat_heavy([chat]) is True

    def test_empty_usage_is_not_heavy(self) -> None:
        assert AIUsageService._is_chat_heavy([]) is False
