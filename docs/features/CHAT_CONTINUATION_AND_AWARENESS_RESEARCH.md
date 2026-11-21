# Chat continuation and dweller awareness — research

Status: implemented (branch `feat/chat-continuation`, plan in
`docs/plans/2026-11-20-chat-continuation-and-awareness.md`). Source baseline: local `master` @
`fda7fdda3`. Decisions taken from this report: one permanent thread per (user, dweller) — no
session splitting, because continuity across days is the goal; memory extraction automatic with
hash dedupe, bio-restatement rejection and a 20-fact cap; token cost accepted.
Product investigation only — no schema, prompt or route change is approved by this report.
Runtime journeys were not exercised; everything below is read from source.

## The short version

Chat is **stateless**. Every message is answered as if it were the first one: the history is
stored and rendered, but it is never sent to the model. Dwellers also have almost no awareness
beyond their own row and the vault's live resource counters. Three separate gaps, three separate
fixes; they should not be shipped as one change.

## What exists today

### Transport and services

| Path | Entry | Service |
|---|---|---|
| text | `POST /chat/{dweller_id}` | `chat_service.send_message` → `run_chat_agent` |
| voice | `POST /chat/{dweller_id}/voice` | `conversation_service.process_audio_message` → `run_chat_agent` |
| history | `GET /chat/history/{dweller_id}?limit&offset` | `chat_service.get_history` → `chat_message_crud.get_conversation` |

Both message paths converge on `run_chat_agent` (`app/services/chat/agent_runner.py:103`), so a
continuation change lands once and covers text and voice.

Voice adds STT → agent → TTS and stores both audio files (`conversation_service.py:143-212`).

### The data model

`ChatMessage` (`app/models/chat_message.py:19-41`) is a flat pairwise record:

- `vault_id`, `from_user_id` **xor** `from_dweller_id`, `to_user_id` **xor** `to_dweller_id`
- `message_text` (2000 chars), optional `audio_url`, `transcription`, `audio_duration`
- `happiness_delta` / `happiness_reason`, optional `llm_interaction_id`

There is **no `conversation_id`, no thread entity, no read state, no summary**. A "conversation"
is derived: every row where the pair matches, ordered by `created_at`. That is enough to render a
chat window and not enough to reason about one.

### What reaches the model

`run_chat_agent` calls the pydantic-ai agent with the single message and the deps bundle:

```python
result = await dweller_chat_agent.run(
    message_text, deps=deps, instructions=instructions, usage_limits=CHAT_USAGE_LIMITS
)   # agent_runner.py:120 — no message_history, no prior turns
```

`instructions` are rebuilt per turn from the dweller's current row (`build_chat_instructions`,
`app/agents/chat_prompts.py:131`): identity, species/state-of-being, age register, mood band,
family line. The agent can additionally call five tools
(`app/agents/dweller_chat_agent.py:104-142`): production rooms, training rooms, all rooms, social
context, plus a pre-computed activity briefing (training/exploration/medical supplies).

So the dweller knows **the present** well and **the past** not at all.

### The one existing memory mechanism

`BioAddendumAction` (`app/schemas/chat.py:95`): the agent may propose one durable first-person
fact; it is only written if the player accepts it (`POST /dwellers/{id}/bio-addendum`,
`app/api/v1/endpoints/dweller.py:284`). Dweller-initiated, user-gated, max one sentence, deduped
against the existing bio (`chat_tools.py:401-407`). Good mechanism, very narrow channel.

### Awareness inventory

| The dweller can currently know | Source |
|---|---|
| own identity, species, state-of-being, age, mood band | prompt, per turn |
| own SPECIAL, health, stimpaks/radaways, outfit/weapon | `DwellerReadFull` fields via tools |
| family and relationship affinity | `build_dweller_social_context` (`chat_tools.py:151`) |
| vault power/food/water + average happiness | fallback prompt (`agent_runner.py:49-54`) |
| active training / exploration progress, training options | activity briefing |
| room availability | room tools |

| Nothing feeds the conversation | Consequence |
|---|---|
| prior messages in the same chat | every turn restarts; follow-ups are non sequiturs |
| who the player is, how long they have been away | no greeting continuity, no "you're back" |
| vault events: deaths, births, raids, arrivals, arena results | dwellers cannot grieve, congratulate or comment |
| other dwellers' fates and chats | no gossip, no social memory |
| the outcome of accepted action suggestions | a dweller cannot follow up on a promise |
| time since the last conversation | no staleness awareness |

`IncidentEvent` (`app/models/incident_event.py`) is the only durable narrative stream, written by
`services/combat/incident_publishing.py`. It is per-incident, not vault-wide, and nothing reads it
for dialogue.

