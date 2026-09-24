# Raw native controls — accounting

The shadcn-vue migration replaced the hand-rolled `U*` primitive layer with the vendored
`core/components/ui/` set. Raw native controls in feature code are migrated **at the call site**
(the a11y payoff is per call site, not automatic), so the migration's definition of done requires
that the ones which intentionally remain are *accounted for* rather than silently left behind.

This file is that accounting. It covers `frontend/src/modules/**/*.vue` only — the dev-only
`core/views/UiCatalogView.vue` is a fixture and is out of scope.

**Snapshot:** 94 controls across 48 files, down from ~150 before the migration. No `<dialog>`
remains; `<select>` / `<textarea>` / `<table>` are down to 0 / 2 / 1.

## Why they remain

| Reason | Meaning | Controls |
|---|---|---|
| `bespoke` | Carries custom scoped CSS and/or structural test selectors (e.g. grid/drop-target/toggle visuals). Swapping in `Button` is a **redesign, not a migration**, so it is deferred to the screen that owns the styling. | 75 `<button>` across 40 files |
| `menu` | `role="menuitem"` rows inside a custom popup (overflow menu, nav dropdown, notification list) that want a `DropdownMenu` primitive — not vendored. | 10 `<button>` (`DwellerOverflowMenu`, `NavBar`, `NotificationBell`) |
| `checkbox` | No `Checkbox` / `Switch` primitive is vendored. These are `sr-only` peer-styled inputs driving a custom visual. | `QuestsView`, `HomeView`, `CraftingPanel` (`HomeView` is already documented inline) |
| `textarea` | No `Textarea` primitive is vendored. | `ProfileEditor` ×2 |
| `table` | No `Table` primitive is vendored. | `DwellersTable` |
| `label-wrap` | `<label>` wrapping a **custom control** (peer checkbox / slider), i.e. not a standalone form label. | `HomeView`, `QuestsView`, `DwellerAppearanceEditor` |

## Per-file inventory

| File (`src/modules/…`) | Controls | Reason |
|---|---|---|
| `profile/views/PreferencesView.vue` | 3 button | bespoke |
| `dwellers/components/DwellerDisplayControls.vue` | 8 button | bespoke |
| `dwellers/components/FamilyTreePanel.vue` | 6 button | bespoke |
| `rooms/components/RoomPreviewSection.vue` | 6 button | bespoke |
| `profile/components/ProfileEditor.vue` | 2 textarea | textarea |
| `social/components/relationships/RelationshipCard.vue` | 4 button | bespoke |
| `vault/components/shell/NavBar.vue` | 4 button | menu |
| `dwellers/components/DwellerOverflowMenu.vue` | 3 button | menu |
| `map/components/MarkerListPanel.vue` | 3 button | bespoke |
| `rooms/components/RoomGridCell.vue` | 3 button | bespoke |
| `vault/components/shell/NotificationBell.vue` | 3 button | menu |
| `dwellers/components/DwellerAppearanceEditor.vue` | 1 button, 1 label | bespoke + label-wrap |
| `dwellers/components/DwellerEquipment.vue` | 2 button | bespoke |
| `dwellers/components/grid/DwellerGridItem.vue` | 2 button | bespoke |
| `dwellers/components/table/DwellersTable.vue` | 1 button, 1 table | table |
| `exploration/components/ExplorerCard.vue` | 2 button | bespoke |
| `exploration/components/ExplorerNavbar.vue` | 2 button | bespoke |
| `map/components/MarkerDetailModal.vue` | 2 button | bespoke |
| `profile/views/ChangelogView.vue` | 1 button | bespoke |
| `progression/views/QuestsView.vue` | 1 input, 1 label | checkbox |
| `rooms/components/ArenaFighterSlot.vue` | 2 button | bespoke |
| `rooms/components/RadioControls.vue` | 2 button | bespoke |
| `vault/components/shell/GameControlPanel.vue` | 2 button | bespoke |
| `vault/views/HomeView.vue` | 1 input, 1 label | checkbox |
| `combat/components/incidents/IncidentAlert.vue` | 1 button | bespoke |
| `crafting/components/CraftingPanel.vue` | 1 input | checkbox |
| `dwellers/components/DwellerFilterGroup.vue` | 1 button | bespoke |
| `dwellers/components/DwellerFilterPanel.vue` | 1 button | bespoke |
| `dwellers/components/DwellersList.vue` | 1 button | bespoke |
| `dwellers/components/cards/DwellerCard.vue` | 1 button | bespoke |
| `dwellers/components/modals/TrainingStartModal.vue` | 1 button | bespoke |
| `exploration/components/ExplorationDurationModal.vue` | 1 button | bespoke |
| `exploration/components/ExplorationEventLog.vue` | 1 button | bespoke |
| `exploration/components/ExplorationRewardsModal.vue` | 1 button | bespoke |
| `exploration/views/ExplorationView.vue` | 1 button | bespoke |
| `progression/components/ObjectiveCard.vue` | 1 button | bespoke |
| `progression/components/PartySelectionModal.vue` | 1 button | bespoke |
| `progression/components/training/TrainingQueuePanel.vue` | 1 button | bespoke |
| `progression/components/training/TrainingRoomModal.vue` | 1 button | bespoke |
| `progression/views/TrainingView.vue` | 1 button | bespoke |
| `rooms/components/DwellerList.vue` | 1 button | bespoke |
| `rooms/components/IncidentBattleLog.vue` | 1 button | bespoke |
| `rooms/components/RoomDwellerCard.vue` | 1 button | bespoke |
| `rooms/components/RoomItem.vue` | 1 button | bespoke |
| `rooms/components/RoomMenu.vue` | 1 button | bespoke |
| `rooms/components/RoomTrainingSection.vue` | 1 button | bespoke |
| `social/components/relationships/ChildChip.vue` | 1 button | bespoke |
| `social/components/relationships/DwellerChildCard.vue` | 1 button | bespoke |

## Driving it to zero

Two levers, both scoped separately from this accounting:

1. **Vendor the missing primitives** — `Textarea`, `Checkbox`/`Switch`, `Table`, and `DropdownMenu`
   are all dependency-free in this stack (plain markup or Reka UI, already installed). Vendoring them
   unblocks the `checkbox` / `textarea` / `table` / `menu` groups above.
2. **Migrate the `bespoke` buttons per screen** — convert them to `Button` only as each screen's
   scoped CSS and structural test selectors are reconciled, so the styling change is reviewed with
   the screen rather than swept.

Until then, the counts above are the frozen baseline: they may shrink as files are touched, but new
raw controls should not be added where a vendored primitive exists.
