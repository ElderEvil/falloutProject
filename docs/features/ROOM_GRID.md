# Room Grid — Requirements Reset

> **Status:** Product requirements captured after reverting the experimental
> room-grid branch. The committed baseline is the visual reference.

## Preserve the baseline

The existing room-grid presentation was close to the intended result. Future
changes must not alter room assets, sprite selection, image aspect/cropping, or
the established room footprint without an explicit design decision.

The room tile/frame may be tuned independently for readability, but the visual
room image must remain the same size and treatment as the baseline.

## Grid shape

- Keep the compact vault dimensions currently used by the UI.
- Keep room placement and occupancy calculations consistent with the committed
  backend coordinate contract.
- Do not introduce a second “rendered grid” contract in the frontend.
- A room’s visual footprint and its stored size are separate concerns until the
  size convention is explicitly finalized.

## Elevator rule

Elevators have one purpose in this version: unlocking a level.

- A level is available for room construction only when it has an elevator.
- There is no horizontal elevator topology requirement; rooms may be placed
  anywhere on an unlocked level.
- Do not require rooms to be adjacent to, aligned with, or connected to a
  particular elevator column.
- Destroying the only elevator on a level containing rooms must be rejected, or
  the level must be locked before the destructive action completes.

This is a level-unlock rule, not a room-footprint or image-layout rule.

## Capacity rule

Do not infer dweller capacity from the number of visual cells. The application
has several distinct capacities:

- assignable worker/training slots;
- Living room population capacity;
- production/storage capacity; and
- tier-dependent production or training effects.

Each must use its own named rule. In particular, do not replace all capacity
logic with `size * 2`. Room tier must be included wherever the existing game
formula defines a tier-dependent capacity, while worker slots must follow the
room-size rules used by the committed backend.

Frontend labels, drag-and-drop validation, training capacity, assignment
services, and backend capacity checks must agree for the same room and tier.

## Data and migration safety

Do not rewrite existing vault coordinates, room sizes, or room images until the
size/capacity convention has been approved and covered by migration tests. A CSS
change cannot repair persisted rooms that were created under a different grid
contract.

## Acceptance checks

- Compare the new UI against the committed baseline at the same viewport.
- Verify room images and their dimensions are unchanged.
- Verify the room frame has the intended larger baseline size.
- Build a room on an elevator-unlocked level at a non-elevator column.
- Reject building on a level with no elevator.
- Verify removing the only elevator from an occupied level is blocked.
- Verify worker, population, production, and training capacities independently
  at tiers 1, 2, and 3.
- Run frontend lint, typecheck, and tests plus the relevant backend tests before
  accepting any implementation change.
