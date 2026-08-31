# AI Layer Upgrade — Prompts, LLM Interactions, Admin & New Usage

> Status: Proposal (Target: next updates). Predecessor docs: `docs/backend/PYDANTIC_AI_GATEWAY.md`,
> `docs/ROADMAP.md` (Bio Extension, Quests Improvements), `docs/features/BIO_MAP_UNCOVERING.md`.

## Goal

Make the AI layer observable, configurable, and cheap — and decide, per consumer, whether the current
per-feature Pydantic AI agents stay, get upgraded, or get replaced with cheaper deterministic paths.

## Current State (audited)

### What exists

| Piece              | Location                                                                                                                   | State                                                                                                               |
| ------------------ | -------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------- |
| Pydantic AI agents | `backend/app/agents/dweller_agents.py` (backstory, extend-bio, visual-attributes), `dweller_chat_agent.py` (chat, 6 tools) | Live, structured outputs, retry validation, Logfire tracing                                                         |
| Provider profile   | `AIService.get_model()` + `AISettings` DB row (provider/model/base_url/gateway)                                            | Live; profile overrides env                                                                                         |
| Usage tracking     | `LLMInteraction` rows (`usage` operation tag, token counts, user) written by `dweller_ai`                                  | Written, but `prompt_id` is **never populated**; no provider/model snapshot                                         |
| Quota              | `quota_service` + `ai_usage_service.get_user_usage()` (all-time/monthly aggregates)                                        | Per-user totals only — **no per-operation breakdown**                                                               |
| Prompt model       | `Prompt` table (`prompt_name`, `prompt_template`, `generate_prompt()`) + CRUD + admin view                                 | **Dead code**: no API, no seed, no consumer reads it; `prompt_name` is **not unique**, no active/version concept    |
| Legacy AI path     | `chat_service.generate_objectives()`                                                                                       | Raw `AsyncOpenAI` + hardcoded `gpt-4-turbo` + inline prompt string — **bypasses** profile, quota, and usage logging |

### Problems

1. **Prompts are code.** All agent instructions are hardcoded in `dweller_agents.py` / `dweller_chat_agent.py`.
   The `Prompt` DB model (name + template + `generate_prompt(**kwargs)`) exists but is orphaned: no seed data,
   no API, no runtime reader. Tuning a prompt = code change + deploy.
2. **`LLMInteraction` is half-wired.** `prompt_id` is never set, `parameters` holds a single string (origin),
   and there is no per-operation aggregation — you cannot answer "how many tokens did bio generation cost this
   month" without a manual query. Because prompt rows are mutable, a stored `prompt_id` would not even say what
   was actually sent.
3. **Two AI stacks.** Pydantic AI agents (profile-aware, quota-gated, traced) coexist with a raw `AsyncOpenAI`
   call in `chat_service.generate_objectives` (hardcoded `gpt-4-turbo`, no quota, no usage row, and the
   `GET /objectives/generate` endpoint has **no auth dependency** — anyone can spend tokens).
4. **Admin is a raw table browser.** 23 model views but no LLM-specific tooling: `LLMInteraction` shows 4
   columns, `PromptAdmin` shows only names, no token dashboards, no prompt playground, no way to trace a bad
   generation back to its inputs. (Configuration regression tests exist in `test_admin/test_views.py`; what is
   missing is authenticated render smoke coverage.)

## Plan

### Plan 0 — Lock down `/objectives/generate` (immediate, do first)

`GET /objectives/generate` is an **unauthenticated, token-spending endpoint** — anyone on the internet can burn
API budget. The frontend has **no caller** (only the generated OpenAPI types mention it).

- **Now:** require `CurrentSuperuser` and switch to `POST` (a token-spending action must not be a GET).
- **Then decide:** no frontend caller exists today, so the likely outcome is **deletion** (Option B below).
  Keep the endpoint only if a product need for on-demand objective generation is confirmed.

### Plan 1 — Durable interaction metadata (before analytics)

Make `LLMInteraction` rows self-describing so later analytics are trustworthy. One migration:

- `operation` — keep the existing `usage` string as the operation tag (values in the wild today:
  `chat_with_dweller`, `audio_chat`, `extend_bio`, `generate_audio`, `generate_backstory`, `generate_photo`,
  `generate_visual_attributes`, `quota_tracking` — **eight**, not seven; treat as an open set with a documented
  enum in code, not a PG enum).
- `provider` / `model` — snapshot the actual provider and model at call time for every provider-backed operation,
  including image and TTS calls (the profile can change between interactions; retroactive cost math and debugging
  need what was actually used).
- `prompt_id` — populate for every prompt-backed interaction (FK already exists, currently always NULL).
  `quota_tracking` is not an LLM request and remains NULL; image/TTS calls remain NULL until their prompts join the
  registry.
