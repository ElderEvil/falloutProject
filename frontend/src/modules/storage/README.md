# Storage

Vault storage and inventory item management module. Provides a storage view with item cards and a service layer for inventory operations. Uses a flat routes.ts file instead of the standard index.ts pattern.

## Routes

- `/vault/:id/storage` — StorageView

## Key Files

- `views/StorageView.vue` — vault storage inventory view
- `components/StorageItemCard.vue` — individual storage item card
- `services/storageService.ts` — storage API service layer
- `routes.ts` — route definitions (flat file, no routes/ directory)
