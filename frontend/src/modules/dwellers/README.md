# Dwellers

Dweller roster module. Provides listing, filtering, detail views, graveyard for deceased dwellers, bulk actions, and statistics. The largest module by component count with cards, grids, modals, and stat panels.

## Routes

- `/vault/:id/dwellers` — DwellersView
- `/vault/:id/dwellers/graveyard` — GraveyardView
- `/vault/:id/dwellers/:dwellerId` — DwellerDetailView

## Key Files

- `views/DwellersView.vue` — main dweller listing with filtering
- `views/DwellerDetailView.vue` — individual dweller detail page
- `views/GraveyardView.vue` — deceased dweller memorial view
- `stores/dweller.ts` — dweller roster state management
- `components/DwellerCard.vue` — individual dweller card
- `components/DwellerFilterPanel.vue` — filtering sidebar
- `components/DwellerBulkActions.vue` — bulk selection actions
- `components/DwellerAppearance.vue` — dweller visual appearance display
- `components/DwellerEquipment.vue` — equipped items display
- `components/stats/` — dweller statistics components
- `models/` — dweller type definitions
