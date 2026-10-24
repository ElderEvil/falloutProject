# Rooms

Room management module. Handles vault room grid layout, construction, production stats, upgrades, and dweller assignment. Embedded in VaultView with no standalone routes. Rich composable architecture for rendering, hover previews, radio assignment, and upgrade flows.

## Routes

- _(no dedicated routes — embedded in VaultView)_

## Key Files

- `stores/room.ts` — room state management
- `components/RoomGrid.vue` — vault room grid layout
- `components/RoomItem.vue` — individual room display
- `components/RoomDetailModal.vue` — room detail dialog
- `components/RoomIncidentDetail.vue` — live incident overlay: scene, visible battle log, batch responder actions, and a manual helper disclosure
- `components/IncidentScene.vue` — room preview with resident/helper portraits, health bars, scaled threats, containment, floating damage, and arena-style lunge/impact motion
- `components/IncidentBattleLog.vue` — incident journal rounds for the overlay
- `components/BattleLog.vue` — shared event log (optional timestamps, skill highlighting, grouping, autoscroll, live region) for arena and incident journals
- `components/RoomActions.vue` — room action buttons (upgrade, destroy)
- `components/ProductionStats.vue` — room production statistics
- `components/DwellerList.vue` — assigned dwellers list
- `components/EmptyCell.vue` — empty grid cell placeholder
- `@/core/composables/useRoomRendering.ts` — shared room-image display preference
- `composables/useRoomUpgrade.ts` — room upgrade flow
- `composables/useRoomProduction.ts` — production calculation
- `composables/useRoomDwellers.ts` — dweller assignment logic
- `models/` — room type definitions
