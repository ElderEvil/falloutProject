import pytest
from fakeredis.aioredis import FakeRedis

from app.services.tick_chain import claim_tick_chain

CHAIN_KEY = "test:incident-tick"
HEARTBEAT_KEY = "test:incident-tick:heartbeat"


@pytest.mark.asyncio
async def test_only_one_bootstrap_claims_a_tick_chain():
    redis = FakeRedis(decode_responses=True)

    first = await claim_tick_chain(redis, CHAIN_KEY, None)
    second = await claim_tick_chain(redis, CHAIN_KEY, None)
    continuation = await claim_tick_chain(redis, CHAIN_KEY, first)

    assert first is not None
    assert second is None
    assert continuation == first
    await redis.aclose()


@pytest.mark.asyncio
async def test_watchdog_takes_over_a_stale_lease_when_the_heartbeat_expires():
    """A dead chain's lingering lease must not block the watchdog until TTL expiry."""
    redis = FakeRedis(decode_responses=True)

    original = await claim_tick_chain(redis, CHAIN_KEY, None)
    assert original is not None
    # Simulate a dead chain: the heartbeat expires while the lease key lingers.
    await redis.delete(HEARTBEAT_KEY)

    takeover = await claim_tick_chain(redis, CHAIN_KEY, None)

    assert takeover is not None
    assert takeover != original
    await redis.aclose()


@pytest.mark.asyncio
async def test_watchdog_does_not_steal_a_live_lease():
    """A fresh heartbeat means the chain is alive - the watchdog must back off."""
    redis = FakeRedis(decode_responses=True)

    original = await claim_tick_chain(redis, CHAIN_KEY, None)
    assert original is not None

    stolen = await claim_tick_chain(redis, CHAIN_KEY, None)

    assert stolen is None
    await redis.aclose()


@pytest.mark.asyncio
async def test_renewal_refreshes_the_heartbeat():
    """Renewing the lease must also refresh the heartbeat so a live chain is never stolen."""
    redis = FakeRedis(decode_responses=True)

    token = await claim_tick_chain(redis, CHAIN_KEY, None)
    assert token is not None
    await redis.expire(HEARTBEAT_KEY, 1)

    renewed = await claim_tick_chain(redis, CHAIN_KEY, token)

    assert renewed == token
    assert await redis.ttl(HEARTBEAT_KEY) > 1
    await redis.aclose()
