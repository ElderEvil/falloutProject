# Chat continuation + dweller awareness — Implementation Plan

> **For Hermes:** Use subagent-driven-development skill to implement this plan task-by-task.

**Goal:** Make dweller chat remember a conversation across days, carry durable firsthand facts about itself, and notice what changed in the vault since you last spoke.

**Architecture:** One `Conversation` row per (user, dweller) pair — never split, because continuity across days is the point. Continuation = the serialised pydantic-ai `Conversation` (messages + usage) stored as JSONB, trimmed to a rolling window, with a `summary` covering everything pruned out. Memory = a `DwellerMemory` table filled by one automatic extraction call per exchange, deduped by hash, capped per dweller. Awareness = a digest assembled from `IncidentEvent` + vault deltas since the last message.

**Tech Stack:** FastAPI, SQLModel/SQLAlchemy async, Alembic (`baseline_versions` chain), pydantic-ai (`ModelMessage`, `ModelRequest`, `ModelResponse`), pytest async fixtures.

**Decisions taken (from maintainer):** cross-day continuation required → single permanent thread plus summaries; memory automatic (no player confirmation); token cost is not a constraint.

---

## Ground rules for the implementer

- Work on one branch, `feat/chat-continuation`, one accumulating PR. Commit after every task.
- Never touch `app/services/vault_layout_backfill_service.py`, `app/utils/partial.py`, `app/cli/ops.py` or `app/core/logging.py` — they carry pre-existing `ty` errors that any edit turns red (#1452). If a change seems to need them, stop and report.
- Every history/memory/awareness failure path must degrade to **today's stateless behaviour**, never to an error.
- Run `pytest app/tests -q -n auto` before each push; the only acceptable failure is `test_ci_hook_scope` (`prek` missing locally).
- Push only outside 00:00–06:00 local unless told otherwise.

---

### Task 1: Add `ChatConfig`

**Objective:** Centralise the three tunables so tests can shrink the window.

**Files:**
- Modify: `backend/app/core/game_config.py` (add class before `GameConfig`, register field near line 1261)

**Step 1: Write the config class**

```python
class ChatConfig(BaseSettings):
    """Conversation continuity, summary and memory bounds."""

    history_messages: int = 12
    history_token_budget: int = 1500
    summary_trigger_messages: int = 20
    summary_max_chars: int = 900
    memory_max_per_dweller: int = 20
    memory_prompt_limit: int = 12
    awareness_max_lines: int = 8
```

**Step 2: Register on `GameConfig`**

```python
    chat: ChatConfig = Field(default_factory=ChatConfig)
```

**Step 3: Verify**

Run: `cd backend && .venv/bin/python -c "from app.core.game_config import game_config; print(game_config.chat.history_messages)"`
Expected: `12`

**Step 4: Commit** `feat(chat): add chat config for continuity bounds`

---

### Task 2: `Conversation` model

**Objective:** A durable thread per (user, dweller).

**Files:**
- Create: `backend/app/models/conversation.py`
- Modify: `backend/app/models/__init__.py` (export)

**Step 1: Write the model**

```python
from datetime import datetime
from uuid import UUID, uuid7

import sqlalchemy as sa
from sqlmodel import Field, SQLModel

from app.models.base import BaseUUIDModel, TimeStampMixin
from app.utils.time import utcnow
from app.utils.types import UTCDateTime


class ConversationBase(SQLModel):
    vault_id: UUID = Field(foreign_key="vault.id", index=True)
    user_id: UUID = Field(foreign_key="user.id", index=True, ondelete="CASCADE")
    dweller_id: UUID = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")
    summary: str | None = Field(default=None, sa_column=sa.Column(sa.Text, nullable=True))
    summary_through_message_id: UUID | None = Field(default=None, foreign_key="chatmessage.id")


class Conversation(BaseUUIDModel, ConversationBase, TimeStampMixin, table=True):
    """The single continuous thread between one user and one dweller."""

    __tablename__ = "conversation"
    __table_args__ = (
        sa.UniqueConstraint("user_id", "dweller_id", name="uq_conversation_user_dweller"),
    )

    last_message_at: datetime | None = Field(default=None, sa_type=UTCDateTime, index=True)
    message_count: int = Field(default=0, ge=0)

    #: Serialised pydantic-ai ``Conversation`` (messages + usage + id): the model-facing thread.
    context: dict | None = Field(default=None, sa_column=sa.Column(JSONB))
```

**Note:** check the actual `chatmessage` table name in `app/models/chat_message.py` before writing the FK — if `__tablename__` is unset, SQLModel derives `chatmessage`; verify with `BaseUUIDModel.__tablename__` behaviour rather than assuming.

**Step 2: Test**

`backend/app/tests/test_models/test_conversation.py` — create a conversation with factory fixtures, assert `uuid7()` id, assert the unique constraint rejects a duplicate pair.

**Step 3: Verify** `pytest app/tests/test_models/test_conversation.py -v` → PASS

**Step 4: Commit** `feat(chat): add Conversation model`

---

### Task 3: Migration for thread + message link + memory table

**Objective:** One revision adding both new tables and `chatmessage.conversation_id`.

**Files:**
- Create: `backend/app/alembic/baseline_versions/2026_11_21_0001-<hash>_chat_continuity.py` (generate the hash with the repo's baseline tool or `alembic revision`)

**Step 1: Write the migration**

```python
revision = "<hash>"
down_revision = "9a73f29c2ed1"
```

`upgrade()`:
1. `op.create_table("conversation", ...)` — id, vault_id, user_id, dweller_id, summary, summary_through_message_id, last_message_at, message_count, **context (JSONB, nullable)**, created_at, updated_at; unique constraint; indexes on vault_id/user_id/dweller_id/last_message_at.
2. `op.add_column("chatmessage", sa.Column("conversation_id", sa.UUID(), nullable=True))` + index.
3. `op.create_table("dweller_memory", ...)` — id, dweller_id (FK cascade), fact (Text), fact_hash (String 64), source_message_id (FK chatmessage, nullable), created_at, updated_at; unique constraint on (dweller_id, fact_hash); index on dweller_id.

`downgrade()` reverses in order.

**Step 2: Backfill in the same revision**

For every distinct `(from_user_id/to_user_id, dweller)` pair in `chatmessage`, create a `conversation`, then `UPDATE chatmessage SET conversation_id = ...`. Set `last_message_at` and `message_count` from the rows. Use one `SELECT` + batched insert, not per-row queries.

**Step 3: Verify against a scratch database**

Run: `cd backend && .venv/bin/alembic upgrade head` then `alembic downgrade -1` then `upgrade head` again.
Expected: no error; `chatmessage` has `conversation_id`; backfilled conversation count equals the distinct pair count.

**Step 4: Commit** `feat(chat): migrate to conversations and dweller memory`

---

### Task 4: `ChatMessage.conversation_id` on the model

**Files:**
- Modify: `backend/app/models/chat_message.py:19-41`

**Step 1:** Add

```python
    conversation_id: UUID | None = Field(default=None, foreign_key="conversation.id", index=True)
```

**Step 2:** Run `pytest app/tests/test_services/test_chat_service.py app/tests/test_api/test_chat.py -q` → PASS (writes still work without the FK set during this task).

**Step 3: Commit** `feat(chat): link messages to conversations`

---

### Task 5: Conversation CRUD + lazy creation

**Objective:** Every write path gets a thread without the caller thinking about it.

**Files:**
- Create: `backend/app/crud/conversation.py`
- Modify: `backend/app/crud/__init__.py`
- Modify: `backend/app/services/chat/persistence.py`

**Step 1: CRUD**

```python
class CRUDConversation(CRUDBase[Conversation, ConversationBase, ConversationBase]):
    async def get_or_create(self, db: AsyncSession, *, vault_id: UUID, user_id: UUID,
                            dweller_id: UUID) -> Conversation
    async def touch(self, db: AsyncSession, conversation: Conversation, *,
                    at: datetime, message_count: int | None = None) -> Conversation
```

`get_or_create` must be race-safe: `select` first, on miss `insert` and catch `IntegrityError`, then re-select.

**Step 2: Wire into persistence** — when a `ChatMessage` is created, set `conversation_id` and `touch()` the row in the same transaction.

**Step 3: Test** — two concurrent `get_or_create` calls yield one row; message creation bumps `message_count` and `last_message_at`.

**Step 4: Verify** `pytest app/tests/test_crud/test_conversation.py app/tests/test_services/test_chat_service.py -q` → PASS

**Step 5: Commit** `feat(chat): thread messages through a conversation`

---

### Task 6: Conversation state (use pydantic-ai's own `Conversation`)

**Objective:** Persist and continue the model-facing thread in the library's native format.

**Why:** this pydantic-ai version exposes `pydantic_ai.conversation.Conversation` — messages **plus**
running usage, `conversation_id` and deferred tool requests — serialisable via
`ConversationTypeAdapter`, and `Agent.run(..., conversation=conv)` accepts it back.
`AgentRunResult.conversation` returns the updated object. Rebuilding `ModelMessage`s by hand from
`ChatMessage` rows would drop usage continuity and duplicate a solved problem. Verified by
round-trip: `ConversationTypeAdapter.dump_json` → `validate_json` preserves messages and usage.

**Files:**
- Create: `backend/app/services/chat/context.py`
- Test: `backend/app/tests/test_services/test_chat_context.py`

**Step 1: Helpers**

```python
def load_context(raw: dict | None) -> Conversation:
    """Deserialise the stored state; a missing/corrupt value starts a fresh conversation."""

def dump_context(conversation: Conversation) -> dict:
    return json.loads(ConversationTypeAdapter.dump_json(conversation))

def plan_prune(conversation: Conversation, *, keep: int, budget: int) -> tuple[list[ModelMessage], Conversation]:
    """Split off the oldest messages that no longer fit; return (dropped, trimmed copy)."""
```

`plan_prune` rules: never drop the newest message; drop from the front until both `keep` and the
`len(content) // 4` budget hold; keep `usage`, `conversation_id`, `deferred_tool_requests` intact on
the trimmed copy.

**Step 2: Tests** — fresh state on `None`; corrupt JSON degrades to fresh; prune keeps the newest
turn and respects both limits; pruning preserves `conversation_id` and usage.

**Step 3: Verify** `pytest app/tests/test_services/test_chat_context.py -q` → PASS

**Step 4: Commit** `feat(chat): persist pydantic-ai conversation state`

---

### Task 7: Summary service

**Objective:** Keep long threads affordable without losing the early thread.

**Files:**
- Create: `backend/app/services/chat/summary.py`
- Test: `backend/app/tests/test_services/test_chat_summary.py`

**Step 1: Logic (test with a fake model, no provider call)**

```python
async def maybe_summarize(db, conversation, *, model=None) -> Conversation:
    """Rewrite the summary when unsummarised messages exceed the trigger."""
```

- Input is the oldest messages that `plan_prune` is about to drop (Task 6), not a raw row count —
  a summary must always be written **before** its source messages leave the context.
- Nothing to drop (`dropped == []`): return unchanged.
- Otherwise: prompt = existing summary + the unsummarised rows (**no model needed for the count test**; pass a stub callable in tests).
- Prompt contract: rewrite in ≤ `summary_max_chars`, third person, keep names, promises, losses and unresolved threads; drop pleasantries.
- Store `summary` and `summary_through_message_id` = newest summarised row id.

**Step 2: Trigger point** — after the reply is persisted, as a fire-and-forget task; a failure must log and leave the summary untouched.

**Step 3: Verify** `pytest app/tests/test_services/test_chat_summary.py -q` → PASS

**Step 4: Commit** `feat(chat): summarise long conversations`

---

### Task 8: `DwellerMemory` model + migration follow-up

If Task 3 already created the table, this task only adds the SQLModel class.

**Files:**
- Create: `backend/app/models/dweller_memory.py`
- Modify: `backend/app/models/__init__.py`

```python
class DwellerMemory(BaseUUIDModel, TimeStampMixin, table=True):
    """One durable first-person fact a dweller knows about itself."""

    __tablename__ = "dweller_memory"
    __table_args__ = (sa.UniqueConstraint("dweller_id", "fact_hash", name="uq_memory_fact"),)

    dweller_id: UUID = Field(foreign_key="dweller.id", index=True, ondelete="CASCADE")
    fact: str = Field(sa_column=sa.Column(sa.Text, nullable=False))
    fact_hash: str = Field(max_length=64, index=True)
    source_message_id: UUID | None = Field(default=None, foreign_key="chatmessage.id")
    last_used_at: datetime | None = Field(default=None, sa_type=UTCDateTime)
```

**Test:** duplicate `(dweller_id, fact_hash)` raises; cascade delete removes memories with the dweller.
**Commit** `feat(chat): add dweller memory model`

---

### Task 9: Automatic memory extraction

**Objective:** Turn each exchange into zero or more facts, without asking the player.

**Files:**
- Create: `backend/app/services/chat/memory.py`
- Test: `backend/app/tests/test_services/test_chat_memory.py`

**Step 1: Contract**

```python
async def extract_memories(db, *, dweller, exchange: Sequence[ChatMessage],
                           existing: Sequence[DwellerMemory], model=None) -> list[DwellerMemory]:
```

- One structured call: input = the two exchanged messages + existing facts (as "already known, do not repeat").
- Output: `list[MemoryCandidate]` where `MemoryCandidate` has `fact: str` (≤240 chars, first person) and `kind: Literal["habit","fear","keepsake","promise","event","relationship"]`.
- Reject non-first-person, restatements of `dweller.bio`, and anything longer than 240 chars (existing `bio_addendum` rules, `chat_tools.py:401-407`).
- `fact_hash = sha256(normalised fact)` where normalised = casefolded, whitespace-collapsed, punctuation-stripped; insert with `ON CONFLICT DO NOTHING` semantics (catch `IntegrityError`).
- Evict when count > `memory_max_per_dweller`: delete oldest `last_used_at` (nulls first).

**Step 2: Hook** — after persistence in both text and voice paths; failures log only.

**Step 3: Test** — dedupe by hash, cap enforcement, rejection of a bio restatement, and that a model failure returns `[]` without raising.

**Step 4: Commit** `feat(chat): extract dweller memories automatically`

---

### Task 10: Awareness digest

**Files:**
- Create: `backend/app/services/chat/awareness.py`
- Test: `backend/app/tests/test_services/test_chat_awareness.py`

**Step 1: Query + format**

```python
async def build_awareness_digest(db, *, vault_id: UUID, since: datetime | None,
                                 max_lines: int) -> list[str]:
```

Sources, in this order: incidents with `IncidentEvent.created_at > since` for the vault; vault resource deltas (food/water/power current vs. a stored previous snapshot — if no snapshot exists, skip rather than invent); dwellers added or deceased since `since`.

Rules: one line each, ≤90 chars, factual past tense, no numbers that were not measured; cap at `max_lines`; `since is None` → return `[]` (first ever conversation has nothing to catch up on).

**Step 2: Test** — empty digest when `since is None`; incident line appears once; cap respected.

**Step 3: Commit** `feat(chat): build a since-last-conversation digest`

---

### Task 11: Wire it all into `run_chat_agent`

**Files:**
- Modify: `backend/app/services/chat/agent_runner.py:103-140`
- Modify: `backend/app/agents/chat_prompts.py:131` (accept `summary`, `memories`, `digest`, `last_seen`)

**Step 1:** Load, in order — conversation row, `context` (Task 6), summary, memories, digest. Any
exception → log and run with a fresh `Conversation()` (exactly today's stateless behaviour).

**Step 2:** If `plan_prune` drops messages, summarise them **first** (Task 7), then run with the
trimmed conversation.

**Step 3:** `result = await dweller_chat_agent.run(message_text, conversation=ctx, deps=..., instructions=..., usage_limits=...)`,
then persist `dump_context(result.conversation)` onto the conversation row in the caller's
transaction. `conversation=` — not `message_history=` — so usage limits and `conversation_id`
survive the turn.

**Step 4:** Extend instructions with three optional blocks:

```
What you remember about yourself: <fact>; <fact>; ...
Earlier in this conversation: <summary>
Since you last spoke to the Overseer (<n> days ago): <digest lines>
```

**Step 5: Test** — a fake model captures the conversation it receives and the instruction text;
assert prior messages are present, the summary block appears once, and a forced exception during
context loading still produces a reply (fresh conversation, no 500).

**Step 6: Verify** `pytest app/tests/test_services/test_chat_service.py app/tests/test_agents/ -q` → PASS

**Step 7: Commit** `feat(chat): continue conversations through pydantic-ai state`

---

### Task 12: Post-exchange hooks

**Files:**
- Modify: `backend/app/services/chat_service.py:117`
- Modify: `backend/app/services/conversation_service.py:170`

`extract_memories(...)` runs after persistence, off the user-visible path (own session, failure
logged only). Summarisation is **not** asynchronous any more — it happens inline in Task 11, and
only when the context actually overflowed, because a summary must exist before its source messages
are dropped.

**Verify:** a text exchange produces exactly one conversation, a bumped `message_count`, and (with a stub model) at least one memory row.
**Commit** `feat(chat): summarise and extract after each exchange`

---

### Task 13: API surface

**Files:**
- Modify: `backend/app/api/v1/endpoints/chat.py`
- Modify: `backend/app/services/chat_service.py:277`

**Step 1:** `GET /chat/history/{dweller_id}` gains optional `conversation_id` and returns `conversation_id` + `summary` on a new `ChatHistoryResponse` (keep the list shape for compatibility, or version the endpoint — decide from frontend usage).

**Step 2:** `GET /chat/conversations` — list threads for the user's vault with `dweller_id`, `last_message_at`, `message_count`, `summary`.

**Step 3: Test** — history returns the conversation id; a second fetch is stable; unauthenticated access is rejected.

**Step 4: Commit** `feat(chat): expose conversation threads`

---

### Task 14: Full verification and docs

**Step 1:** `pytest app/tests -q -n auto` → expect all pass except `test_ci_hook_scope`.
**Step 2:** `ruff check app && ruff format --check app` → clean.
**Step 3:** `ty check` on every changed module **except the four excluded files** → 0 errors.
**Step 4:** Live two-turn playtest: seed a vault, chat twice across a simulated day gap, confirm the second reply references the first turn and the digest. Record the real `LLMInteraction.prompt_tokens` for both turns in the PR body.
**Step 5:** Update `docs/features/CHAT_CONTINUATION_AND_AWARENESS_RESEARCH.md` status line to "implemented in #<PR>" and note any deviation from this plan.
**Step 6: Commit** `docs(chat): record continuity implementation`

---

## Acceptance criteria

- Second message in a thread references the first — verified by a stub-model unit test **and** one live exchange.
- A conversation survives a simulated 3-day gap: history + summary still produce a coherent reply, and the instructions contain a "since you last spoke" line.
- Memories are automatic, deduped, capped at 20 per dweller, and never restate the bio.
- Every new failure path degrades to the previous stateless behaviour; no new 500s.
- No new `ty` errors; the four debt modules remain untouched.

## Risks

| Risk | Mitigation |
|---|---|
| Continued context makes the model re-answer the previous question | time-gap line + "the last message was X ago" marker; test with a 3-day gap |
| Pruning drops unsummarised turns | `plan_prune` runs before the summary call; a test asserts every dropped message is covered by `summary_through_message_id` |
| Memory drifts into inventing canon | extraction is restricted to what the exchange states; bio restatements rejected; 20-fact cap keeps it honest |
| Summaries lose names/promises | explicit prompt contract; a test asserting names appear in the summary output |
| Backfill creates a conversation per stray row | backfill groups by pair; assert count == distinct pairs |
| Background hooks running on a closed session | own session per hook; `asyncio.shield`; failure logged only |