Notably, chatting never touches `Relationship.affinity` — a conversation has zero social
consequence between dwellers.

### Prior art in the repo

No open issue and no doc covers chat memory, dialogue continuation or dweller awareness
(`gh issue list --search 'chat OR conversation OR dialogue OR memory'` returns only unrelated
multiplayer/platform/design umbrellas; `docs/` has no mention). This is greenfield.

## Options

### A. Transcript continuation — the smallest real fix

Load the last N messages for the `(user, dweller)` pair, convert to pydantic-ai model messages,
pass as `message_history`. Trim by token budget, oldest first, and keep the newest turn always.

- Change surface: `run_chat_agent` (+ an adapter module), query on `ChatMessage`.
- Cost: every turn resends history. Budget ~12 messages / ~1.5k tokens, not the 100 the UI loads.
- Failure mode to design for: the model re-answering the previous question, or treating a stale
  history as the present. Needs a "the last message was N ago" marker to stay honest.
- Buys: multi-turn coherence inside one sitting. Does not survive a week.

### B. Threads and sessions

`ChatMessage.conversation_id` + a `Conversation` table (`summary`, `last_message_at`,
`message_count`). Enables session lists, resume-after-days, and cheap long-term context via
summaries instead of full transcripts.

- This is the real "continuation" answer, and the most schema-heavy.
- Summaries also make continuation affordable: 12 recent messages + a 200-token summary of
  everything older is roughly the cost of option A for unlimited history depth.
- Requires a summarization job (or a lazy summarize-on-open) and a migration with backfill
  (existing rows have no thread; the natural key is the user/dweller pair).

### C. Dweller memory (long-term facts)

A `DwellerMemory` table: `dweller_id`, `fact`, `source_message_id`, `confidence`, `created_at`.
Fed into the prompt as "things you remember", deduped, capped (say 20 facts, newest first).

- Generalizes the existing `bio_addendum` idea from one sentence in the bio to a bounded memory.
- Needs extraction (a second model pass or the existing structured output), dedupe, eviction,
  and a decision on gating: automatic (cheap, risk of drift) vs player-confirmed (the current
  pattern, honest, but most facts die).
- This is what makes a dweller feel like a person across weeks, and it is the riskiest piece:
  a memoried dweller can contradict canon, invent history, or latch onto a joke.

### D. Awareness digest (world state)

A compact "since we last spoke" block assembled from `IncidentEvent` (new deaths, births, raids,
arena results since the last message), vault resource deltas, and vault changes (new rooms,
arrivals, departures). Injected into instructions, no new table needed for the first version.

- Cheapest high-impact change after A: it is a query + a prompt block.
- Needs a vault-wide event view; `IncidentEvent` is incident-scoped, so either widen it or add a
  derived digest query over incident rows.
- Must be filtered to what this dweller could plausibly know — a dweller in the diner does not
  know about a sealed room incident.

## Recommendation

Ship in three stages, each independently verifiable:

1. **A + D-lite** — transcript window plus a "since your last conversation" digest. Together they
   fix the felt problem: a dweller who remembers what you just said and notices something happened.
   No schema change. One PR.
2. **B** — threads and summaries, once the multi-session UX is wanted. Migration + backfill by pair.
3. **C** — dweller memory, last, with an explicit gating decision and an eviction budget.

Do not ship C first: memory without continuation produces confident, well-remembered nonsense.

## Acceptance criteria for stage 1

- A two-turn test: turn one states a fact, turn two asks about it; the reply must reference it.
  Written as a unit test over the history adapter with a fake model, not a live provider call.
- The history adapter caps at a token budget and always keeps the newest turn; oldest dropped first.
- Voice and text paths both receive history (shared `run_chat_agent`).
- A cost ceiling: measured prompt tokens per turn with a 12-message history, recorded in the PR.
- No change to the 2000-char message limit, quotas, or the fallback path's behaviour when history
  loading fails (it must degrade to today's stateless behaviour, never to an error).

## Open questions for the maintainer

1. Continuation scope: one sitting, or across days? That decides A vs B-first.
2. Should the dweller remember **the player's** statements as facts (e.g. "the Overseer promised
   radiation suits"), and may it act on them, or is memory descriptive only?
3. Awareness depth: only their own vault, or gossip about dwellers they have a relationship with?
4. Memory gating: automatic with dedupe, or player-confirmed like `bio_addendum` today?
5. Is there an acceptable token-cost ceiling per message? The current turn is instructions plus
   one message (roughly 700-900 prompt tokens by prompt length; not measured against a provider);
   a 12-message window is expected to roughly double it. Anyone implementing stage 1 should record
   the real number from `LLMInteraction` rather than trust this estimate.
