# Fallout-inspired explorer perks

Implementation tracker: [#1316](https://github.com/ElderEvil/falloutProject/issues/1316).

This pilot adapts Fallout 4's Hacker and New Vegas's Terrifying Presence into authored encounter approaches. Descriptions and encounter prose are original adaptations. It does not add a D&D ruleset, skill XP, item condition or repairs.

## Player behavior

- A living adult dweller in the vault may choose one permanent, single-rank perk from level 5.
- Hacker requires trained Intelligence 4; Terrifying Presence requires trained Charisma 6. Equipment and identity bonuses do not count toward learning eligibility.
- The Perks tab in dweller details explains requirements, asks for confirmation, and displays the learned perk. Existing dwellers start with no perk; unused eligibility can be deferred.
- Selection persists an unlock notification and shows a success toast. Bell navigation opens the same dweller's Perks tab. Notification opt-outs do not cancel selection or its direct success feedback.
- The new Research Checkpoint is ordinary site content near map coordinates `(52, 48)`, offered under existing trail/discovery and site-consumption rules. Actual discovery depends on the journey; the pilot does not bypass fog, trail proximity or cooldowns.
- Hacker guarantees access to a technical cache with junk; Terrifying Presence guarantees a cache with a weapon. Other explorers can attempt a Charisma negotiation, safely salvage a smaller junk haul, or retreat. Failed negotiation produces no haul and no injury.
- Encounter loot joins the existing expedition haul and reaches storage through normal return settlement and overflow handling. Outcomes explain an existing next use: crafting or equipment comparison.

## Persistence and authority

`Dweller.selected_perk` is a nullable string on the table model, deliberately absent from public create/update bases. Perk identifiers live in `core/enums.py`; the small catalog is in `options/perks.py`; wire contracts are in `schemas/perk.py`.

`PerkService.select` owns one transaction: lock/reload the dweller, recheck current ownership and eligibility, stage the perk, stage the notification with `commit=False`, commit once, then deliver deferred notification messages. A second concurrent selection conflicts after the first commits. Selection is unavailable while exploring/questing.

New runs snapshot the chosen perk into `ExpeditionRun.flags`. Authored options declare their prerequisite and whether the outcome is guaranteed. The view explains locked options, and resolution independently enforces the prerequisite. The Research Checkpoint requires a run-and-room choice context; stale submissions cannot resolve another attempt. A completed run has no open choice to replay.

`ExpeditionService.resolve_node` remains the transaction owner for encounter changes. Branches stage existing haul/health/event writes; `_refresh_run` flushes the run before the owner's commit. Existing damage appliers stage writes, and existing legacy pending-fight retries replay the fight without re-requiring the original choice. The pilot's new failure outcome causes no damage or spending.

## Odds compatibility

The existing d20 formula and roll outcomes are unchanged. Displayed odds now cover 0–100% so a guaranteed check no longer advertises a 5% failure chance. Exhaustive die-face tests compare the projection with actual resolution across supported SPECIAL/difficulty values.

## Schema and rollout

Migration `e7a1b3c5d9f2` adds `selected_perk` with `NULL` meaning no selection and adds PostgreSQL notification label `PERK_UNLOCKED`. Apply it before starting API/workers that use the new label. The enum drift snapshot accompanies the migration.

The downgrade drops the selected-perk column but retains the PostgreSQL enum label because PostgreSQL cannot drop an individual enum value. Do not downgrade a database containing valued player selections without a preservation/recovery decision.

Frontend wire types are generated from this worktree's OpenAPI schema, without borrowing a running server's older schema. State has one Pinia owner; pending requests are invalidated when the selected dweller/vault is reloaded or authentication changes.

## Verification and remaining evidence

Tests cover eligibility, owner authorization, permanent-choice confirmation, stale frontend responses, duplicate selection, late notification-write rollback, perk-gated and ordinary encounter routes, duplicate/stale encounter resolution, late run-write rollback, and legacy expedition behavior. The optional PostgreSQL race test requires `PERK_POSTGRES_TESTS=1` and an explicitly isolated database named `fallout_perks_1316_*`; it is skipped otherwise.

Relevant commands from `backend/`:

```bash
uv run pytest app/tests/test_services/test_perk_service.py app/tests/test_services/test_perk_encounter.py app/tests/test_api/test_perks.py app/tests/test_services/test_expedition_checks.py
uv run pytest app/tests/test_services/test_expedition_engine.py app/tests/test_services/test_expedition_sites.py app/tests/test_db/test_enum_drift.py app/tests/test_architecture
```

From `frontend/`: `pnpm run lint`, `pnpm run typecheck`, `pnpm run test:run`, and `pnpm run build`.

Authenticated Chromium playtesting on 2026-11-04 used an isolated PostgreSQL database and Redis instance, a normal non-superuser account, and a standard, non-boosted vault. Two adults were prepared at level 5 with trained INT 4 / CHA 6; this does not establish first-session leveling pacing. Desktop used 1440×1000 and phone used 390×844. No HTTP responses were mocked.

- Desktop: learned Hacker, reloaded, departed, discovered and entered the checkpoint, reloaded the open encounter, confirmed intimidation was locked, and opened the terminal cache. The haul contained 45 caps and an Alarm clock.
- Phone: opened confirmation with the keyboard, verified initial focus inside the dialog, cancelled with Escape and recovered focus on Choose, then learned Terrifying Presence. Hacker was locked at the checkpoint; intimidation returned 26 caps and a Pipe pistol. Choice buttons remained reachable in the dialog's scroll region without horizontal overflow.
- Both explorers were recalled through the UI. After arrival, the normal exploration tick settled both runs; the vault balance increased from 1,000 to 1,071 caps. The Alarm clock appeared in storage. The returned Pipe pistol was equipped through the phone Equipment tab and remained equipped after reload.

Elapsed travel and return time were accelerated in this isolated fixture, using the real movement, terrain, trail/discovery and settlement services. Fog and site offers were not bypassed. The playtest caught and corrected an ambiguous destination description and a keyboard-focus loss in the initial confirmation UI; confirmation now uses the existing shared dialog. Real-time discovery frequency, level-5 acquisition pacing and reward balance still need ordinary play evidence before expanding the catalog.

Future candidates include Scrapper and Robotics Expert after relevant uses exist. Nuclear Physicist depends on the separate Power Armor/Fusion Core feature and is outside this pilot.
