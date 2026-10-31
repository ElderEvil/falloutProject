import logging
from typing import Final
from uuid import uuid4

from redis.asyncio import Redis

logger = logging.getLogger(__name__)

TICK_CHAIN_LEASE_SECONDS: Final = 300
TICK_CHAIN_HEARTBEAT_SECONDS: Final = 30
_CLAIM_CHAIN_SCRIPT: Final = """
if redis.call('exists', KEYS[1]) == 0 then
    redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
    redis.call('set', KEYS[2], ARGV[1], 'EX', ARGV[3])
    return 1
end
return 0
"""
_RENEW_CHAIN_SCRIPT: Final = """
if redis.call('get', KEYS[1]) == ARGV[1] then
    redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
    redis.call('set', KEYS[2], ARGV[1], 'EX', ARGV[3])
    return 1
end
return 0
"""
_TAKEOVER_CHAIN_SCRIPT: Final = """
if redis.call('exists', KEYS[2]) == 0 then
    redis.call('del', KEYS[1])
    redis.call('set', KEYS[1], ARGV[1], 'EX', ARGV[2])
    redis.call('set', KEYS[2], ARGV[1], 'EX', ARGV[3])
    return 1
end
return 0
"""


async def claim_tick_chain(redis: Redis, key: str, token: str | None) -> str | None:
    """Claim a new tick chain, renew a continuation, or take over a stale lease.

    ``token=None`` is the bootstrap/watchdog path: it claims a fresh chain when
    the key is absent, and takes over a stale lease whose heartbeat has expired
    so a dead chain recovers within the heartbeat TTL instead of the lease TTL.
    """
    candidate = token or uuid4().hex
    heartbeat_key = f"{key}:heartbeat"
    if token is None:
        claimed = await redis.eval(
            _CLAIM_CHAIN_SCRIPT,
            2,
            key,
            heartbeat_key,
            candidate,
            TICK_CHAIN_LEASE_SECONDS,
            TICK_CHAIN_HEARTBEAT_SECONDS,
        )
        if claimed:
            logger.info("Claimed new tick chain for %s", key)
            return candidate
        if await redis.exists(heartbeat_key):
            logger.debug("Tick chain %s is alive - watchdog not taking over", key)
            return None
        took_over = await redis.eval(
            _TAKEOVER_CHAIN_SCRIPT,
            2,
            key,
            heartbeat_key,
            candidate,
            TICK_CHAIN_LEASE_SECONDS,
            TICK_CHAIN_HEARTBEAT_SECONDS,
        )
        if took_over:
            logger.warning("Took over stale tick chain for %s (heartbeat expired)", key)
            return candidate
        logger.debug("Takeover race lost for %s", key)
        return None

    renewed = await redis.eval(
        _RENEW_CHAIN_SCRIPT,
        2,
        key,
        heartbeat_key,
        candidate,
        TICK_CHAIN_LEASE_SECONDS,
        TICK_CHAIN_HEARTBEAT_SECONDS,
    )
    if renewed:
        logger.debug("Renewed tick chain lease for %s", key)
        return candidate
    logger.warning("Lost tick chain lease for %s - another owner took over", key)
    return None
