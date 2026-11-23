"""Automatic dweller memory extraction: bounded, deduped, capped, never raising."""

from collections.abc import Sequence

import pytest
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.chat_message import chat_message as chat_message_crud
from app.models.chat_message import ChatMessage, ChatMessageCreate
from app.models.dweller import Dweller
from app.models.dweller_memory import DwellerMemory
from app.models.vault import Vault
from app.services.chat.memory import (
    MemoryCandidate,
    MemoryExtractionRequest,
    extract_memories,
    fact_hash,
    normalise_fact,
)
from app.utils.time import utcnow

BIO = "Nora grew up in Vault 101 and repairs pipes."


async def _exchange(async_session: AsyncSession, vault: Vault, dweller: Dweller) -> list[ChatMessage]:
    await async_session.refresh(vault, ["user"])
    question = await chat_message_crud.create_message(
        async_session,
        obj_in=ChatMessageCreate(
            vault_id=vault.id, from_user_id=vault.user.id, to_dweller_id=dweller.id, message_text="Anything you miss?"
        ),
    )
    answer = await chat_message_crud.create_message(
        async_session,
        obj_in=ChatMessageCreate(
            vault_id=vault.id,
            from_dweller_id=dweller.id,
            to_user_id=vault.user.id,
            message_text="I keep a lucky wrench under my bunk. I slept through the alarms last week.",
        ),
    )
    return [question, answer]


def _stub(candidates: Sequence[MemoryCandidate], calls: list[MemoryExtractionRequest]):
    async def stub(request: MemoryExtractionRequest) -> Sequence[MemoryCandidate]:
        calls.append(request)
        return candidates

    return stub


def _facts(*facts: str):
    return _stub([MemoryCandidate(fact=fact) for fact in facts], [])


async def _rows(async_session: AsyncSession) -> list[DwellerMemory]:
    return (await async_session.exec(select(DwellerMemory))).all()


async def test_extracts_and_persists_stated_facts(async_session, vault, dweller):
    exchange = await _exchange(async_session, vault, dweller)
    calls: list[MemoryExtractionRequest] = []
    candidates = [
        MemoryCandidate(fact="I keep a lucky wrench under my bunk."),
        MemoryCandidate(fact="I slept through the alarms last week."),
    ]
    stored = await extract_memories(async_session, dweller=dweller, exchange=exchange, model=_stub(candidates, calls))
    assert [memory.fact for memory in stored] == [candidate.fact for candidate in candidates]
    assert all(memory.dweller_id == dweller.id for memory in stored)
    assert all(memory.source_message_id == exchange[-1].id for memory in stored)
    assert stored[0].fact_hash == fact_hash("I keep a lucky wrench under my bunk.")
    assert len(calls) == 1
    assert calls[0].exchange == tuple(message.message_text for message in exchange)
    assert len(await _rows(async_session)) == 2


async def test_dedupes_within_one_exchange_and_against_existing(async_session, vault, dweller):
    exchange = await _exchange(async_session, vault, dweller)
    existing = DwellerMemory(dweller_id=dweller.id, fact="I fear the dark.", fact_hash=fact_hash("I fear the dark."))
    async_session.add(existing)
    await async_session.flush()
    stored = await extract_memories(
        async_session,
        dweller=dweller,
        exchange=exchange,
        existing=[existing],
        model=_facts(
            "I fear the dark!",
            "i   FEAR the dark",
            "I keep a lucky wrench under my bunk.",
            "I keep a lucky wrench under my bunk",
        ),
    )
    assert [memory.fact for memory in stored] == ["I keep a lucky wrench under my bunk."]
    assert len(await _rows(async_session)) == 2


async def test_dedupe_is_whitespace_case_and_punctuation_insensitive():
    assert normalise_fact("  I   fear the DARK!  ") == "i fear the dark"
    assert fact_hash("I fear the dark") == fact_hash("i FEAR the dark...")


async def test_evicts_oldest_memories_beyond_the_cap(async_session, vault, dweller, monkeypatch):
    monkeypatch.setattr(game_config.chat, "memory_max_per_dweller", 2)
    exchange = await _exchange(async_session, vault, dweller)
    for index, fact in enumerate(["I hoard bottle caps.", "I hate radroaches."]):
        async_session.add(
            DwellerMemory(
                dweller_id=dweller.id,
                fact=fact,
                fact_hash=fact_hash(fact),
                created_at=utcnow().replace(year=2020 + index),
            )
        )
    await async_session.commit()
    stored = await extract_memories(
        async_session, dweller=dweller, exchange=exchange, model=_facts("I keep a lucky wrench under my bunk.")
    )
    facts = sorted(memory.fact for memory in await _rows(async_session))
    assert facts == ["I hate radroaches.", "I keep a lucky wrench under my bunk."]
    assert [memory.fact for memory in stored] == ["I keep a lucky wrench under my bunk."]


async def test_rejects_bio_restatements_and_non_first_person_facts(async_session, vault, dweller):
    dweller.bio = BIO
    async_session.add(dweller)
    await async_session.flush()
    exchange = await _exchange(async_session, vault, dweller)
    stored = await extract_memories(
        async_session,
        dweller=dweller,
        exchange=exchange,
        model=_facts(
            "Nora grew up in Vault 101 and repairs pipes.",
            "Nora keeps a lucky wrench under her bunk.",
            "She fears the dark.",
            "I " + "really " * 40 + "mean it.",
            "I fear the dark.",
        ),
    )
    assert [memory.fact for memory in stored] == ["I fear the dark."]


async def test_model_failure_returns_empty_list(async_session, vault, dweller, caplog):
    exchange = await _exchange(async_session, vault, dweller)

    async def broken(_: MemoryExtractionRequest) -> Sequence[MemoryCandidate]:
        raise RuntimeError("provider exploded")

    stored = await extract_memories(async_session, dweller=dweller, exchange=exchange, model=broken)
    assert stored == []
    assert await _rows(async_session) == []
    assert "provider exploded" in caplog.text


async def test_unique_violation_is_a_skip_not_an_error(async_session, vault, dweller):
    """A row inserted after the hash read races the insert; it must be skipped quietly."""
    exchange = await _exchange(async_session, vault, dweller)

    async def racing(_: MemoryExtractionRequest) -> Sequence[MemoryCandidate]:
        async_session.add(
            DwellerMemory(dweller_id=dweller.id, fact="I fear the dark.", fact_hash=fact_hash("I fear the dark."))
        )
        await async_session.flush()
        return [MemoryCandidate(fact="I fear the dark!")]

    stored = await extract_memories(async_session, dweller=dweller, exchange=exchange, model=racing)
    assert stored == []
    assert len(await _rows(async_session)) == 1


async def test_no_configured_model_remembers_nothing(async_session, vault, dweller, monkeypatch):
    import app.services.chat.memory as memory_module

    monkeypatch.setattr(memory_module, "get_model", lambda: None)
    exchange = await _exchange(async_session, vault, dweller)
    assert await extract_memories(async_session, dweller=dweller, exchange=exchange) == []


async def test_empty_exchange_skips_the_model(async_session, dweller):
    calls: list[MemoryExtractionRequest] = []
    stored = await extract_memories(async_session, dweller=dweller, exchange=[], model=_stub([], calls))
    assert stored == []
    assert calls == []
