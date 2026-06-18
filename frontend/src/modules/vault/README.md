# Vault

Vault management module. Handles vault CRUD operations, home dashboard, resource monitoring, and happiness tracking. Includes the eagerly-loaded HomeView for fastest initial page load.

## Routes

- `/` — HomeView
- `/vault/:id` — VaultView
- `/vault/:id/happiness` — HappinessView

## Key Files

- `views/HomeView.vue` — home dashboard (eager loaded)
- `views/VaultView.vue` — main vault management view
- `views/HappinessView.vue` — happiness tracking view
- `stores/vault.ts` — vault state management
- `components/VaultList.vue` — vault listing component
- `components/HappinessDashboard.vue` — happiness metrics dashboard
- `composables/` — vault-specific composables
- `schemas/` — Zod validation schemas for vault forms
