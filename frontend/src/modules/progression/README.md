# Progression

Dweller progression module covering training queues, quest management, and vault objectives. Includes training room assignment, quest party selection, and objective tracking with debug overlays.

## Routes

- `/vault/:id/training` — TrainingView
- `/vault/:id/quests` — QuestsView
- `/vault/:id/quests/:questId` — QuestDetailView
- `/vault/:id/objectives` — ObjectivesView

## Key Files

- `views/TrainingView.vue` — training queue and assignment view
- `views/QuestsView.vue` — quest listing view
- `views/QuestDetailView.vue` — single quest detail page
- `views/ObjectivesView.vue` — vault objectives tracking view
- `stores/training.ts` — training state management
- `stores/quest.ts` — quest state management
- `stores/objectives.ts` — objectives state management
- `components/ObjectiveCard.vue` — objective display card
- `components/QuestCard.vue` — quest summary card
- `components/PartySelectionModal.vue` — quest party selection dialog
- `components/training/TrainingQueuePanel.vue` — training queue display
- `components/training/TrainingRoomModal.vue` — training room assignment modal
