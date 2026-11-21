---
name: fallout-feature-intake
description: Use before starting any new game feature or system in falloutProject. Sizes the idea against a hard line/token budget, forces a playtest hypothesis, and gives the measured integration tax so cost is a number, not a guess.
---

# Feature intake — keep the game small

The game must stay small enough that one person can hold it in their head. A feature that cannot justify
its integration tax is not built.

## When to use

- Before starting any new feature, system, module, endpoint family or gameplay mechanic.
- When a request feels like "we could also add…" — that phrase is the trigger.
- When reviewing a PR that introduces a new concept rather than extending one.

## When not to use

- Bug fixes, refactors that remove code, copy changes, balance tweaks to existing numbers.

## The gate — answer in one paragraph, in the issue

1. **Which existing verb does it use?** No new player verbs without removing one.
2. **Could it be a data row instead of a system?** Kinds, quests, dweller lines, event definitions are
   data. If the answer is data, budget near zero and do not build a subsystem.
3. **What does it delete or replace?** "Nothing" is an allowed answer only for content-as-data.
4. **LOC budget** — code and tests separately. Estimate from a comparable feature, not optimism.
5. **Playtest hypothesis** — the specific thing to watch that decides whether it is fun. "It seems cool"
   is not a hypothesis.
6. **Dark for 30 days, then what?** Default answer: it is removed, not left behind a flag forever.

If questions 1–4 cannot be answered, the feature is not ready; it is a wish.

## Budgets (measured at 3.12.0 — update these numbers, not the principle)

| Metric | Now | Ceiling |
|---|---|---|
| backend prod lines | 89k | 100k |
| backend test:prod ratio | 1.12 | 0.8 |
| frontend src lines | 100k | 110k |
| feature docs | 32 | 15 |
| frontend module folders | 21 | 21 (no new folder without deleting one) |

Crossing a ceiling is allowed only with a consolidation or deletion in the same PR. The budget is not
there to be defended by argument; it is there to force the argument.

## The integration tax — what a system actually costs

A feature's real cost is its registration, not its logic. Adding **two tables and one flag** in one
session touched **47 files** and tripped **five** gates (timestamp drift, pinned UTC inventory, core→module
boundary, pinned enum snapshot, single-head migration assertion). Budget this explicitly.

Minimum registration for a new persisted concept:

- model + `app/models/__init__.py` (autogenerate is blind without it)
- migration in `app/alembic/baseline_versions/` chained onto the current head
- CRUD module + `app/crud/__init__.py`
- service, schema, endpoint module + `api/v1/api.py`
- tests: service, API, migration

Each of these is a separate file the author must remember. That is why new *systems* are expensive and
new *data* is cheap.

## Content is data, systems are code

The fun levers — more quests, more event kinds, more dweller lines, more sites — are the cheapest lines in
the repo (102 quest JSONs cost almost nothing to maintain). New subsystems are the most expensive
(47 files). So:

- Be **generous** with data: new event kinds, quests, dialogue, seeded rows.
- Be **ruthless** with systems: new screens, new periodic actors, new state machines, new cross-cutting
  concepts.

Do not answer "make the game more fun" by adding a system when a data row will do.

## Definition of done

- [ ] Gate answered in the issue, including the playtest hypothesis.
- [ ] Within budget, or something removed in the same PR.
- [ ] Tests cover failure modes, not surfaces — one test per distinct way it can break.
- [ ] No new module folder unless an old one dies.
- [ ] Feature flag has an owner and a date by which it is either enabled or deleted.

## Delete-first

Any PR over ~300 lines removes something: dead code, a superseded doc, or tests for a feature that no
longer exists. A habit, not a ratio.

## Doc discipline

`docs/features/` is a working set, not an archive. Shipped docs move to `docs/archive/`; unbuilt docs are
built or removed; speculation longer than a page belongs in an issue.