- `instructions_hash` (and optionally `rendered_instructions`) — snapshot of what was actually sent, so a
  mutable prompt row never erases provenance. This is the cheapest possible audit trail; retrofitting it later
  is far more expensive.

### Plan 2 — Prompt Registry (immutable versions, not mutable rows)

Move agent instructions into the `Prompt` table — but as **append-only history**, not mutable rows:

- **Schema additions:** `version: int`, `is_active: bool`, a **unique constraint on `(prompt_name, version)`**,
  and a PostgreSQL partial unique index allowing only one active row per `prompt_name`. `prompt_name` alone is not
  unique today, which would make runtime resolution ambiguous.
- **"Copy as new version"** in admin creates a new row with `version+1` and flips `is_active` in one transaction;
  old rows are never edited. Activation invalidates the prompt cache immediately. This preserves the provenance
  guarantee: an old `LLMInteraction.prompt_id` still points at the exact instructions that were sent.
- **Runtime resolution with failure/latency strategy:** `PromptService.get_instructions(agent_name)` reads the
  active row through a **short TTL cache** (e.g. 60 s) so admin edits propagate quickly without a DB hit per
  request. **Any DB error/timeout falls back to the hardcoded default** and logs a warning — a prompt-store
  outage must degrade to the shipped prompt, never fail the agent. Note the deps shape: `BackstoryDeps` /
  `ExtendBioDeps` / `VisualAttributesDeps` do **not** carry a DB session, so the loader resolves prompts in the
  service layer before the agent runs and passes the resolved string via deps (or a cached service) — this is a
  designed change, not a decorator swap.
- **Templates are a constrained interface:** validate allowed variables on save (admin-side validation listing
  the permitted slots per agent), and reject unknown `{placeholders}` and unescaped literal braces — plain
  `str.format()` raises on both, and JSON examples in prompts are full of braces. Prefer explicit
  `string.Template`-style substitution or an allow-listed formatter over raw `str.format`.
- **Seed** the current hardcoded strings as version 1 (one seed script): `backstory`, `extend_bio`,
  `visual_attributes`, `chat`.
- **LLMInteraction gains `prompt_id` + `instructions_hash`** — populated for prompt-backed interactions;
  non-prompt operational rows remain NULL by design.

### Plan 3 — Usage analytics & admin surfacing

Built on the now-trustworthy metadata:

- **Per-operation breakdown** in `AIUsageResponse` (`by_operation`), so the profile page can show "bio
  generation: 40% of your quota". One `GROUP BY usage, user_id` query covers totals; a **daily trend needs a
  separate `GROUP BY day` query** — do not pretend one query does both.
- **Cost estimation done honestly:** input and output token prices differ, providers/models can change
  mid-history, and image/audio operations are not token-priced. Snapshot `provider`/`model` on the interaction
  (Plan 1 metadata) and price per interaction from a config-side price table; any retroactive figure is labeled
  a _current-price estimate_, never a historical truth. Image/audio operations are excluded from token-based
  cost math.
- **Anomaly surfacing** — admin flag for users whose `chat_with_dweller` share exceeds a threshold (chat is the
  highest-volume operation; runaway loops show here first).

### Plan 4 — sqladmin improvements (small, high-value)

Current admin has configuration regression tests (`test_admin/test_views.py`: credential exposure, read-only
guards, verify-email action) but **no authenticated render smoke coverage** — that is the gap to fill.

1. **LLM Interaction view upgrade** — add `prompt_tokens`, `completion_tokens`, `total_tokens`, `created_at`,
   `provider`/`model` (once Plan 1 lands) to `column_list`; read-only; sortable by operation and user.
2. **Prompt view** — add `prompt_template` to details plus a "preview rendered prompt" panel (format with sample
   kwargs, using the validated formatter) so tuning doesn't require DB access.
3. **Dweller view bio column** — show a has-bio flag / bio length in the list; jump-starts bio-gap audits
   (feeds the Bio Extension backfill).
4. **Authenticated render smoke tests** — one per view (list renders, 200) using the existing superuser
   fixtures; catches template/URL regressions like the mixed-content CSS bug.
5. **Optional**: `can_export = True` on Vault/Dweller for balance analysis (currently only two views allow it).

Each idea must justify its token cost against the template-first rule: anything that can be a template should be,
and nothing ships before per-operation usage data shows there is budget headroom.

### Plan 5 — Pre-Generation Shift (local AI → curated content, zero runtime cost)

**Direction:** reduce in-time AI generation to the minimum and rely on **pre-generated, curated, reusable**
content — including for AI-generated parts. The local setup (LM Studio on an RTX 3080, ComfyUI for images) is
more than capable of batch-generating text quests and images offline; the runtime then serves committed content
instead of calling providers.

**Why this fits the existing architecture:**

