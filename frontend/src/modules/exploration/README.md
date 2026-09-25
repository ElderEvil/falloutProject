# Exploration

Wasteland exploration module. Tracks exploration events via timeline, manages rewards through modal dialogs, and displays quest party cards for dwellers sent into the wasteland.

## Routes

- `/vault/:id/exploration` — ExplorationView
- `/vault/:id/exploration/:explorationId` — ExplorationDetailView

## Key Files

- `views/ExplorationView.vue` — main exploration listing
- `views/ExplorationDetailView.vue` — single exploration detail page
- `stores/exploration.ts` — exploration state management
- `stores/expeditionSite.ts` — interactive expedition site run state (picker/room/outcome)
- `api/expeditionSite.ts` — expedition site API client + wire types
- `components/ExplorationEventLog.vue` — chronological event display
- `components/ExplorationRewardsModal.vue` — reward distribution modal
- `components/ExpeditionSiteModal.vue` — interactive expedition site modal (enter, resolve, retreat)
- `components/ExplorerCard.vue` — explorer status card
- `components/QuestPartyCard.vue` — quest party summary card
- `components/WastelandPanel.vue` — wasteland overview panel
