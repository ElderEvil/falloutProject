"""Regression tests for the shared AI usage cache key."""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.services.ai_constants import AI_USAGE_CACHE_KEY
from app.services.quota_service import QuotaService
from app.services.user_service import UserService


@pytest.mark.asyncio
async def test_ai_usage_services_use_the_shared_cache_key() -> None:
    """Read, write, and invalidate the same user-scoped usage cache entry."""
    user_id = uuid4()
    cache_key = AI_USAGE_CACHE_KEY.format(user_id=user_id)
    redis_client = MagicMock(get=AsyncMock(return_value=None), setex=AsyncMock(), delete=AsyncMock())
    db_session = MagicMock(flush=AsyncMock())
    usage = MagicMock(model_dump=MagicMock(return_value={"total_tokens": 42}))

    with patch("app.services.ai_usage_service.AIUsageService.get_user_usage", new=AsyncMock(return_value=usage)):
        result = await UserService().get_ai_usage(db_session, redis_client, str(user_id))

    await QuotaService().record_usage(user_id, 1, db_session, redis_client)

    assert result == {"total_tokens": 42}
    redis_client.get.assert_awaited_once_with(cache_key)
    redis_client.setex.assert_awaited_once_with(cache_key, 300, '{"total_tokens": 42}')
    redis_client.delete.assert_awaited_once_with(cache_key)
