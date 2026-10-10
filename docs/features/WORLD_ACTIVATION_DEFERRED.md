# World Activation — Deferred (Parked)

> Status: **deferred, not abandoned.** PR #901 (`feat/world-activation`, Track C of
> the exploration/world plan) is **draft** and unmerged. Master keeps a single shared
> world. Revisit only when a world swap becomes a real, scheduled need.

## Decision log

- One shared world is enough: a world swap will **never overlap an in-flight spatial
  run** (maintainer decision, 2026-10-06).
- `generator_version` stays as **recipe identity** (fingerprint input + `/map/world`
  label). Only the version *catalog/pointer* is dropped — the int itself is cheap.
- No candidate/activation machinery on master until a candidate source exists.

## What #901 built (preserved on the branch, not merged)

- `WorldSnapshot.is_active` / `activated_at` + partial unique index (`a9b8c7d6e5f4`).
- `world_activation_service.py`: structured read-only `preview`
  (terrain/slot/home/origin deltas, conflicts, land safety, affected vaults/expeditions;
  blocked while an affected expedition is active) and atomic `activate`
  (`confirm` + `expected_active_version` stale guard, progress-preserving).
- `active_slot_coord` / `active_slot_coords` / `active_slot_placement` in
  `world_snapshot_service.py`; `_vault_origin` returning `(coord, version)` with both
  departure paths (`send_dweller`, `dispatch`) persisting the active snapshot's version.
- `get_vault_map` `player_vaults` built from the active placement.
- `WorldSnapshotAdmin` (POST+CSRF preview/activate) + `world_activation.html`.

## Why it was parked instead of merged

1. **Unreachable:** nothing in production creates a second version — `get_or_generate()`
   always uses the default recipe (v1), `WorldSnapshotAdmin` is read-only, and there is
   no CLI/seed path. So `preview`/`activate` could never run; untestable end-to-end.
2. **Half-wired:** `GET /api/v1/map/world` serves `get_or_generate()` (the default
   recipe), not the active snapshot — an activated v2's terrain would never render while
   markers/origins used v2 placements.
3. **Ambiguity cost:** the active-vs-legacy placement duality and per-run
   `world_version` pinning would become part of every world read, for a capability that
   can't be exercised. Closing the PR keeps master simple; git preserves the work, so
   "recreate later" is really "rebase later."

## How to revive it

1. Rebase `feat/world-activation` onto then-current master (expect migration
   `down_revision` drift on `a9b8c7d6e5f4`; review fixes are already in `e7c5873c`).
2. Add the missing **candidate-generation path** first (ops CLI or seed that builds a
   non-default-recipe snapshot) — without it, activation stays unreachable.
3. Wire `GET /api/v1/map/world` to the **active** snapshot, not the default recipe.
4. Decide the row model: single row + staging table, or `unique(world_id)` with an ops
   `world-regenerate` that replaces the row; keep `Exploration.world_version` pinning
   only if swaps may overlap runs (currently decided: no).
5. Re-request review; the CodeRabbit findings on #901 (origin/version pairing,
   marker agreement, blocked-reason message) are already addressed in `e7c5873c`.

## Explicitly out of scope

- `slot_coords` (legacy scatter grid) vs the snapshot's generator `slots` are still two
  coordinate systems. #901 began reconciling them via activation; dropping #901 leaves
  them as-is. Unifying placement is a separate task.
