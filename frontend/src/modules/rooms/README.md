# Rooms

Room management module. Handles vault room grid layout, construction, production stats, upgrades, and dweller assignment. Embedded in VaultView with no standalone routes. Rich composable architecture for rendering, hover previews, radio assignment, and upgrade flows.

## Routes

- _(no dedicated routes — embedded in VaultView)_

## Key Files

- `stores/room.ts` — room state management
- `components/RoomGrid.vue` — vault room grid layout
- `components/RoomItem.vue` — individual room display
- `components/RoomDetailModal.vue` — room detail dialog
- `components/RoomActions.vue` — room action buttons (upgrade, destroy)
- `components/ProductionStats.vue` — room production statistics
- `components/RoomInfoGrid.vue` — room information grid
- `components/DwellerList.vue` — assigned dwellers list
- `components/EmptyCell.vue` — empty grid cell placeholder
- `composables/useRoomRendering.ts` — room grid rendering logic
- `composables/useRoomUpgrade.ts` — room upgrade flow
- `composables/useRoomProduction.ts` — production calculation
- `composables/useRoomDwellers.ts` — dweller assignment logic
- `models/` — room type definitions
