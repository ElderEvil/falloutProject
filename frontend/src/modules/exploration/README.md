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

## Wasteland journey and expedition artwork

Exploration details show the explorer against the desert highway or an illustration matching the last
reported location name. Returning journeys use the road scene. This presentation reads the existing
exploration snapshot; it does not add destinations, encounters, polling, or event delivery.
Super Duper Mart site rooms use the supermarket interior, with the road for its outdoor parking-lot
encounter. The roadside supply truck uses the road. Unknown sites retain their existing text layout.
Combat nodes use the supplied battleback framing; other nodes use the landscape. Artwork never
changes decisions, enemy rosters, or rewards, and a room belonging to another exploration stays hidden.

`WastelandScene` reserves a 16:9 landscape or 50:37 battleback frame before images load. The explorer
occupies 44% of that frame's height, with a 1:2 portrait frame. Original artwork is contained without
cropping. Captions sit on an opaque semantic surface, and failed images preserve the frame, caption,
and explorer. Landscape variants are 640/1280 pixels wide; battlebacks are 500/1000 pixels wide.
Browsers choose through `srcset`. Content-addressed WebPs receive immutable cache headers.

The five backgrounds and five battlebacks were supplied by the maintainer in the local
`fallout-asset-batch/backgrounds/` batch. No artwork was generated or recolored for this integration.
`models/wasteland-scenes.json` records relative input names, source SHA-256 values, output paths, and
dimensions. Reimport from the repository root with:

```bash
uv run --project backend python scripts/import_wasteland_scenes.py /path/to/backgrounds
```

Commit the generated manifest and `frontend/public/assets/wasteland-scenes/` together. All five
locations are available under `/dev/wasteland-scenes` in the development menu; the browser fixture
mounts that same preview component at `/tests/e2e/fixtures/wasteland-scenes.html`. Generic research
facilities are not depicted as arctic stations, and cinemas are not depicted as amusement parks.
Scene layout checks run at 390px and 1280px in Chromium and the focused Firefox scene project.

## Discovered site reports

The spatial exploration tick records `site_found` journey events and matching exploration-update
notifications once per journey/site. Discovery follows the saved trail and level gates; it does not
pause travel. Existing legacy non-spatial journeys keep their catalog picker without discovery alerts.
The journey event and inbox row share one transaction under the existing vault/exploration locks.
Movement is an earlier committed stage; a failed report is retried on the next tick. External delivery
runs only after the report commit and respects notification preferences.

The bell surfaces a toast and links to `/vault/:id/exploration/:explorationId?siteId=:siteId`.
That link opens the picker for review without entering automatically. A reported site remains offered
on the return leg until arrival home; cleared sites are spent for that journey. The backend checks
arrival under the entry lock even before the tick finalizes the return. An already entered spatial
encounter pauses travel and remains reconnectable while open. Historical reports remain readable
when offers expire. Party missions waiting at their destinations are a separate follow-up (#1193).
