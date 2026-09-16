# Playtest Feedback — Frontend Developer Session

**Source:** Sveta Zaytseva, ~35-minute session on 17 Sep 2026 (raw log: `docs/feedback.txt`, Russian).
**Triage date:** 2026-09-17. **Status:** untriaged — nothing here is scheduled yet.

19 observations: 7 defects, 3 improvement ideas, 1 product dead-end, plus one positive note (the dweller
details page is otherwise fine).

---

## 1. Product dead-end (highest value — needs a design decision, not a fix)

**D1 — Spending money on upgrades can make quest income unreachable.**
Quests are the only income source, quests require an **Office**, and training/capacity buildings cost the same
money. Spend it all on those first and the vault can never earn again: no income → no Office → no income.
Playtester's words: *"I blocked myself."*

- **Why it matters:** it's an unrecoverable soft-lock for a new player — exactly the person least able to know
  the Office is load-bearing. It also compounds with I1 below (guidance that never arrives).
- **Options to weigh:** a guaranteed non-Office income floor (wasteland salvage / daily stipend); make the Office
  the cheapest early build and refundable; gate early spending so the first Office is always affordable; or add a
  recovery action (sell/dismantle for partial refund).
- **The vehicle already exists:** the objectives subsystem (`modules/progression/` — `ObjectiveCard`,
  `ObjectiveCompleteModal`, with assignment/evaluators/notifications behind it) is the right place to say *"build
  an Office to earn from quests"* early, and to detect a player who can no longer afford one. This is a sequencing
  and content problem in a system that already works, not a new system.
- **Ask:** a design decision first. Any fix without one risks adding a second currency-shaped problem.

## 2. Defects

| ID | Summary | Severity | Notes |
|---|---|---|---|
| B1 | Menu sometimes won't switch; the collapse arrow doesn't respond | High | Blocks navigation; reproduces intermittently |
| B2 | Site periodically freezes, buttons stop responding | High | **No console errors** — needs network/tab evidence to chase |
| B3 | Chat stopped opening | High | Was working earlier in the same session |
| B4 | Can't open dweller details from an expedition, though the affordance is there | Medium-High | Affordance exists but navigation never fires |
| B5 | Items in the inventory delete instantly, no confirmation | Medium | Destructive action with no guardrail |
| B6 | Delete-dweller modal: buttons are flush against each other | Low | Spacing/padding only |
| B7 | "Complete dossier" runs very long with no feedback | Medium | Reads as a hang rather than slow work |

**B1–B3 look like one family** — hangs without errors, intermittently. Worth investigating together, and each
needs reproduction steps plus network-panel output before anyone guesses at a cause.

**B7 is the cheapest win:** the work is genuinely slow, so say so up front (~a minute) and show progress, rather
than leaving the user to conclude it's broken.

## 3. Improvements

- **I1 — Onboarding / first-run guidance.** *"I didn't know where to start or what to do"* — despite objectives
  **already existing**: they live in `modules/progression/` with a `HomeView` presence and completion toasts via
  the notification bell. So the gap is **surfacing and sequencing, not absence**: nothing routes a brand-new player
  to the objectives view, and the objective list doesn't lead with the economy step that decides whether the vault
  can earn at all. Pairs directly with D1 — the player who doesn't know the Office matters is the one who
  soft-locks, so the first objectives should walk them to it.
- **I2 — Filters: collapse the chip rows into selectors.** Today status is a row of chip buttons (age too). The
  suggestion: one (multi-)select per dimension — status and age merged — showing choices in a dropdown, leaving
  room for further filters, **plus a "Clear filters" button**.
  - **Directly shapes parked work:** the roster-filter branch (#661, parked with faction) currently ships the
    per-status-chip pattern the playtester is arguing against. Fold this in before reviving it, and treat
    multiselect (any status, not one) as the design target.
- **I3 — Family tree redesign.** Schematic, Sims-like lineage view rather than the current presentation. Larger
  and cosmetic; no correctness claim attached.

## 4. Positive

- Dweller details page: *"I don't really see a problem there"* — only B6 (modal spacing) came out of it.

---

## Suggested order

1. **D1** (design decision — soft-lock) and **B1–B3** (intermittent hangs; same family, need repro evidence).
2. **B7**, **B4**, **B5** — small, contained, each independently shippable.
3. **I2** — fold into the parked filter work before it resumes.
4. **I1**, **I3**, **B6** — polish and onboarding.
