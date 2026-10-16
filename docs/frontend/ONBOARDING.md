# Spotlight onboarding

> Status: **implemented** in PR #1000, not yet released. This document records the behaviour
> that is implemented, its ownership boundaries and the checks still outstanding. Deferred
> work is summarised at the end and tracked in [`../ROADMAP.md`](../ROADMAP.md).

## Implemented behaviour

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
- **Yields to dialogs.** The guide reads a shared blocking-overlay signal
  (`core/composables/useBlockingOverlay.ts`) instead of sniffing the DOM for `[role="dialog"]`.
  Both the card and the cut-out suspend while a player-opened dialog, incident dialog,
  confirmation or the About help owns attention, and the same pending lesson resumes on
  dismissal without acknowledging, skipping or completing it. Nested dialogs keep it suspended
  until the whole stack closes, and an overlay torn down by navigation releases immediately.
  Tooltips and ordinary popovers deliberately do not suspend it. `TerminalModal` registers once
  for every Reka dialog shell; `RoomMenu`, `NotificationBell`, `DwellerBulkActions`,
  `ChangelogModal` and `PageHelp` register their own non-`TerminalModal` dialogs.
- **Responsive placement.** The card sits on the opposite side of the highlighted control so it
  never covers what it explains. When the control is below the fold the card moves above it and
  collapses to its title (the lesson is preserved); a manual collapse/expand toggle wins until
  the lesson changes, so a background poll never reopens the card, moves focus or re-announces
  unchanged copy. When the control is on the current page but out of view, the guide offers an
  explicit **Show control** action that scrolls only when clicked; navigating to the route you
  are already on is not offered.

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
| "Is a blocking overlay open?" | `core/composables/useBlockingOverlay.ts` (dialogs register; the guide reads) |

Tap and inspection lessons advance by Continue; objective-backed lessons advance by claim or
Skip step. Selection changes, navigation and background polling never count as acknowledgement.
The overlay signal carries only that boolean — lesson selection, placement and progress stay in
the onboarding module.

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

## Validation record

Run for the simplification pass:

- Backend: `ruff` clean, single Alembic head, **127 passed** (alembic, objective
  CRUD/claim/guidance/evaluators, seed integrity, `test_db`).
- Frontend: `typecheck` + `lint` clean, **114 passed** (`OnboardingSpotlight`,
  `useOnboardingState` + persistence, `onboardingSteps`, `ObjectivesView`, `dwellerFilter`).

Still owed before release sign-off:

- Full backend and frontend suite runs.
- Full-seed resource stability across a 20-minute active session and a return from inactivity.
- Keyboard, touch and small-screen walkthrough of the spotlight and the Starter surface.
- Real-service walkthrough of the cohort migration against production-like legacy rows.
- Browser (Playwright) coverage that actually clicks and keyboard-activates the highlighted
  control at phone width and 200% zoom, rather than asserting visibility alone.

## Deferred

Out of scope for this PR; tracked in [`../ROADMAP.md`](../ROADMAP.md).

- **Contextual first-time mechanic hints** (resources, SPECIAL, housing, departure, radio,
  medicine, loot, quests, training, crafting) with their dedupe and arbitration rules.
- **Timed Undo** for Skip step; Help replay is the recovery route for now.
- **Later chapters** (Medbay, Science Lab, Office quests, Workshops, Training, 50+ vault) as
  contextual lessons — the Briefing owns the next action until something is actionable.
- A dedicated `exploration_id` on the departure event.
