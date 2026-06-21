import asyncio
import logging
from collections.abc import AsyncIterable, AsyncIterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Request
from fastapi.sse import EventSourceResponse, ServerSentEvent
from pydantic import UUID4
from sqlmodel.ext.asyncio.session import AsyncSession

from app.api.deps import CurrentUser, get_user_vault_or_403
from app.db.session import get_async_session
from app.models.vault import Vault
from app.schemas.chat import ChatMessage
from app.services.chat_service import chat_service
from app.services.stream_manager import sse_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Send a heartbeat comment every 30 s of inactivity so nginx / Cloudflare /
# browsers detect a dead connection within ~30 s instead of waiting minutes.
_HEARTBEAT_INTERVAL = 30


async def _with_heartbeat(
    stream: AsyncIterable[dict[str, Any]],
    interval: int = _HEARTBEAT_INTERVAL,
) -> AsyncIterator[dict[str, Any] | None]:
    """Interleave heartbeat sentinels into an SSE event stream.

    Uses ``asyncio.wait`` instead of ``asyncio.wait_for`` so the
    underlying ``__anext__`` task is **never cancelled** — the subscriber
    stays alive across heartbeat timeouts.
    """
    it = stream.__aiter__()
    task: asyncio.Task | None = None
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
    async for data in _with_heartbeat(sse_manager.subscribe(vault.id, "game_ticks")):
        if await request.is_disconnected():
            break
        if data is None:
            yield ServerSentEvent(comment="heartbeat")
            continue
        yield ServerSentEvent(data=data, event="tick")


@router.post("/stream/chat/{dweller_id}", response_class=EventSourceResponse)
async def stream_chat(
    dweller_id: UUID4,
    current_user: CurrentUser,
    message: ChatMessage,
    db_session: Annotated[AsyncSession, Depends(get_async_session)],
    request: Request,
) -> AsyncIterable[ServerSentEvent]:
    try:
        async for payload in chat_service.stream_response(db_session, current_user, dweller_id, message.message):
            if await request.is_disconnected():
                break
            event_type = payload.get("type", "message")
            yield ServerSentEvent(data=payload, event=event_type)
    except Exception:
        logger.exception("Chat SSE stream failed")
        yield ServerSentEvent(data="Internal streaming error", event="error")


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
