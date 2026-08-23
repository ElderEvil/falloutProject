import pytest
from fakeredis.aioredis import FakeRedis

from app.services.tick_chain import claim_tick_chain


@pytest.mark.asyncio
async def test_only_one_bootstrap_claims_a_tick_chain():
    redis = FakeRedis(decode_responses=True)

    first = await claim_tick_chain(redis, "test:incident-tick", None)
    second = await claim_tick_chain(redis, "test:incident-tick", None)
    continuation = await claim_tick_chain(redis, "test:incident-tick", first)

    assert first is not None
    assert second is None
    assert continuation == first
    await redis.aclose()
