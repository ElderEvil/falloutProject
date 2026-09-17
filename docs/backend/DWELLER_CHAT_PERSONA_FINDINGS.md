# Dweller Chat — Persona & Dialogue Findings

> Status: **Findings audited 2026-09-17; prompts improved and measured the same day.**
> Harness: `scripts/dweller_chat_scenarios.py`
> Baseline run (before): `scripts/scenario_output/20260917T194436Z/`
> Improved run (after): `scripts/scenario_output/20260917T202740Z/`
> Branch: `chore/dweller-chat-scenario-harness`

## Why this exists

Dweller chat had no way to answer "does a child sound like a child, does a ghoul sound like a ghoul,
does a miserable dweller sound miserable?". This document records an evidence-based audit of how well the
**original** chat prompts expressed dweller individuality, what changed to fix it, and the measured effect.

Read this before touching `backend/app/agents/chat_prompts.py` or
`backend/app/services/chat/agent_runner.py`.

---

## How the experiment was run

`scripts/dweller_chat_scenarios.py` drives LM Studio sequentially (one request at a time — never parallel)
and records every turn with usage, latency and heuristic metrics.

The system prompt is assembled from the **real production sources**, not a paraphrase:

| Piece | Source |
| --- | --- |
| Registry prompt | `DEFAULT_PROMPTS["chat"]` in `app/services/prompt_service.py` |
| Structured (agent) profile | `build_chat_instructions()` in `app/agents/chat_prompts.py` |
| Plain (fallback) profile | `build_dweller_prompt()` in `app/services/chat/agent_runner.py` |

Order matches PydanticAI: literal instructions first, dynamic ones second.

> **Fidelity note:** the live `prompt` table was empty during both runs, so production resolves `"chat"`
> to the hardcoded v1 default. That is exactly the string the harness used.

### Modes

| Mode | Prompt | Answers |
| --- | --- | --- |
| `agent` | `build_chat_instructions` + registry | What does the shipped structured prompt produce? |
| `fallback` | `build_dweller_prompt` + registry | What does the plain path produce? |
| `history+` | `fallback` + prior turns replayed | What does conversation memory cost? |

### Run

```bash
cd backend && uv run python ../scripts/dweller_chat_scenarios.py           # full run (~13 min, 60 turns)
cd backend && uv run python ../scripts/dweller_chat_scenarios.py --dry-run # print assembled prompts only
cd backend && uv run python ../scripts/dweller_chat_scenarios.py --modes fallback --only child --turns 2
```

Settings: `google/gemma-4-e4b`, temperature `0.8`, `max_tokens 1200`, 7 personas × 4 shared probes,
plus a 4-turn history ablation. Personas: `adult_baseline`, `child`, `elder` (age 72), `ghoul` (sane),
`super_mutant` (average), `low_happiness` (happiness 12), `family` (partner Ana + daughter Tomas).

> **Model note:** `gemma-4-e4b` is a reasoning model that emits hidden `reasoning_content`. At
> `max_tokens=220` answers came back **empty** (budget spent thinking); real answers needed ~600–1600 tokens.
> Any hard cap below ~800 will surface empty dweller replies.

---

## Original problem (audited)

**The prompt did not know who the dweller was.** The profile conveyed level, gender,
`Child`/`Teen`/`Adult`, rarity, room, gear, health, SPECIAL, vault stats — and happiness as a bare integer.
Everything that made a dweller an individual was either never read or gated behind a tool call a small
local model cannot make.

---

## What was implemented

| Item | Change |
| --- | --- |
| Species | `chat_prompts.identity_line()` reads `visual_attributes["race"]` / `["state_of_being"]` via `race_of()` and states it, using the canonical `race_descriptions` |
| Age register | `chat_prompts.age_voice_line()` adds child / teen / elder speech rules |
| Mood | `chat_prompts.happiness_mood_line()` maps happiness to four tone bands |
| Family | `chat_tools.load_family_members()` resolves partner/parents/children; injected by `chat_instructions` (agent path) and `run_fallback_chat_agent` (fallback path) |
| Fallback hardening | `build_dweller_prompt` now includes the **biography** (it previously omitted it entirely), an 80–120 word cap, and a never-contradict-the-biography rule |
| New age group | `AgeGroupEnum.ELDER`, with `ADULT_AGE_GROUPS` replacing the ~20 literal `== AgeGroupEnum.ADULT` gameplay gates that silently excluded any non-adult name |
| Fallback robustness | `load_family_members` re-reads the ORM row (relation ids are not on `DwellerReadFull`) and returns `[]` for a missing record |

