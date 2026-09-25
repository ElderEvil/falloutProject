# Expedition Site UI

State of the interactive expedition-site UI. Only current state lives here —
release history is in `CHANGELOG.md`; the gameplay rules are in
[`docs/features/EXPEDITION_SITES_GAPS.md`](../features/EXPEDITION_SITES_GAPS.md)
and [`docs/features/INTERACTIVE_EXPEDITION_SITES.md`](../features/INTERACTIVE_EXPEDITION_SITES.md).

Where it lives: `frontend/src/modules/exploration/` — `ExpeditionSiteModal.vue`,
`stores/expeditionSite.ts`, `api/expeditionSite.ts`, plus the entry CTA and
reconnect in `views/ExplorationDetailView.vue` and the `site` journal branch in
`models/exploration.ts`.

## Done

- **Entry CTA** ("Expedition site") on an active exploration, plus
  **reconnect-on-mount**: a reload mid-run reopens the modal via `GET .../site`
  instead of stranding the player.
- **Picker**: level- and cooldown-filtered site cards (name, flavor, level and
  room-count chips) with an empty state, loading state, and inline error.
- **Room pane**: site/room progress header, flavor, node prompt, combat enemy
  preview, and choice buttons carrying a stat chip and a `success_odds`
  percentage for each option.
- **Outcome readout** sits above the next node's actions after a resolve. It is
  deliberately *not* a separate step: the backend returns the next room's node
  with the previous room's outcome, so the player reads the result and acts on
  the next node in one pane.
- **Defeat (push on / retreat)**: when `room.defeated` is set, the option
  buttons are replaced by a **Push on** action plus **Retreat** (via the shared
  confirm step). Push on replays the same pack; the room does not advance while
  defeated. This is the risk/choice loop the backend enforces.
- **Retreat confirm** uses `TerminalModalActions` ("Keep Exploring" / "Retreat").
- **Terminal banner** for `cleared` / `retreated` / `died`, with a finale-paid
  note on a clear. Closing a terminal run emits `updated` so the exploration
  haul refreshes in the normal rewards surface.
- **Remaining-time chip** (`≈Xm left`) in the room pane; below 300s it flips to
  a warning that clock expiry will force a retreat.
- **Room-pane errors**: `store.error` renders where the failed action happened
  (not only in the picker) and clears on the next action.
- **Recovery state**: a run open on a non-active exploration renders close-only
  ("This expedition has ended") with no resolve/retreat affordances — the
  backend rejects both on a non-active exploration.
- **Room scoping**: `store.room` is keyed to the exploration id; navigating
  between explorers cannot render a stale room.
- **Journal**: the `site` event type has an icon/color branch; events render
  through the shared `getEventIcon`/`getEventColor` maps.

## Rules the UI reflects (set by the backend)

- Resolve/retreat require an **active** exploration.
- A combat **defeat** leaves the run in the room (`defeated`), it does not
  advance.
- Any **terminal** run (cleared / retreated / died) puts the site on a **7-day
  per-vault cooldown**; after the window the site fully resets.
- One **open run per vault/site** — a second dweller cannot enter the same site.
- Clock expiry **force-retreats** an open run and starts the return leg, so
  remaining time is shown before the player commits.

## Open

- **Discovery prompt (the original-game flow)**: a site should be offered as a
  time-limited exploration event (Enter / Ignore with a countdown), delivered
  over SSE (`site_prompt`), rather than only the manual picker. Not built; the
  backend has no offer state yet and deferred it deliberately. Decide whether an
  offer is a run state or a separate one-use opportunity before wiring the UI.
- **Map / journal deep-link**: site discoveries could register a map marker and
  deep-link into the modal. The `site` journal event carries no `site_id` today,
  so a per-event CTA is not possible yet.
- **Accessibility pass**: give the option buttons a proper group semantic
  (`radiogroup`/`radio` or a list with `aria-describedby` for the odds), ensure
  the countdown is announced politely (`aria-live`), and confirm focus is trapped
  and restored by the dialog.
- **Mobile layout**: the room pane's chip row and two-action defeat row are tight
  at narrow widths; verify wrapping and 44px touch targets.
- **Progression surfacing**: site entry/clear/death should surface through the
  standard modal/toast path in addition to the journal entry, per the
  progression-visibility rule in `docs/backend/GAME_MECHANICS.md`.
