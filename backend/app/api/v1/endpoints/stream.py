import asyncio
import contextlib
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent

from app.api.deps import CurrentUser, get_user_vault_or_403
from app.core.config import settings
from app.core.game_config import game_config
from app.models.vault import Vault
from app.services.stream_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter()


async def _with_heartbeat(
    stream: AsyncIterable[dict[str, Any]],
    interval: int = settings.SSE_HEARTBEAT_INTERVAL,
) -> AsyncIterator[dict[str, Any] | None]:
    """Interleave heartbeat sentinels into an SSE event stream.

    Uses ``asyncio.wait`` instead of ``asyncio.wait_for`` so the
    underlying ``__anext__`` task is **never cancelled** — the subscriber
    stays alive across heartbeat timeouts.
    """
    it = stream.__aiter__()
    task: asyncio.Task | None = None
    try:
        while True:
            if task is None:
                task = asyncio.create_task(it.__anext__())
            done, _pending = await asyncio.wait([task], timeout=interval)
            if done:
                try:
                    data = task.result()
                    yield data
                    task = None
                except StopAsyncIteration:
                    return
            else:
                yield None
    finally:
        if task is not None and not task.done():
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task


@router.get("/stream/notifications", response_class=EventSourceResponse)
async def stream_notifications(
    current_user: CurrentUser,
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
    async for data in _with_heartbeat(sse_manager.subscribe(current_user.id, "notifications")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="notification")


@router.get("/stream/game/{vault_id}/ticks", response_class=EventSourceResponse)
async def stream_game_ticks(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
    # Use game tick interval as heartbeat — no point heartbeating faster
    # than the actual data cadence.
    stream = sse_manager.subscribe(vault.id, "game_ticks")
    async for data in _with_heartbeat(stream, interval=game_config.game_loop.tick_interval):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="tick")


@router.get("/stream/exploration/{vault_id}", response_class=EventSourceResponse)
async def stream_exploration(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
    async for data in _with_heartbeat(sse_manager.subscribe(vault.id, "exploration")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="exploration")


@router.get("/stream/incidents/{vault_id}", response_class=EventSourceResponse)
async def stream_incidents(
    vault: Annotated[Vault, Depends(get_user_vault_or_403)],
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
    async for data in _with_heartbeat(sse_manager.subscribe(vault.id, "incidents")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="incident")
