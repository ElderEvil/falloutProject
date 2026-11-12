"""Redis notification fan-out across independent transport instances."""

import asyncio
import json
from uuid import uuid4

import fakeredis.aioredis
import pytest
from redis.asyncio.client import PubSub
from redis.exceptions import ConnectionError as RedisConnectionError

from app.core.stream_manager import sse_manager
from app.core.websocket_manager import ConnectionManager


@pytest.fixture
def redis_server(monkeypatch: pytest.MonkeyPatch):
    server = fakeredis.FakeServer()
    monkeypatch.setattr(
        "app.core.websocket_manager.Redis.from_url",
        lambda *_args, **_kwargs: fakeredis.aioredis.FakeRedis(server=server, decode_responses=True),
    )
    return server


async def test_worker_notification_reaches_api_sse_without_a_websocket(redis_server) -> None:
    api = ConnectionManager()
    worker = ConnectionManager()
    user_id = uuid4()
    event = {"type": "notification", "notification": {"id": str(uuid4()), "title": "Training complete"}}
    stream = sse_manager.subscribe(user_id, "notifications")
    pending = asyncio.create_task(anext(stream))
    try:
        await api.start_redis()
        await worker.send_personal_message(event, user_id)
        assert await asyncio.wait_for(pending, 1) == event
        assert api.active_connections == {}
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await stream.aclose()
        await api.stop_redis()
        await worker.stop_redis()
        await sse_manager.close()


async def test_local_notification_is_not_echoed_back_from_redis(redis_server) -> None:
    api = ConnectionManager()
    user_id = uuid4()
    event = {"type": "notification", "notification": {"id": str(uuid4())}}
    stream = sse_manager.subscribe(user_id, "notifications")
    pending = asyncio.create_task(anext(stream))
    try:
        await api.start_redis()
        await api.send_personal_message(event, user_id)
        await sse_manager.publish(user_id, "notifications", event)
        assert await asyncio.wait_for(pending, 1) == event
        with pytest.raises(TimeoutError):
            await asyncio.wait_for(anext(stream), 0.05)
    finally:
        pending.cancel()
        await asyncio.gather(pending, return_exceptions=True)
        await stream.aclose()
        await api.stop_redis()
        await sse_manager.close()


async def test_invalid_or_unrelated_messages_do_not_leak_or_break_delivery(redis_server) -> None:
    api = ConnectionManager()
    user_id, other_id = uuid4(), uuid4()
    stream = sse_manager.subscribe(user_id, "notifications")
    other_stream = sse_manager.subscribe(other_id, "notifications")
    pending = asyncio.create_task(anext(stream))
    other_pending = asyncio.create_task(anext(other_stream))
    event = {"type": "notification", "notification": {"id": str(uuid4())}}
    worker = ConnectionManager()
    try:
        await api.start_redis()
        async with fakeredis.aioredis.FakeRedis(server=redis_server, decode_responses=True) as redis:
            for invalid in (
                "not-json",
                "[]",
                '{"payload":null}',
                '{"msg_type":"personal","payload":{},"user_id":"bad"}',
            ):
                await redis.publish(api.redis_channel, invalid)
        await worker.send_personal_message({"type": "unrelated"}, user_id)
        await worker.send_chat_message({"type": "chat"}, user_id, uuid4())
        await worker.send_personal_message(event, user_id)
        assert await asyncio.wait_for(pending, 1) == event
        assert not other_pending.done()
    finally:
        for task in (pending, other_pending):
            task.cancel()
        await asyncio.gather(pending, other_pending, return_exceptions=True)
        await stream.aclose()
        await other_stream.aclose()
        await api.stop_redis()
        await worker.stop_redis()
        await sse_manager.close()


@pytest.mark.slow
async def test_disconnect_closes_only_notification_streams_then_recovers(redis_server, monkeypatch) -> None:
    original_listen = PubSub.listen
    fail_next = asyncio.Event()
    recovered = asyncio.Event()
    disconnected = False

    async def interrupted_listen(pubsub):
        nonlocal disconnected
        async for message in original_listen(pubsub):
            if fail_next.is_set() and message["type"] == "message":
                fail_next.clear()
                disconnected = True
                raise RedisConnectionError("injected network disconnect")
            if disconnected and message["type"] == "subscribe":
                recovered.set()
            yield message

    monkeypatch.setattr(PubSub, "listen", interrupted_listen)
    api, worker = ConnectionManager(), ConnectionManager()
    user_id = uuid4()
    stream = sse_manager.subscribe(user_id, "notifications")
    ticks = sse_manager.subscribe(user_id, "game_ticks")
    pending = asyncio.create_task(anext(stream))
    tick_pending = asyncio.create_task(anext(ticks))
    next_stream = None
    try:
        await api.start_redis()
        fail_next.set()
        await worker.send_personal_message({"type": "notification"}, user_id)
        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(pending, 1)
        assert not tick_pending.done()
        await sse_manager.publish(user_id, "game_ticks", {"tick": 1})
        assert await asyncio.wait_for(tick_pending, 1) == {"tick": 1}
        await asyncio.wait_for(recovered.wait(), 3)
        next_stream = sse_manager.subscribe(user_id, "notifications")
        pending = asyncio.create_task(anext(next_stream))
        event = {"type": "notification", "notification": {"id": str(uuid4())}}
        await worker.send_personal_message(event, user_id)
        assert await asyncio.wait_for(pending, 1) == event
    finally:
        pending.cancel()
        tick_pending.cancel()
        await asyncio.gather(pending, tick_pending, return_exceptions=True)
        for iterator in (stream, ticks, next_stream):
            if iterator is not None:
                await iterator.aclose()
        listener = api.listener_task
        await api.stop_redis()
        assert listener is not None
        assert listener.done()
        assert api.redis is None
        async with fakeredis.aioredis.FakeRedis(server=redis_server) as redis:
            assert (await redis.pubsub_numsub(api.redis_channel))[0][1] == 0
        await worker.stop_redis()
        await sse_manager.close()
