# Dweller-first assignment (#981)

The maintainer chose the dweller-first option on 2026-10-13. This applies the issue's
player-task, consequence-preview, consistency and specific-feedback principles to an
existing flow while retaining the CRT interface.

## Current journey and observed friction

Source inspection: UnassignedDwellers already isolates available dwellers, roster filters
already support idle status, the detail card already has an Assign action, and the room
picker already ranks dwellers by its SPECIAL (PR #963). Reuse those surfaces.

Before this change: find an idle dweller → open detail → click Assign. The adult action
calls autoAssignToRoom immediately; the youth action chooses a production room automatically.
The player cannot compare rooms, review occupancy or select the destination first. The
success message describes a best match rather than naming a chosen room. Changing one's
mind requires unassignment and navigation to room management.

After: find an idle dweller → open detail → Choose room → compare/select → Confirm assignment
→ a named toast and refreshed detail. Assignment is deliberately an extra decision:
we are optimizing player control and predictability, not claiming fewer clicks or faster
completion. Both paths start from the same roster/detail surfaces; the new path keeps room
comparison and confirmation in one modal with no additional route change.

## Complete prototype and layout

The delivered RoomAssignmentModal is a working prototype wired to the existing manual
assignment endpoint, not a detached mockup. It shows real rooms/roster data in the game.

```text
CHOOSE A PRODUCTION ROOM
Martha Dewey · Worker
Compare the SPECIAL each room uses. Highest effective stat appears first.

[✓ Science Lab · Tier 1          Intelligence 8 · 0/2 workers]
[  Power Generator · Tier 1          Strength 3 · 0/2 workers]
[  Water Treatment · Tier 1        Perception 4 · 2/2 workers] disabled
   All worker slots are occupied.

Science Lab: Intelligence 8 contributes to this room's production.
Assignment changes only when you confirm.

[Cancel] [Confirm assignment]
```

Room identity/tier stays left; relevant stat/worker occupancy stays right and wraps on
mobile. Selection has a visible check and aria-pressed state. Names are never the only
accessible signal: each choice's accessible name includes tier, stat and occupancy.

Reuse TerminalModal/Dialog focus management, Button variants, theme/surface/muted/danger
tokens, getAbilityConfig, getSpecialBreakdown, getTrainingRoomCapacity, RoomStore and
DwellerManagementStore. Effective SPECIAL uses the existing base/identity/outfit/pet
resolver, not another formula. The complete roster is fetched independently of the
player's current list filters, so occupancy does not undercount a filtered-out worker.

KISS/YAGNI: the first comparison covers production work and apprentices. Training and
Arena keep their existing dedicated controls. No new API, production estimate, wizard,
search system, design-system primitive, or reimplementation of server eligibility.
Existing loaders gain opt-in error propagation for this explicit user operation, leaving
background callers unchanged. Submission uses existing service/store error handling.

## State contract

| State | Visible behavior |
|---|---|
| loading | rooms and occupancy loading status; selection/confirmation unavailable |
| selected | check + aria-pressed, named consequence text, explicit confirmation |
| disabled | occupied worker slots or apprentice slot, with readable explanation |
| unavailable dweller | away/dead/already assigned explanation; no assignment |
| empty | build a production room guidance, distinct from network failure |
| load error | specific alert and retry; never claim the vault is empty |
| submit error | specific server restriction, retain selection, allow retry/reselection |
| success | “Martha Dewey assigned to Science Lab” toast, close, refreshed detail |
| busy submit | block duplicate confirmation/cancel buttons during the request |

The server remains authoritative. Occupancy is a snapshot: a source audit found manual
move_to lacked the automatic path's transactional worker-capacity enforcement.
PR #1005 now enforces it for manual and bulk assignments; stale UI choices can
still receive a server conflict, which stays visible without losing selection.

## Evaluation and browser evidence

Chromium review rendered the actual action component and modal with realistic fixture
rooms/dweller, including a deliberately long room name and a full room. This verifies
rendering and controls, not human task completion time or a production play session.

- At 1440×1000 the modal is 576×584; at 390×844 it fits the 390px viewport with body scroll.
  No horizontal document overflow. Long destination text initially clipped in the footer;
  a fixed “Confirm assignment” label corrected it while the full name stays in the summary
  and accessible name. [Wide](reviews/assignment-wide.webp), [narrow](reviews/assignment-narrow.webp).
- Keyboard Enter opens from the action, Space selects a room, Escape closes, and focus
  returns to the triggering action. Selected/disabled states use more than color.
- Reduced-motion media was exercised; the new UI adds no animated effects. Existing
  Dialog/CRT reduced-motion styles remain in effect.
- Text uses established high-contrast primary/muted/surface roles. The browser review
  inspected visible labels/focus; it is not a formal WCAG contrast certification.
- Browser confirmation produced the named success toast with no page errors. Unit tests
  cover effective-stat ranking, explicit confirmation, occupancy/apprenticeship, loading
  versus empty failure, retry, server errors and unavailable dwellers.

What improved is directly observable: destination choice is available, consequences and
restrictions appear before the POST, and success names the person and room. No numeric
usability targets or invented before/after timing measurements are claimed.

## Validated follow-up

[#990](https://github.com/ElderEvil/falloutProject/issues/990): add server-side transactional worker-capacity enforcement to manual moves, using the
existing policy and row locks, with a failing regression first and a competing PostgreSQL
assignment test. Keep junior slots separate. This follows from the source audit above;
production estimates and broader reward-settlement research (#928) remain separate work.

## Integration review (2026-10-15)

Updated against master after #1005. Room loading preserves the store's loaded,
failed and superseded results; a superseded room or roster request shows a retry
state instead of claiming that occupancy is loaded. While saving, Escape, outside
click and shell-close cannot dismiss/reopen the picker and submit a duplicate.
Submission conflicts retain selection and the confirmation button retries them;
the load retry button appears only when loading failed. Disabled destinations
reference their restriction text with aria-describedby; body scroll is contained.

Chromium checks at 1440×1000 and 390×844 used the actual modal and fixture data,
including a long destination and a full room. Enter opens, Space selects, Escape
returns focus to the trigger when idle, and Escape/outside click cannot dismiss
a pending POST. Each scenario sent exactly one POST and produced the named toast.
Both widths had no horizontal document overflow or page errors. Reduced-motion
preference was enabled. This is browser verification, not a human usability study.
