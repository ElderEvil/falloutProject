"""Shared per-user send limit: Redis-backed across workers, with a local fallback."""

from uuid import uuid4

import fakeredis.aioredis
import pytest

from app.services.direct_message_service import DirectMessageService
from app.utils.exceptions import ValidationException


class _BrokenRedis:
    async def incr(self, *_args, **_kwargs):
        raise RuntimeError("redis unreachable")

    async def expire(self, *_args, **_kwargs):
        raise RuntimeError("redis unreachable")

    async def delete(self, *_args, **_kwargs):
        raise RuntimeError("redis unreachable")


async def test_rate_limit_is_shared_across_service_instances() -> None:
    """Two workers must share one counter, so an in-process deque alone is not enough."""
    redis = fakeredis.aioredis.FakeRedis(decode_responses=True)
    first, second = DirectMessageService(), DirectMessageService()
    first.max_sends_per_window = 1
    second.max_sends_per_window = 1
    user_id = uuid4()

    await first._check_rate(user_id, redis)

    with pytest.raises(ValidationException):
        await second._check_rate(user_id, redis)
    await redis.aclose()


async def test_rate_limit_falls_back_when_redis_is_unreachable() -> None:
    service = DirectMessageService()
    service.max_sends_per_window = 1
    user_id = uuid4()

    await service._check_rate(user_id, _BrokenRedis())

    with pytest.raises(ValidationException):
        await service._check_rate(user_id, _BrokenRedis())
