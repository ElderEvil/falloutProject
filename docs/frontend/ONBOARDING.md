# Spotlight onboarding

> Status: **shipped** in PR #1000, pending the validation below. This document records the
> behaviour that ships, its ownership boundaries and the checks still outstanding. Deferred
> work is summarised at the end and tracked in [`../ROADMAP.md`](../ROADMAP.md).

## What ships

A first-session guide that shows one useful action at a time, then hands off to the Briefing.

- **Five authored orientation lessons** (`frontend/src/modules/progression/models/onboardingSteps.ts`):
  power bar → generator → SPECIAL staffing → housing → departure. This definition list is the
  only source of **teaching** order.
- **Local teaching progress is separate from server reward progress.** Teaching state is a
  per-vault ledger in `core/composables/useOnboardingState.ts`; reward order, completion
  targets and payouts stay server-side.
- **Skip step / Skip tour / Resume / Replay.** `skipLesson` bypasses one explanation and leaves
  the server objective untouched; `skipTour` suppresses the whole orientation; `resumeGuide`
  clears only that suppression; `replayOrientation` clears orientation teaching statuses and
  re-arms the tour without paying again. Preferences exposes Resume and Replay.
- **Server-authoritative claims.** A claim is offered only when the lesson's objective is the
  lowest unclaimed starter step; otherwise the card shows a blocker with an Open Starter link.
  Replay reaches claimed explanations with Continue and no reward action.
- **Eligibility checks** (`onboardingSteps.ts`). Housing prices the build as
  `base_cost + existing same-category rooms × incremental_cost` (matching backend
  `get_room_build_price`); departure uses the complete vault roster (mature, not away,
  `health > 0`). Unloaded data reads `unknown` and never dims.
- **Persistence and error recovery.** One shared state per session, created in a detached
  effect scope so it survives a consumer unmount and a storage failure after start-up; corrupt
  or unsupported persisted data degrades to an empty ledger. A failed objective read surfaces
  Retry; a claim error clears when the lesson or vault changes; hidden or off-screen anchors
  fall back to explicit navigation.

## Compatibility (starter cohort)

Objectives share template rows, so preserving a legacy vault's ordering and rewards requires
separate revised templates rather than an in-place rewrite.

- **Existing vaults keep their entire original starter track.** Each legacy row is restored to
  its released `challenge`/`reward`/`objective_type`/`target_entity`/`sequence` and marked
  `assignable = false`; its links keep evaluating and claiming.
- **New standard vaults receive the revised track**, whose definitions that changed
  requirements, payout or sequence use versioned keys (`…#v2`). The new explore step has no
  legacy counterpart and keeps its key.
- **Fresh assignment requires both `assignable = true` and `objective_type IS NOT NULL`.**
- **Links are never touched** by the cohort migration: progress, totals, completed claims and
  reward snapshots survive. No template is retired while assigned links still depend on it.
- **Boosted-vault assignment is unchanged.**
- Implemented by the corrective migration `2026_10_14_0002-f6a1b2c3d4e5`, applied on top of the
  spine revision `2026_10_14_0001-e5c2b7f19a04`.

## State ownership

| Concern | Owner |
|---|---|
| Teaching order, anchors, presentation | Frontend definition list + ledger |
| Reward order, completion targets, payouts, claim gating | Backend catalog |

Tap and inspection lessons advance by Continue; objective-backed lessons advance by claim or
Skip step. Selection changes, navigation and background polling never count as acknowledgement.

## Acceptance criteria

- Spotlight an available action; show waiting, locked, unavailable or unaffordable work without
  dim.
- Preconditions cover eligibility, room space, placement, caps, supplies and prerequisites.
- One prominent guide action at a time; incidents, resource recovery and player-opened dialogs
  keep priority.
- A step normally takes under two minutes of interaction; orientation aims at 3–6 minutes.
- The player explicitly claims server rewards; a tap never pays and never marks a server
  objective claimed.
- Already-built rooms, skipped steps and migrated progress have deliberate completion rules;
  replaying and reloading never replay a reward.

## Remaining validation

Not yet verified end-to-end — record before sign-off:

- Full-seed resource stability across a 20-minute active session and a return from inactivity.
- Real-service walkthrough of the cohort migration against production-like legacy rows.
- Keyboard, touch and small-screen walkthrough of the spotlight and the Starter surface.
- A complete backend suite run; the simplification pass only covered the objective, guidance,
  alembic and seed suites.

## Deferred

Out of scope for this PR; tracked in [`../ROADMAP.md`](../ROADMAP.md).

- **Contextual first-time mechanic hints** (resources, SPECIAL, housing, departure, radio,
  medicine, loot, quests, training, crafting) with their dedupe and arbitration rules.
- **Timed Undo** for Skip step; Help replay is the recovery route for now.
- **Later chapters** (Medbay, Science Lab, Office quests, Workshops, Training, 50+ vault) as
  contextual lessons — the Briefing owns the next action until something is actionable.
- A dedicated `exploration_id` on the departure event.
