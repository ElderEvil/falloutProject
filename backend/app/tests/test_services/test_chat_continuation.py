from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import patch
from uuid import uuid4

import pytest
from pydantic_ai.conversation import Conversation
from pydantic_ai.messages import ModelRequest, ModelResponse, TextPart, ToolReturnPart, UserPromptPart
from sqlmodel.ext.asyncio.session import AsyncSession

from app.crud.chat_message import chat_message as chat_message_crud
from app.models.chat_message import ChatMessage, ChatMessageCreate
from app.models.conversation import Conversation as ConversationRow
from app.models.dweller import Dweller
from app.models.dweller_memory import DwellerMemory
from app.models.vault import Vault
from app.services.chat.context import dump_context, load_context
from app.services.chat.continuation import after_exchange, build_continuation, save_context
from app.utils.time import utcnow


def _dweller() -> SimpleNamespace:
    return SimpleNamespace(id=uuid4(), first_name="Ana", bio=None, vault=SimpleNamespace(id=uuid4()))


def _thread(**overrides) -> ConversationRow:
    values = {"vault_id": uuid4(), "user_id": uuid4(), "dweller_id": uuid4()}
    values.update(overrides)
    return ConversationRow(**values)


def _context_with_turns(count: int) -> Conversation:
    messages = []
    for index in range(count):
        messages.extend(
            (
                ModelRequest(parts=[UserPromptPart(content=f"Overseer {index}")]),
                ModelResponse(parts=[TextPart(content=f"Dweller {index}")]),
            )
        )
    return Conversation(messages=messages)


async def test_prior_turns_reach_the_next_reply(async_session):
    dweller = _dweller()
    state = _context_with_turns(2)
    thread = _thread(dweller_id=dweller.id, context=dump_context(state))
    conversation, _ = await build_continuation(async_session, thread=thread, dweller=dweller)
    assert len(conversation.messages) == 4
    assert conversation.conversation_id == state.conversation_id
    assert conversation.messages[0].parts[0].content == "Overseer 0"


async def test_summary_and_memories_are_injected(async_session):
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


async def test_long_thread_is_trimmed_but_keeps_the_newest_turn(async_session):
    dweller = _dweller()
    state = _context_with_turns(30)
    thread = _thread(dweller_id=dweller.id, context=dump_context(state))
    conversation, _ = await build_continuation(async_session, thread=thread, dweller=dweller)
    assert len(conversation.messages) < len(state.messages)
    assert conversation.messages[-1].parts[0].content == state.messages[-1].parts[0].content
    # Trimming must not reset the usage accounting or the identity of the thread.
    assert conversation.conversation_id == state.conversation_id


async def test_corrupt_state_degrades_to_stateless(async_session):
    dweller = _dweller()
    thread = _thread(dweller_id=dweller.id, context={"not": "a conversation"})
    conversation, instructions = await build_continuation(async_session, thread=thread, dweller=dweller)
    assert conversation.messages == []
    # Only the gap line may survive; no summary, no memories.
    assert "remember" not in instructions.lower()


async def test_gap_line_reports_absence_in_days(async_session):
    dweller = _dweller()
    thread = _thread(
        dweller_id=dweller.id,
        context=dump_context(_context_with_turns(1)),
        last_message_at=utcnow() - timedelta(days=3),
    )
    _, instructions = await build_continuation(async_session, thread=thread, dweller=dweller)
    assert "It has been 3 days since the Overseer last spoke to you." in instructions


