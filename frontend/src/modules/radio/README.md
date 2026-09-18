# Radio

Radio broadcasting module for dweller recruitment. Manages radio station operation, broadcast statistics, and manual recruit triggers to attract new dwellers to the vault.

> **Superseded:** the standalone `/vault/:id/radio` view duplicates the in-room radio panel
> (`RoomDetailModal` → radio stats + `RadioControls`, via `modules/rooms/composables/useRadioRoom.ts`).
> Slated for removal; see `docs/ROADMAP.md` → Technical Debt → Frontend.

## Routes

- `/vault/:id/radio` — RadioView (superseded, slated for removal — see note above)

## Key Files

- `views/RadioView.vue` — radio station management view
- `stores/radio.ts` — radio broadcast state management
- `components/RadioStatsPanel.vue` — broadcast statistics display
- `components/ManualRecruitButton.vue` — manual recruitment trigger
- `models/` — radio type definitions
