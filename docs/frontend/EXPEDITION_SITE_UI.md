# Expedition Site UI

Living state of the interactive expedition-site UI. Release history is in
`CHANGELOG.md`; the gameplay rules live in
[`docs/features/EXPEDITION_SITES_GAPS.md`](../features/EXPEDITION_SITES_GAPS.md).

Code: `frontend/src/modules/exploration/` — `ExpeditionSiteModal.vue`,
`stores/expeditionSite.ts`, `api/expeditionSite.ts`; entry CTA and reconnect in
`views/ExplorationDetailView.vue`; the `site` journal branch in
`models/exploration.ts`.

## Contract

`ExpeditionSiteModal`
- props: `show`, `explorationId`, `dwellerName?`, `timeRemainingSeconds?`,
  `explorationActive?` (default `true`)
- emits: `close`, `updated` (the parent refreshes the exploration so finale loot
  reaches the normal rewards surface)

`useExpeditionSiteStore`
- state: `availableSites`, `room`, `isLoading`, `error`, `currentExplorationId`
- actions: `fetchAvailableSites`, `enterSite`, `resolveNode`, `retreat`,
  `fetchCurrentRoom`, `clearError`, `reset`

## Decisions worth knowing

- **The outcome readout is not a separate step.** Resolve returns the next
  room's node together with the previous room's outcome, so the readout renders
  above the next node's actions — one pane, no "continue" round-trip.
- **Defeat hides the option buttons.** `room.defeated` swaps them for Push on /
  Retreat; push-on replays the same pack and the cursor never advances while
  defeated.
- **Recovery is close-only.** A run on a non-active exploration renders "This
  expedition has ended" with no resolve/retreat, because the backend rejects
  both — the UI must not offer an action that can only fail.
- **The room is guarded, not cleared.** The store is a singleton that survives a
  close, so the modal renders `room` only when
  `room.exploration_id === props.explorationId`. `ExplorationDetailView` watches
  `explorationId` to re-scope the store and reconnect when the router reuses the
  view for another explorer.
- **The time chip exists because expiry force-retreats.** Below 300s it warns
  that clock expiry will end the run.
- **The fight reads as a transcript, not rounds.** A resolve returns
  `outcome.combat[]` (per-enemy results) plus live `dweller_health`; the modal
  renders the pack as enemy entries with per-enemy outcomes and flashes damage
  on the HP bar. Site combat stays an atomic per-enemy roll — no rounds and no
  per-enemy HP — so it reuses `Progress` and the CRT tokens rather than the
  incident/arena battle UI, which requires combatants and round events the site
  does not model.
- **Retreat is warned.** The confirm step states that retreating puts the site
  on a 7-day cooldown (rule D2-B), which the player would otherwise not know.

## Open

- **Map / journal deep-link** — blocked: the `site` journal event carries no
  `site_id`, so a per-event CTA cannot be built yet.
- **Accessibility** — option buttons need a group semantic (`radiogroup`/`radio`,
  or a list with `aria-describedby` for the odds), a polite `aria-live` for the
  countdown, and verified focus trap/restore.
- **Progression surfacing** — site entry/clear/death should also surface via
  modal/toast, not journal-only (the `GAME_MECHANICS.md` red line).

The remaining gameplay gap — a time-limited Enter/Ignore discovery prompt over
SSE — is a backend offer-state decision, tracked in the gaps doc, not a UI task.
