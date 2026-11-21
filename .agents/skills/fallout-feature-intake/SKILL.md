---
name: fallout-feature-intake
description: Use before starting any new game feature or system in falloutProject. Sizes the idea against the repo's advisory size targets, forces a playtest hypothesis, and gives the measured integration tax so cost is a number, not a guess.
---

# Feature intake — keep the game small

The policy lives in `AGENTS.md` ("Feature intake and size policy"); this skill is the long form. The
numbers are advisory review context, not CI enforcement — CI gains no size gate.

## When to use

- Before starting a new feature, system, module, endpoint family or gameplay mechanic.
- When a request feels like "we could also add…" — that phrase is the trigger.
- When reviewing a PR that introduces a new concept rather than extending one.

## When not to use

- Bug fixes, refactors that remove code, copy changes, balance tweaks to existing numbers.

## The gate — answer in one paragraph, in the issue

1. **What player action does this extend, and can existing code own it?**
2. **Can a catalog or configuration entry deliver it?** Kinds, quests, dweller lines and event
   definitions are data. If a data row will do, budget near zero and do not build a subsystem.
3. **What existing behavior or maintenance work does it replace?**
4. **What production, test and integration work will it require?** Estimate from a comparable change,
   not optimism, and count code and tests separately.
5. **What would a playtest need to show?** The specific thing to watch that decides whether it is fun.
   "It seems cool" is not a hypothesis.
6. **Who owns any flag, and when will they decide to enable or remove it?**

If questions 1–4 cannot be answered, the feature is not ready; it is a wish.

## Review targets (advisory, measured)

Refresh with `python3 scripts/size-report.py <base-ref> [head-ref]`; it prints test:production ratios and
the gross handwritten application/test additions that trigger the ~300-line PR prompt (tooling excluded).
Compare trends, not one number.

| Metric | Advisory target |
|---|---|
| handwritten backend production | ~100k lines |
| handwritten frontend production | ~110k lines |

There is no test-ratio ceiling, module-count ban or mandatory deletion. Those are trends and judgement
calls. A material overage calls for a short explanation in the PR body; it is not a merge blocker.
Preserve the distinct coverage families in `AGENTS.md` rule 10.

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

Each of these is a separate file the author must remember. `fallout-conventions` prices the individual
gates. That is why new *systems* are expensive and new *data* is cheap.

## Content is data, systems are code

The fun levers — more quests, more event kinds, more dweller lines, more sites — are the cheapest lines in
the repo. New subsystems are the most expensive. So be generous with data rows and ruthless with systems;
do not answer "make the game more fun" by adding a system when a data row will do.

## Definition of done

- [ ] Gate answered in the issue, including the playtest hypothesis.
- [ ] Production, test and integration work estimated from a comparable change.
- [ ] Tests cover failure modes, not surfaces — one test per distinct way it can break.
- [ ] Any feature flag has an owner and a date by which it is enabled or removed.
- [ ] At ~300 handwritten application/test lines added (tooling excluded), the change names what it
      replaces ("nothing to remove" is allowed).

## Doc discipline

`docs/features/` is a working set. Shipped contracts that still guide development stay with the code they
describe; superseded reference material moves to `docs/archive/`; proposals without scheduled work live in
their issue. Long speculation belongs in an issue, not a feature doc.