`elder_age_years` (default 60) lives in `DwellerConfig`. Elders are full adults for work, training,
combat, exploration, quests and auto-assignment; **breeding stays ADULT-only**. Elders are derived from
`birth_date` at generation and promoted by `BreedingService.age_children`.

---

## Measured delta

Fallback path (the realistic local-model route) — `before -> after`:

| Persona | Words | Flesch | Affect | Race hits | Family names |
| --- | --- | --- | --- | --- | --- |
| adult_baseline | 200.8 → **121.0** | 65.2 → 66.7 | −0.25 → +0.75 | 0 → 0 | 0 → 0 |
| child | 130.0 → **97.8** | 67.4 → **74.5** | +0.75 → +3.25 | 0 → 0 | 0 → 0 |
| elder | 195.0 → **118.8** | 63.9 → 64.9 | −0.75 → 0 | 0 → 0 | 0 → 0 |
| ghoul | 188.3 → **118.5** | 63.3 → **69.5** | +0.75 → 0 | 1 → **6** | 0 → 0 |
| super_mutant | 194.8 → **108.5** | 67.3 → 68.5 | +0.25 → +1.5 | 0 → **7** | 0 → 0 |
| low_happiness | 178.3 → **95.5** | 67.0 → **72.2** | **+0.75 → −2.0** | 0 → 0 | 0 → 0 |
| family | 169.8 → **105.3** | 69.0 → 65.0 | +1.0 → +1.25 | 0 → 0 | **0 → 8** |

Agent path highlights: child length 98.8 → **62.0** words; low_happiness affect −0.75 → **−1.75**;
family names 4 → 6. Zero truncations and zero empty replies in the improved run.

The four defects the audit found, restated as outcomes:

1. **Race was invisible.** A super mutant answered as an ordinary human repairman. Now: 0 → 7 race hits,
   and `Species:` is explicit in both prompts.
2. **Children did not sound like children.** They were statistically indistinguishable from adults — and
   slightly *more* lexically complex. Now shorter and simpler (*"Good morning! I feel... good today"*,
   drawing a bird, parents describing the open sky).
3. **Happiness was inert — and inverted on the fallback path.** The happiness-12 dweller read *happier*
   than the baseline. Now correctly negative (*"It's exhausting, staying contained here"*).
4. **Family vanished.** The family dweller never used the names in its own biography; asked about family,
   it answered generically. Now names Ana and Tomas and keeps its backstory.

**Conversation-memory drift is also fixed.** With history replayed, the family dweller previously invented
*"my parents… a small apartment… dinner parties… a movie"* — contradicting its biography. After adding the
biography + never-contradict rule, the same 4-turn run invents nothing and names Ana and Tomas correctly.

---

## Still open

1. **Chat is still stateless.** No `message_history` is passed anywhere in `chat_service` /
   `agent_runner` / `streaming`, so a dweller cannot reference the player's previous message. The drift fix
   above makes history *safe* to add, but adding it is a separate decision (token cost, retention).
2. **Tool-call leakage on the agent path.** With `gemma-4-e4b`, 53% of agent-mode turns leaked internal
   contract text (`**Sentiment Analysis:** +3`, `<|tool_call>call: …`) into the user-visible reply, and 2
   turns fabricated a tool *result*. These fail structured validation in production and fall back to the
   plain path, so the fallback prompt is the one that matters. Sanitising tool-call output before
   persistence is still outstanding.
3. **Numeric age is not in the prompt.** `visual_attributes["age"]` remains unused; the elder register comes
   from `age_group`. That is deliberate (one source of truth) but means no dweller ever states its age.

---

## Appendix

**Metric caveats.** Affect/family/race counts are dependency-free keyword heuristics, calibrated for
*comparison within a run*, not absolute truth. Read them beside the raw transcripts. Flesch reading ease
uses a vowel-group syllable estimate, so treat it as a relative simplicity signal.

**Artifacts.** `scripts/scenario_output/<UTC timestamp>/` holds `transcript.json` (every turn incl.
hidden reasoning), `summary.json` (per-mode aggregates) and `report.md`. The directory is gitignored.

**Ruled out.** `race_of()` (`app/options/races.py`) was initially suspected of returning `None` for API
read schemas. Verified **not a bug**: `DwellerReadFull.visual_attributes` is a `dict`. The real constraint
is the opposite one — `DwellerReadFull` carries **no** `partner_id`/`parent_*` fields (only
`DwellerReadLess` does), which is why the family resolver re-reads the ORM row.
