# Radiation System — Mechanics + UI (Red Health Segment)

> **Status:** Plan — branch `feat/radiation-mechanics-ui`. Full slice: mechanics + UI.
> Related: `EXPLORATION_SYSTEM.md`, `RESOURCE_ECONOMY_BALANCE.md`, `DWELLER_TEMPLATES.md`
> Shelter reference: rads eat max HP from the right (red segment), healed only by RadAway.

## 1. Goal

Make radiation a real system instead of a vestigial field:

- **Mechanics:** something actually adds rads; effects and tuning are deliberate and tested.
- **UI:** every health bar shows radiation as a red segment (no more yellow-number-only display).

## 2. Current State (verified on master @ 2.71.1)

| Area | What exists | Gap |
|---|---|---|
| Field | `Dweller.radiation` (int, default 0); newborns/recycled 0 | — |
| Healing | `crud.dweller.use_radaway` removes 50% (`crud/dweller.py:514`); `POST /dwellers/{id}/use_radaway`; exploration auto-uses RadAway when rads > 30 (`exploration/event_service.py:214`) | Works, keep |
| Effects | Happiness penalty when rads > 50 (`happiness_service.py:216,360`); death at `death.radiation_death_threshold` (`game_loop.py:398`); death-cause tracking | Works, needs tuning decision (§4.1) |
| Sources | **None found.** Exploration danger templates mention "rads" (`data/exploration/event_templates.json`) but `event_generator.py` emits only `health_loss`. No incident / water-shortage path adds rads | **Core gap (Unit 1)** |
| UI | `DwellerCard.vue` shows rads as numeric yellow stat-row + RadAway button; `DwellerGridItem.vue` green-only `.health-fill`; `ExplorerSummaryCard.vue` health-width bar | **No red segment anywhere (Units 3–4)** |
| Frontend logic | `useDwellerMedicalStore.useRadaway` wired and working | Keep |

## 3. Plan

### Unit 1 — Radiation sources (core gap)

- Exploration rad events add `dweller.radiation` (endurance-mitigated, mirroring combat damage formula `max(1, base - endurance*2)` style). Touch: `exploration/event_generator.py`, `exploration/event_service.py` (`_apply_health_loss` area).
- One vault-side source: water shortage and/or incidents (owner decision, §4.2). Candidate: `resource_manager.py` (water == 0 tick) or incident service.
- Tuning via `game_config.py` (new `RadiationConfig` or extend `DeathConfig`): per-event rad range, vault-source rate.
- Tests first (repo bugfix workflow): rad event raises `radiation`; endurance reduces it.
- Success: an explorer can return glowing; a vault can accumulate rads without exploring.

### Unit 2 — Effect model (decision, §4.1)

- Recommended: keep threshold-death + happiness penalty, tune numbers only. Full Shelter model (rads eat effective max HP) rejected for now — it ripples into combat/exploration/death math.
- Success: documented thresholds + boundary tests (below/at/above death threshold, happiness at 50).

### Unit 3 — Shared `RadiationHealthBar` component

- One component: green HP fill + red rad segment, theme tokens only (no hardcoded colors; follow `DwellerBadge` `--badge-color` / `color-mix` pattern used in ChildrenList fix).
- Props: `health`, `maxHealth`, `radiation` (+ `size` if needed). Reuse, don't duplicate.
- Success: unit tests for 0 / partial / full rads; replaces ad-hoc fills (net-LOC negative).

### Unit 4 — UI integration

- `DwellerGridItem.vue` (`.health-fill`), `ExplorerSummaryCard.vue` (health width bar), `DwellerCard.vue`/detail view. Keep numeric rad readout + RadAway button in `DwellerCard` (already coherent).
- Success: red segment visible wherever HP shows; `pnpm run lint && pnpm run typecheck`; component tests green.

### Unit 5 — Balance + verification

- Re-check `RESOURCE_MEDICAL_PRODUCTION_RATE` (0.01) against new RadAway demand; adjust if explorers burn through stock.
- Full backend suite + frontend suite; manual end-to-end: trigger rad event → red segment → use RadAway → segment shrinks.

## 4. Open Decisions (owner)

1. **Effect model:** (a) threshold-death + happiness (recommended) vs (b) rads-eat-max-HP.
2. **Vault-side source:** water shortage vs incidents vs both.
3. **Passive decay:** do rads fade slowly over time, or only via RadAway? (Recommend: RadAway only — gives the stat purpose.)

## 5. Non-Goals

- No new rooms/items (no RadAway crafting); no ghoul-immunity mechanics; no changes to death-claim flow beyond thresholds.
- No endpoint shape changes (`use_radaway` contract stays).
