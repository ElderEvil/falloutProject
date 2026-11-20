"""Automatic dweller memory: one extraction call per exchange, bounded and deduped.

The player never confirms a memory. Bounds do the work instead: only what the exchange
states, first person, <=240 chars, never a restatement of the biography, deduped by the
normalised fact's hash, and capped per dweller. Any model failure degrades to "nothing
remembered this turn" — it never raises into the chat path.
"""

import hashlib
import logging
import re
import unicodedata
from collections.abc import Awaitable, Callable, Sequence
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from pydantic_ai import Agent
from sqlalchemy.exc import IntegrityError
from sqlmodel.ext.asyncio.session import AsyncSession

from app.core.game_config import game_config
from app.crud.dweller_memory import dweller_memory as dweller_memory_crud
from app.models.chat_message import ChatMessage
from app.models.dweller_memory import DwellerMemory
from app.schemas.chat_memory import MemoryCandidate, MemoryExtractionOutput
from app.services.ai_service import get_model

logger = logging.getLogger(__name__)

MEMORY_MIN_CHARS = 8
MEMORY_MAX_CHARS = 240


_FIRST_PERSON = re.compile(r"\bi\b|\bi['\u2019](?:m|ve|ll|d)\b|\b(?:my|me|mine|myself)\b")
_WHITESPACE = re.compile(r"\s+")

MEMORY_INSTRUCTIONS = """\
You read one exchange between the Overseer and a Vault dweller and record what the
dweller durably revealed about itself.

Rules:
- Record only facts the exchange actually states. Never infer, embellish or invent.
- Write each fact in the dweller's own first person ("I ..."), as one sentence of at
  most 240 characters.
- Never restate the biography, and never repeat an already known fact.
- Durable means a habit, fear, keepsake, promise, remembered event or relationship.
  Small talk, moods and plans for the next hour are not durable.
- Return an empty list when nothing durable was said.
"""


class DwellerLike(Protocol):
    """The slice of a dweller this module reads (model row or read schema)."""

    id: UUID
    first_name: str
    bio: str | None


@dataclass(frozen=True)
class MemoryExtractionRequest:
    """Everything the extractor may see: the exchange, and what is already known."""

    dweller_name: str
    bio: str | None
    exchange: tuple[str, ...]
    known_facts: tuple[str, ...]

    def render(self) -> str:
        lines = [f"Dweller: {self.dweller_name}"]
        if self.bio:
            lines.append(f"Biography (never repeat it): {self.bio}")
        if self.known_facts:
            lines.append("Already known, do not repeat:")
            lines.extend(f"- {fact}" for fact in self.known_facts)
        lines.append("Exchange:")
        lines.extend(self.exchange)
        return "\n".join(lines)


MemoryExtractor = Callable[[MemoryExtractionRequest], Awaitable[Sequence[MemoryCandidate]]]


def normalise_fact(fact: str) -> str:
    """Casefold, collapse whitespace, drop punctuation — the dedupe key's basis."""
    without_punctuation = "".join(char for char in fact if not unicodedata.category(char).startswith("P"))
    return _WHITESPACE.sub(" ", without_punctuation).strip().casefold()


def fact_hash(fact: str) -> str:
    return hashlib.sha256(normalise_fact(fact).encode("utf-8")).hexdigest()


def _is_first_person(fact: str) -> bool:
    spoken = _WHITESPACE.sub(" ", fact).strip().casefold()
    return _FIRST_PERSON.search(spoken) is not None


def _restates_bio(fact: str, bio: str | None) -> bool:
    if not bio:
        return False
    return normalise_fact(fact) in normalise_fact(bio)


def _admissible_fact(candidate: MemoryCandidate, *, bio: str | None, seen: set[str]) -> str | None:
    """Return the trimmed fact if it passes every bound, else None."""
    fact = _WHITESPACE.sub(" ", candidate.fact).strip()
    if not MEMORY_MIN_CHARS <= len(fact) <= MEMORY_MAX_CHARS:
        return None
    if not _is_first_person(fact):
        return None
    if _restates_bio(fact, bio):
        return None
    digest = fact_hash(fact)
    if digest in seen:
        return None
    seen.add(digest)
    return fact


async def _extract_with_model(request: MemoryExtractionRequest) -> Sequence[MemoryCandidate]:
    """Default extractor: one structured call. Returns [] when no model is configured."""
    model = get_model()
    if model is None:
        return []
    agent: Agent[None, MemoryExtractionOutput] = Agent(
        model=model,
        output_type=MemoryExtractionOutput,
        instructions=MEMORY_INSTRUCTIONS,
    )
    result = await agent.run(request.render())
    return result.output.facts


async def _persist(db: AsyncSession, *, dweller_id: UUID, fact: str, source_message_id: UUID) -> DwellerMemory | None:
    """Insert one fact; a unique-constraint race is a skip, not an error."""
    memory = DwellerMemory(
        dweller_id=dweller_id,
        fact=fact,
        fact_hash=fact_hash(fact),
        source_message_id=source_message_id,
    )
    try:
        async with db.begin_nested():
            db.add(memory)
            await db.flush()
    except IntegrityError:
        logger.debug("Dweller %s already remembers: %s", dweller_id, fact)
        return None
    return memory


async def extract_memories(
    db: AsyncSession,
    *,
    dweller: DwellerLike,
    exchange: Sequence[ChatMessage],
    existing: Sequence[DwellerMemory] = (),
    model: MemoryExtractor | None = None,
) -> list[DwellerMemory]:
    """Record what this exchange durably revealed about the dweller.

    The caller owns the transaction: this flushes, it never commits. A model failure
    returns [] so the exchange itself is unaffected.
    """
    messages = [message for message in exchange if message.message_text.strip()]
    if not messages:
        return []

    # Read before the model runs so a duplicate arriving mid-flight is caught at insert.
    known = await dweller_memory_crud.hashes_for(db, dweller_id=dweller.id)
    request = MemoryExtractionRequest(
        dweller_name=dweller.first_name,
        bio=dweller.bio,
        exchange=tuple(message.message_text.strip() for message in messages),
        known_facts=tuple(memory.fact for memory in existing),
    )
    extractor = model or _extract_with_model
    try:
        candidates = await extractor(request)
    except Exception:
        logger.warning("Dweller memory extraction failed for dweller %s", dweller.id, exc_info=True)
        return []

    seen = set(known)
    source_message_id = messages[-1].id
    stored: list[DwellerMemory] = []
    for candidate in candidates:
        fact = _admissible_fact(candidate, bio=dweller.bio, seen=seen)
        if fact is None:
            continue
        memory = await _persist(db, dweller_id=dweller.id, fact=fact, source_message_id=source_message_id)
        if memory is not None:
            stored.append(memory)

    if stored:
        await dweller_memory_crud.trim_to_cap(
            db, dweller_id=dweller.id, cap=game_config.chat.memory_max_per_dweller
        )
    return stored
