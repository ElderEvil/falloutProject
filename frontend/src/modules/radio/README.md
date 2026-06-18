# Radio

Radio broadcasting module for dweller recruitment. Manages radio station operation, broadcast statistics, and manual recruit triggers to attract new dwellers to the vault.

## Routes

- `/vault/:id/radio` — RadioView

## Key Files

- `views/RadioView.vue` — radio station management view
- `stores/radio.ts` — radio broadcast state management
- `components/RadioStatsPanel.vue` — broadcast statistics display
- `components/ManualRecruitButton.vue` — manual recruitment trigger
- `models/` — radio type definitions
