# TypeSafe Jev Classifier — Dweller Combat Triage & Radiant AI

> Status: proposal. Full model docs: `https://pydantic.dev/docs/ai/models/typesafe/`.
> Roadmap stub: `docs/ROADMAP.md` ("TypeSafe Jev Classifier"). Complementary to the
> dweller chat agent — it does NOT replace it.

## What Jev is

[Jev](https://typesafe.ai/) is not a language model. You give it text and typed questions;
it answers each one with a confidence. It does not write text.

`TypeSafeModel` lets an agent whose job is to decide something run on Jev like on any other
model. Each field of the `output_type` becomes one question, the prompt is the text, and the
answers come back as the output. Change the model name and the same agent runs on a language
model, so the two can be compared.

```bash
pip install "pydantic-ai-slim[typesafe]"
export TYPESAFE_API_KEY='your-api-key'
```

```python
agent = Agent('typesafe:jev-latest', output_type=Handling)
result = agent.run_sync('rm -rf ./build')
```

## Model shape rules (non-negotiable)

- **Prompt = material judged, question = field description.** A question written into the prompt
  is text to be judged — Jev judges it. Only a bare `bool` with no description and no
  instructions is refused; do not count on errors catching misplaced questions.
- **One judgement per field.** `good pitch?` becomes `large_market` / `feasible` /
  `differentiated` + code. Multi-judgement questions return plausible numbers with low
  confidence — found out later, not at request time.
- **Framing in docstrings/instructions, wording in field descriptions.** An `Enum` field
  without a description uses the enum's class docstring. Name `Literal`/`Enum` options for
  what they mean — Jev sees an option by its name.

## What Jev can answer

| Field type | Question | Answer |
|---|---|---|
| `bool` | yes or no | `True` when probability ≥ 0.5 |
| `Literal[...]` / str `Enum` | pick one | chosen option |
| `float` with `ge=0, le=1` | yes or no | the probability itself (no confidence entry) |
| `list[Literal\|Enum]` | yes/no per option | options Jev said yes to |
| nested model | its fields as `outer.inner` | the model |
| `X \| None` | pick one + "None of these" | option or `None` |

- Confidence per field in `response.provider_details['confidence']` (0–1). For yes/no it is
  `abs(p - 0.5) * 2`; for pick-one it is spread-based. Pick the threshold **per use** (acting
  automatically deserves a higher bar than flagging for review) and calibrate on own labeled
  data — the shipped defaults come from a tiny internal ticket set.
- **Pin the version after tuning** (`typesafe:jev-1.13.0`): `jev-latest` moves and shifts the
  numbers under a tuned threshold. `ModelResponse.model_name` always records the versioned id.
- Low confidence → `FallbackModel('typesafe:jev-latest', '<llm>', fallback_on=[...])` hands
  exactly the unsure requests to a language model. Watch the hand-off rate, not just accuracy.

## Tools: Jev picks, calls what it can

With tools attached, every request carries one more question — which route the text calls for —
with the output type first and every tool after it. Each tool is described by its docstring.

- **No-arg tool** → Jev calls it alone; result returns as history for the next request.
- **No-arg output function** → hand-off that ends the run (only handed-off requests pay for a model).
- **Tool with args** → Jev cannot fill them; the request ends in `ToolCallProposed` (a
  `ModelAPIError`), so a `FallbackModel` with a language model behind Jev takes the whole step.
- Taken at or above `typesafe_tool_call_threshold` (default 0.6 — a starting point, tune it).
  A pick is a classification of the text, **not** a judgement that running the tool is safe:
  approval and limits stay the agent's job. Put `UsageLimits(request_limit=...)` on any Jev
  agent with tools.

## What Jev answers badly / cannot do

Badly (returns an answer, not an error — that is what makes it worth knowing): arithmetic,
counting, dates; several judgements in one question; indirection; bloated state; repeated tool
picks; unseen args; adversarial text; option-order sensitivity.

Cannot (refused with `UserError` before a request): `str` output, second structured type,
`NativeOutput`/`PromptedOutput`, native tools, image/audio/video/document input, `ModelRetry`
revision (same answer comes back). Jev answers in one piece — streaming shims emit one event.
State + longest question cap is 64k tokens; over-long conversations fail with
`max_tokens_exceeded`, which a `FallbackModel` quietly turns into a language-model call.

## Integration plan — radiant AI first

New self-rescheduling Dramatiq actor (`radiant_tick`), modeled on `arena_tasks.arena_tick`
(Redis lease + `task_session()`). **Never** inline per-dweller calls into `process_game_tick`
(one shared session across all vaults). Online-gated via `game_state.is_user_online()`.

```python
class RadiantNeed(BaseModel):
    """Decide what an idle/resting dweller wants next."""

    wants_rest: bool = Field(description='Does this dweller need rest or solitude right now?')
    wants_social: bool = Field(description='Does this dweller seek company right now?')
    wants_change: bool = Field(description='Is this dweller restless with current assignment?')
```

- State text reuses `chat_tools.build_dweller_social_context` /
  `build_dweller_activity_briefing` (the same builder the chat agent uses).
- Feeds `dweller_assignment_service`, `happiness_service._calculate_happiness_change`,
  `exit_request_service.sync_despair_requests`; below-threshold confidence falls back to the
  deterministic formula.
- Prompt registered append-only (`version-prompt radiant_behavior`), gated on `quota_service`,
  usage logged as `LLMInteraction`; outcomes surface via `notification_service.create_and_send`
  under the modal/toast red line (`GAME_MECHANICS.md`).

## Integration plan — combat triage (narrow seams)

Damage math stays deterministic in `incident_math.py` / `utils/combat.py`; Jev only triages.

- **Incident-spawn triage** (`incident_spawning.spawn_incident` / `notify_spawn`):
  `Literal['hold','reinforce','evacuate']` + confidence on the spawn SSE. Hours-scale budget.
- **Exploration engage/avoid** (`exploration/combat_calculator.calculate_combat_outcome`):
  10-minute budget behind the existing `to_thread` boundary, formula fallback.
- **Responder suggestion** (`incident_service.assign_responders`): player-facing ranked subset.
- **Explicitly out:** synchronous calls in `incident_round.process_incident` (2s all-vault
  advisory-locked tick), arena rounds, quests (timer-only, no combat).

## Guardrails

- Deterministic resolvers stay where they are; new module named `*_service.py`; CRUD owns
  queries (no raw `select()` in services); tick path uses `await session.execute(...)`, never
  `.exec()`; endpoints stay thin with `verify_dweller_access` / `get_user_vault_or_403`.
- Measure accuracy, hand-off rate, and threshold on own labeled dwellers/incidents first;
  wire cost through `ai_usage_service` before rollout.

## Rollout order

1. `radiant_tick` with `RadiantNeed` on idle/resting dwellers, deterministic fallback.
2. Incident-spawn triage attached to spawn notifications.
3. Exploration engage/avoid behind the formula fallback.
4. Responder suggestions in the incident UI.

## Implementation findings — first integration attempt (2026-10-01)

A first pass wired Jev into the codebase. Results, decisions, and traps found along the way.

### Provider wiring (pydantic-ai 2.52+)

- `pydantic-ai-slim` gained the `typesafe` extra **after 2.30**; the repo was pinned at
  2.30, where `TypeSafeModel` / `typesafe:` does not exist. The extra must be a
  **project optional-dependency** (`uv add "pydantic-ai-slim[typesafe]"`), not a marker on
  the main dependency list — otherwise `uv` resolves it to nothing and installs nothing.
- **`Agent("typesafe:…")` reads the API key from the OS environment, not from `settings`.**
  The app loads `.env` into `settings.TYPESAFE_API_KEY` but never into `os.environ`, so the
  by-name constructor silently has no key and auth fails at call time. **Pass the key
  explicitly**: `TypeSafeProvider(api_key=settings.TYPESAFE_API_KEY)` (or export it). Any
  code path that only works when the key is exported to the shell is broken in production.
- `Agent.__init__` does **not** accept `usage_limits`; it is a per-run argument
  (`run(..., usage_limits=...)` / `run_stream(..., usage_limits=...)`).

### What worked

- Typed `decide(state, output_type) -> {output, per-field confidence, model_name}` is a
  clean seam. `JevDecision` must stay **generic** (`JevDecision[OutputType]`) so callers
  keep their concrete output type; a `BaseModel`-typed `output` loses the fields.
- Screening chat input for injection + toxic is a genuine fit: on a 24-case synthetic set,
  benign 12/12, injection 8/8, toxic 3-4/4. Injection lands at **0.97+ confidence**;
  **toxic is unstable at 0.5-0.7** run to run — one threshold for both fields is wrong,
  the two need **per-field bars** (or the toxic field needs better criteria wording).
- A labelled corpus + `fo-cli jev-eval` is worth keeping: it turns threshold tuning into
  measurement, prints a false-positive/false-negative split, and records the resolved
  model version. Pin `JEV_MODEL` once a bar is tuned (`jev-latest` moves under it).

### Removed: exploration-event triage (do not re-add as-is)

An advisory Jev label on generated exploration event narratives was built and then
removed. Reasons, which apply to any future "classify text that already has a type":

- **Wrong value.** The event already carries a typed `event_type` from the generator, so
  re-classifying the narrative added a label nobody acted on. Reclassifying typed data is
  not a decision; prefer targets where Jev *chooses* something (see rollout order).
- **Ran inside the locked game tick.** `event_service.process_event` awaits Jev **before**
  the commit, while the exploration row is locked — a slow Jev serialises the tick. **Any
  Jev call on a tick/locked path must be post-commit enrichment in a worker**, never an
  inline `await` ahead of gameplay effects.

### Other traps to honour

- **Screen at a shared boundary.** Ordinary text chat screened the message; the streaming
  (WebSocket) path did not, so the same policy was enforced on one transport only. Put
  screening where both transports pass, not in each caller.
- **Bound the call.** Give every optional decision a deadline and usage accounting:
  elapsed time, tokens/cost, model version, outcome. Fail-open only helps once the call
  *returns*; SDK retries can extend a failure, so cap the whole operation.
- **Jev is advisory, never authoritative.** It answers the question as written and is
  documented as movable by adversarial text; keep it beside deterministic checks, not in
  place of them.