- The **provider profile** already supports LM Studio (`AIService` priority: Gateway → direct → Ollama →
  LM Studio → disabled) — batch runs are a profile row, not new plumbing.
- The **pregen pattern already exists**: `PregenService` + CLI (`pregen-dwellers`, `fill-missing-bios`) produce
  deterministic, seeded, reviewable content offline. Extend the same shape to quests and images.
- **Storage exists**: RustFS already hosts dweller images (`dweller-images` bucket); pre-generated portraits and
  quest art land there exactly like runtime-generated ones.
- **Recycling pipeline** proves the pool model: radio recruits prefer soft-deleted dwellers (80%). A
  pre-generated content pool is the same idea for text/images.

**What moves offline (batch → curate → ship as content):**

| Content                   | Today                                                                   | Pre-generated                                                                                     |
| ------------------------- | ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| Quest chains / objectives | runtime AI (`generate_objectives`, hardcoded gpt-4-turbo) or JSON seeds | LM Studio batch → curated `quests.json` (feeds the Quests Improvements fragment)                  |
| Dweller portraits         | per-request OpenAI image call                                           | ComfyUI batch per archetype/race/faction matrix → RustFS library; creation picks from the library |
| Bios                      | template-first (already shipped)                                        | LM Studio generates template _variations_ offline → curated into the options library              |
| Incident narration        | (idea, parked)                                                          | pre-generated pool per incident type, runtime picks one                                           |
| TTS audio                 | runtime `tts-1` per message                                             | pre-generate common lines offline; runtime TTS stays opt-in                                       |

**How it works:**

1. **Offline batch** — a CLI (`pregen-content`) drives LM Studio (OpenAI-compatible API) and ComfyUI's API with
   the production prompts (from the Plan 2 prompt registry), producing candidate content with seeds.
2. **Curation gate** — generated content lands in a review queue (files or admin), a human curates before it
   becomes shippable. Nothing auto-promotes.
3. **Ship as data** — curated content is committed like `dwellers/*.json` / `quest_rewards.json` (which already
   carry hand-authored bios) or uploaded to RustFS for images; runtime reads it like any other static data. Each
   portrait library release includes a versioned manifest mapping asset key, archetype, generation seed, source,
   and review status; retention rules prune superseded unreferenced assets from RustFS.
4. **Runtime fallback** — if the curated pool runs dry (e.g. unique quest reward dwellers), fall back to
   template content, never to a runtime AI call.

**Effect:** in-time AI shrinks to chat (the only genuinely interactive surface) plus optional user-triggered
upgrades. Everything else — quest text, portraits, flavor pools — is generated offline, curated, versioned with
the repo, and costs zero at runtime. The RTX 3080 does the work at authoring time, not request time.

**Blockers:** none hard. ComfyUI integration is a new (small) client; portrait library needs a naming/indexing
convention keyed by the archetype matrix; quest JSON schema comes from the quest improvements fragment.

### Plan 6 — New AI usage ideas (parked, need product decisions)

- **Incident narration** — one-paragraph incident resolution flavor text (cheap, high flavor-per-token).
- **Quest flavor generation** — chain descriptions from the quest improvements fragment.
- **Overseer daily digest** — LLM summary of the Overseer Briefing metrics (P3; the briefing already computes
  the data, this only adds narration).
- **Dweller-to-dweller ambient chat** — **stays parked indefinitely**: periodic autonomous conversations are the
  easiest path to a runaway-cost feature. Revisit only if per-operation usage data shows real headroom.

Each idea must justify its token cost against the template-first rule: anything that can be a template should be,
and nothing ships before per-operation usage data shows there is budget headroom.

## Delivery Order

1. **Plan 0 (lock down `/objectives/generate`)** — immediate: auth + POST, then decide delete vs migrate after
   confirming the (currently absent) frontend usage.
2. **Plans 1–2 (interaction metadata + prompt registry)** — schema first (`version`, `is_active`, snapshot/hash),
   then runtime resolution with cache + DB-failure fallback.
3. **Plan 3 (usage analytics)** — only after Plans 1–2 make the data trustworthy.
4. **Plan 4 (sqladmin)** — rides along with Plans 1–3 (same views).
5. **Plan 5 (pre-generation shift)** — offline LM Studio/ComfyUI batch runs; content lands as curated JSON/assets.
6. **Plan 6 ideas** — only after 1–3 land and only if per-operation usage shows headroom.

## Non-Goals

- No migration off Pydantic AI — the agent layer stays; only prompt sourcing and the raw-OpenAI outlier change.
- No per-request admin editing of agent behavior beyond prompt text (no model/temperature per prompt).
- No retroactive cost "truth" — historical figures are estimates labeled as such; exact per-interaction cost
  starts only once provider/model snapshots exist.
