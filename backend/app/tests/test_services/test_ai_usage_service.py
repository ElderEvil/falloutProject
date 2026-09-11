from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.schemas.ai_usage import AIOperationStats, AIUsageResponse, AIUsageStats, QuotaInfo
from app.services.ai_usage_service import AIUsageService, ai_usage_service
from app.services.quota_service import DEFAULT_QUOTA_LIMIT


@pytest.mark.asyncio
class TestAIUsageService:
    """Tests for AIUsageService token aggregation and quota reporting."""

    async def test_get_user_usage_zero_quota(self) -> None:
        """Percentage is 0.0 when quota limit is zero."""
        user_id = uuid4()
        db_session = AsyncMock()

        user = MagicMock()
        user.monthly_token_limit = 0
        result = MagicMock()
        result.scalar_one_or_none = MagicMock(return_value=user)
        db_session.execute = AsyncMock(return_value=result)

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

        service = AIUsageService()
        since = datetime(2026, 1, 1)
        with patch(
            "app.services.ai_usage_service.llm_interaction.aggregate_tokens",
            new_callable=AsyncMock,
            return_value=(1, 2, 3),
        ) as mock_aggregate:
            stats = await service._aggregate_tokens(db_session, user_id, since=since)

        assert stats.total_tokens == 3
        assert stats.prompt_tokens == 1
        assert stats.completion_tokens == 2
        mock_aggregate.assert_awaited_once_with(db_session, user_id, since)

    async def test_aggregate_tokens_no_row(self) -> None:
        """Returns zeros when no interactions exist."""
        user_id = uuid4()
        db_session = AsyncMock()

        service = AIUsageService()
        with patch(
            "app.services.ai_usage_service.llm_interaction.aggregate_tokens",
            new_callable=AsyncMock,
            return_value=(0, 0, 0),
        ):
            stats = await service._aggregate_tokens(db_session, user_id)

        assert stats.total_tokens == 0
        assert stats.prompt_tokens == 0
        assert stats.completion_tokens == 0

    async def test_aggregate_tokens_logs_and_reraises(self) -> None:
        """Aggregation errors are logged and re-raised."""
        user_id = uuid4()
        db_session = AsyncMock()

        service = AIUsageService()
        with (
            patch(
                "app.services.ai_usage_service.llm_interaction.aggregate_tokens",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB failure"),
            ),
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
            ("chat_with_dweller", 10, 20, 30, 2),
            ("quota_tracking", 0, 0, 5, 1),
            ("unknown", 1, 1, 2, 1),
        ]

        with patch(
            "app.services.ai_usage_service.llm_interaction.aggregate_by_operation",
            new_callable=AsyncMock,
            return_value=rows,
        ) as mock_aggregate:
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
        mock_aggregate.assert_awaited_once_with(db_session, user_id, None)

    async def test_aggregate_by_operation_with_since(self) -> None:
        """Per-operation query accepts the optional since filter."""
        user_id = uuid4()
        db_session = AsyncMock()

        service = AIUsageService()
        since = datetime(2026, 8, 1)
        with patch(
            "app.services.ai_usage_service.llm_interaction.aggregate_by_operation",
            new_callable=AsyncMock,
            return_value=[],
        ) as mock_aggregate:
            stats = await service._aggregate_by_operation(db_session, user_id, since=since)

        assert stats == []
        mock_aggregate.assert_awaited_once_with(db_session, user_id, since)

    async def test_aggregate_by_operation_logs_and_reraises(self) -> None:
        """Per-operation aggregation errors are logged and re-raised."""
        user_id = uuid4()
        db_session = AsyncMock()

        service = AIUsageService()
        with (
            patch(
                "app.services.ai_usage_service.llm_interaction.aggregate_by_operation",
                new_callable=AsyncMock,
                side_effect=RuntimeError("DB failure"),
            ),
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
