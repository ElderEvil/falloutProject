"""Continuation assembly: what a dweller carries into the next reply.

These tests run against a real session (no provider) and assert the four inputs that make a
conversation continuous: prior turns, the running summary, durable memories, and the digest
of what changed since the last exchange.
"""

from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, UserPromptPart
from sqlmodel.ext.asyncio.session import AsyncSession

from app.models.conversation import Conversation as ConversationRow
from app.models.dweller_memory import DwellerMemory
from app.services.chat.context import dump_context, load_context
from app.services.chat.continuation import build_continuation, save_context
from app.utils.time import utcnow


def _dweller() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), first_name="Ana", bio=None, vault=SimpleNamespace(id=uuid4()))


def _thread(**overrides) -> ConversationRow:
    values = {"vault_id": uuid4(), "user_id": uuid4(), "dweller_id": uuid4()}
    values.update(overrides)
    return ConversationRow(**values)


def _context_with_turns(count: int):
    from pydantic_ai.conversation import Conversation

    messages = []
    for index in range(count):
        messages.extend(
            (
                ModelRequest(parts=[UserPromptPart(content=f"Overseer {index}")]),
                ModelResponse(parts=[TextPart(content=f"Dweller {index}")]),
            )
        )
    return Conversation(messages=messages)


@pytest.mark.asyncio
async def test_prior_turns_reach_the_next_reply(async_session: AsyncSession) -> None:
    dweller = _dweller()
    state = _context_with_turns(2)
    thread = _thread(dweller_id=dweller.id, context=dump_context(state))

    conversation, _ = await build_continuation(async_session, thread=thread, dweller=dweller)

    assert len(conversation.messages) == 4
    assert conversation.conversation_id == state.conversation_id
    assert conversation.messages[0].parts[0].content == "Overseer 0"


@pytest.mark.asyncio
async def test_summary_and_memories_are_injected(async_session: AsyncSession) -> None:
    dweller = _dweller()
    async_session.add(DwellerMemory(dweller_id=dweller.id, fact="I am afraid of the dark.", fact_hash="h" * 64))
    await async_session.commit()
    thread = _thread(
        dweller_id=dweller.id,
        context=dump_context(_context_with_turns(1)),
        summary="Ana asked about the water purifier and was promised a repair.",
    )

    _, instructions = await build_continuation(async_session, thread=thread, dweller=dweller)

    assert "Ana asked about the water purifier" in instructions
    assert "I am afraid of the dark." in instructions


@pytest.mark.asyncio
async def test_long_thread_is_trimmed_but_keeps_the_newest_turn(async_session: AsyncSession) -> None:
    dweller = _dweller()
    state = _context_with_turns(30)
    thread = _thread(dweller_id=dweller.id, context=dump_context(state))

    conversation, _ = await build_continuation(async_session, thread=thread, dweller=dweller)

    assert len(conversation.messages) < len(state.messages)
    newest = state.messages[-1]
    assert conversation.messages[-1].parts[0].content == newest.parts[0].content
    # Trimming must not reset the usage accounting or the identity of the thread.
    assert conversation.conversation_id == state.conversation_id


@pytest.mark.asyncio
async def test_corrupt_state_degrades_to_stateless(async_session: AsyncSession) -> None:
    dweller = _dweller()
    thread = _thread(dweller_id=dweller.id, context={"not": "a conversation"})

    conversation, instructions = await build_continuation(async_session, thread=thread, dweller=dweller)

    assert conversation.messages == []
    # Only the gap line may survive; no summary, no memories.
    assert "remember" not in instructions.lower()


@pytest.mark.asyncio
async def test_gap_line_reports_absence_in_days(async_session: AsyncSession) -> None:
    dweller = _dweller()
    thread = _thread(
        dweller_id=dweller.id,
        context=dump_context(_context_with_turns(1)),
        last_message_at=utcnow() - timedelta(days=3),
    )

    _, instructions = await build_continuation(async_session, thread=thread, dweller=dweller)

    assert "It has been 3 days since the Overseer last spoke to you." in instructions


@pytest.mark.asyncio
async def test_save_context_round_trips(async_session: AsyncSession) -> None:
    thread = _thread()
    async_session.add(thread)
    await async_session.commit()
    state = _context_with_turns(1)

    await save_context(async_session, thread, state=dump_context(state))
    await async_session.commit()
    await async_session.refresh(thread)

    assert len(load_context(thread.context).messages) == 2
