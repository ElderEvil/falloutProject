# Dweller UI Updates

Status of the roster/detail UI work. Only current state lives here — release history is in `CHANGELOG.md`.

## Filter toolbar

Lands across #668 (counts/summary), #669 (URL sync) and the `feat/dweller-display-tier` branch.

### Done

- **Contextual counts** beside every normal-roster status chip, computed from `allDwellers` under the active Age/Race/Faction filters but before Status. `Dead` stays uncounted: its panel is served by `/dead`, which lists only revivable dwellers, so any number would disagree with the result. Counts are exact up to `ALL_DWELLERS_FETCH_LIMIT` (1000).
- **Zero-count chips** stay selectable and are muted rather than disabled.
- **Active-filter summary + Clear**, scoped to Status/Age/Race/Faction — never sorting, view mode or table columns.
- **Selected chip** uses the raised surface plus theme glow, the same treatment as the active view toggle. A fill (including a fixed amber one) is explicitly out: it would be the only filled control in the toolbar and would clash with the amber theme variant.
- **`:focus-visible`** rings on the chip, sort, view and clear controls, and `transition: all` replaced with explicit properties.
- **Display tier.** Sort, View and the Columns picker live in a `DwellerDisplayControls` island on the list toolbar, with `N shown` on the trailing edge — they change presentation, not the roster being filtered. The Columns picker collapses behind a `Columns N` menu so entering table mode cannot widen the toolbar.
- **URL sync.** Status/Age/Race/Faction/Sort are read from the query in setup and written back with `router.replace`, emitting only non-default keys and preserving unrelated params.
- **Age filter hidden in Dead mode**, where the dead panel ignores it.
- **Race column** in the table (badge, off by default, included in the Demographics preset).
- **Presets**: Roster, Vitals, Demographics. `Assignments` was dropped as a near-duplicate (Roster minus `level`), and a **Reset** restores the default column set — previously a preset or an unticked column replaced it with no way back.

### Open

- **Status grouping** (Vault / Away / Incident / Records). The chip order already groups by meaning; only the visual separation is missing. Use spacing, never a literal divider — it wraps unreliably.
- **Collapsible Filters block** on compact layouts, keeping active filters visible while collapsed.
- **Summary form**: `Filters (3) · Status: Working ×` with per-filter dismissal, instead of one plain label line.
- **Zero-result empty state**: a specific message ("No adult ghouls are currently training") plus a "Show all statuses" recovery action.
- **Semantic groups**: Status and Age as `radiogroup`/`radio` with roving focus. `aria-pressed` on exclusive chips is the wrong semantic. No numeric shortcuts; defer arrow keys until the group is a real radio group.

## Dweller detail page

Completed frontend-only refactor, no backend or API change. `useDwellerDetail` owns loading and actions, `DwellerDetailContainer` provides a typed context, and sections render from the `dwellerDetailSections` registry. Sections cover Profile, Appearance, Stats, Equipment and Family; pets and apprentices wait on backend support.

## Rework proposal (not decided)

Explored against a local design lab, never agreed:

- **Radiation as cause → consequence → action** in one block ("12 HP blocked… Use RadAway · 1"), and `82 / 88` with "Base 100 · 12 blocked by RAD" instead of three bare numbers. Both fit the progression-visibility rule in `GAME_MECHANICS.md`.
- **Drop the duplicated level readout** — a level bar and an XP bar currently state one fact twice.
- **Touch targets and roles**: 44px on every control, `role="status"` on action feedback, `aria-labelledby` per section. Tabs need `aria-selected`, not `aria-pressed`.
- **Fact next to its action**: group room + status + reasoning + actions, answering "should I move her?" instead of only labelling state. Feasible — `ability` is on the room schema and `getAbilityConfig` exists — but the advice must be derived from the same rule as the backend assignment-correct flag or the copy will contradict the badge.
- **Rejected**: chat + pencil replacing the overflow menu (soft-delete disappears), routing every action through a modal, gender/age demoted to plain text, and three dossier tabs instead of five.

## Identity facts: storage vs presentation

`gender`, `rarity` and `age_group` are typed enum columns; `race`, `faction` and `state_of_being` live in the `visual_attributes` JSONB the generation agent writes. That is why identity originally rendered through a second component at a different weight.

**Resolved.** All six facts now render through one `DwellerBadge` primitive, sized by context (`sm` in lists, `md` on detail), using `UTooltip` rather than a native `title`. `DwellerIdentitySignal` composes its race entries from `RACE_CONFIG_MAP` in `models/dweller.ts`, so the detail signal and the table's race badge cannot drift apart.

**Still real.**

- `visual_attributes` has no GIN index. Race and faction *are* filtered (JSONB `as_string()` predicates in `crud/dweller.py`) but unindexed, and nothing can be sorted by them.
- JSONB values are validated in the app layer instead of by the `PG_ENUM_LABELS_SNAPSHOT` enum-drift guard.
- The trio is not homogeneous: `race` and `faction` are user input, `state_of_being` is AI-derived. Promoting `race`/`faction` to columns is worth revisiting only if sorting by them becomes a product need.