async def _thread_with_rows(
    session: AsyncSession, vault: Vault, dweller: Dweller, exchanges: int, carried: int
) -> tuple[ConversationRow, list[ChatMessage]]:
    """A persisted thread holding ``exchanges`` exchanged pairs, its state trimmed to ``carried``."""
    await session.refresh(vault, ["user"])
    thread = ConversationRow(vault_id=vault.id, user_id=vault.user.id, dweller_id=dweller.id)
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    rows: list[ChatMessage] = []
    for index in range(exchanges):
        question = ChatMessageCreate(
            vault_id=vault.id,
            from_user_id=vault.user.id,
            to_dweller_id=dweller.id,
            message_text=f"Question {index}",
            conversation_id=thread.id,
        )
        answer = ChatMessageCreate(
            vault_id=vault.id,
            from_dweller_id=dweller.id,
            to_user_id=vault.user.id,
            message_text=f"Answer {index}",
            conversation_id=thread.id,
        )
        rows.extend(
            [
                await chat_message_crud.create_message(session, obj_in=question),
                await chat_message_crud.create_message(session, obj_in=answer),
            ]
        )
    await session.commit()
    thread.context = dump_context(_context_with_turns(carried // 2))
    session.add(thread)
    await session.commit()
    await session.refresh(thread)
    return thread, rows


async def _run_after_exchange(
    session: AsyncSession,
    thread: ConversationRow,
    dweller: Dweller,
    *,
    summarised: list[ChatMessage] | None = None,
    seen: list[ChatMessage] | None = None,
) -> None:
    """Run the upkeep with both model calls stubbed, recording what each was handed."""
    summary_sink = summarised if summarised is not None else []
    seen_sink = seen if seen is not None else []

    async def on_summarise(_db, _thread, *, dropped):
        summary_sink.extend(dropped)

    async def on_extract(_db, *, dweller, exchange, existing):
        seen_sink.extend(exchange)
        return []

    with (
        patch("app.services.chat.continuation.maybe_summarize", new=on_summarise),
        patch("app.services.chat.continuation.extract_memories", new=on_extract),
    ):
        await after_exchange(session, thread=thread, dweller=dweller)


async def test_after_exchange_ages_rows_the_next_window_will_not_carry(async_session, vault, dweller):
    """The stored state holds the exchange just made plus a tool-return request, so it is longer
    than the rows it covers. Measuring it raw left nothing aged and summarisation never ran
    against a real run (issue #1462)."""
    thread, rows = await _thread_with_rows(async_session, vault, dweller, exchanges=7, carried=14)
    state = _context_with_turns(7)
    state.messages.append(
        ModelRequest(parts=[ToolReturnPart(tool_name="final_result", content="done", tool_call_id="call_1")])
    )
    thread.context = dump_context(state)
    async_session.add(thread)
    await async_session.commit()
    summarised: list[ChatMessage] = []
    await _run_after_exchange(async_session, thread, dweller, summarised=summarised)
    # 14 rows, a 12-message window that spends one message on the tool return and refuses to
    # split a turn: ten rows stay in the prompt, four are aged.
    assert [row.id for row in summarised] == [row.id for row in rows[:4]]


async def test_after_exchange_summarises_exactly_the_rows_the_window_dropped(async_session, vault, dweller):
    """The summary must cover what left the prompt, not a count guessed from config."""
    thread, rows = await _thread_with_rows(async_session, vault, dweller, exchanges=4, carried=4)
    summarised: list[ChatMessage] = []
    await _run_after_exchange(async_session, thread, dweller, summarised=summarised)
    assert [row.id for row in summarised] == [row.id for row in rows[:4]]


async def test_after_exchange_summarises_budget_trimmed_turns_too(async_session, vault, dweller):
    """A token budget can carry fewer messages than the count limit; those are not lost."""
    thread, rows = await _thread_with_rows(async_session, vault, dweller, exchanges=4, carried=2)
    summarised: list[ChatMessage] = []
    await _run_after_exchange(async_session, thread, dweller, summarised=summarised)
    assert [row.id for row in summarised] == [row.id for row in rows[:6]]


async def test_after_exchange_gives_memory_extraction_both_halves(async_session, vault, dweller):
    thread, _rows = await _thread_with_rows(async_session, vault, dweller, exchanges=2, carried=4)
    seen: list[ChatMessage] = []
    await _run_after_exchange(async_session, thread, dweller, seen=seen)
    assert [row.message_text for row in seen] == ["Question 1", "Answer 1"]


async def test_save_context_round_trips(async_session):
    thread = _thread()
    async_session.add(thread)
    await async_session.commit()
    state = _context_with_turns(1)
    await save_context(async_session, thread, state=dump_context(state))
    await async_session.commit()
    await async_session.refresh(thread)
    assert len(load_context(thread.context).messages) == 2
