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

## Single-scene encounters

Each new spatial site visit is one complete encounter in one location. Super Duper Mart starts
inside the supermarket and resolves its raider fight there; it has no parking-lot or back-room
progression. A successful encounter adds the site's haul, marks it spent for that journey, and
resumes travel in the final combat-turn transaction. Defeat ends the encounter without site loot,
leaves the dweller alive and resumes travel. Stat checks remain available in the legacy engine for later design.

Site content owns `scene_id`; the client does not infer artwork from names or room labels.
The picker, encounter, and result use the same landscape artwork; the encounter frame crops it.
Missing artwork has a reserved neutral frame and the dweller portrait. The ordinary exploration page shows status and the journey log;
artwork belongs to the encounter. Saved room-based runs retain their original definitions and cursors;
new spatial runs persist `single_scene` in their existing flags. Legacy non-spatial journeys retain
the old rooms for original sites; newly authored sites use the new combat flow.
The original five sites' `rooms` trees are frozen compatibility data for saved runs. Their duplicated
text is migration debt; edit `encounter` for new visits and preserve legacy room identifiers/cursors.
New sites author only `encounter`.

`WastelandScene` reserves a 16:9 landscape or 50:37 encounter frame before images load. The explorer
occupies 44% of that frame's height, with a 1:2 portrait frame. The landscape image is contained in
the 16:9 frame and cropped with `object-cover` in the 50:37 encounter frame. Captions sit on an opaque
semantic surface, and failed images preserve the frame, caption, and explorer. Each scene ships one
640px and one 1280px landscape WebP; browsers choose through `srcset`. Content-addressed WebPs receive
immutable cache headers.

The eight backgrounds were supplied by the maintainer in the local
`fallout-asset-batch/backgrounds/` batch. No artwork was generated or recolored for this integration.
`models/wasteland-scenes.json` records relative input names, source SHA-256 values, output paths, and
dimensions. Reimport from the repository root with:

```bash
uv run --project backend python scripts/import_wasteland_scenes.py /path/to/backgrounds
```

Commit the generated manifest and `frontend/public/assets/wasteland-scenes/` together. All five
locations are available under `/dev/wasteland-scenes` in the development menu; the browser fixture
mounts that same preview component at `/tests/e2e/fixtures/wasteland-scenes.html`. Every supplied location is assigned to at least one site through its `scene_id`.
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

### Playable local discovery scenario

From `backend/`, create a scout already returning from a discovered site:

```bash
uv run fo-cli expedition-scenario setup --user-email YOUR_LOCAL_EMAIL --dweller-level 10 --duration-hours 24 --special 7 --discovered-site super_duper_mart
```

This creates a dedicated boosted vault and a level-10 scout, stages the saved trail through the
supermarket, and sends the real discovery report. The command prints a link that opens its picker.
Open the notification bell, review the site, enter an encounter, and reload to check reconnecting.
Travel pauses after entry; resolving or retreating resumes it. The return deadline follows the actual
site-to-vault travel distance. Setup fast-forwards development data; it does not simulate outbound
combat. Vault/scout/departure setup and discovery reporting are separate committed stages.

To use a dweller already in a vault, add `--vault-id VAULT_UUID --dweller-id DWELLER_UUID`.
This preserves that dweller's level and SPECIAL and does not create another scout. The usual dispatch
rules apply, including adulthood, health, and site level requirements.

### Vault 1 test scenario

Creating a vault numbered 1 pre-selects the `vault_1_test` scenario and Boosted Start; both stay
toggleable. The scenario seeds one named dweller per non-scenario site, fast-forwards each journey
past its site, and sends the real discovery report, so the bell lists every shipped site while each
dweller keeps a long outbound window before turning home. Starter objectives are skipped.

The same seeding is available from `backend/`:

```bash
uv run fo-cli expedition-scenario vault1 --user-email YOUR_LOCAL_EMAIL
```

`--sites` limits the picked sites, `--dwellers` caps the count (at most one per site), and
`--outbound-hours` sets the window left after the reports arrive.

### Single-scene combat

Spatial site encounters use `SiteCombatScene` and the shared Arena ring/playback. Fight starts alternating
server-authoritative turns while the modal is open; weapon skills activate from the existing meter/target
controls. Entry first shows a compact briefing. Fight expands to a viewport-sized encounter, using the
location’s landscape artwork, cropped for the mobile encounter frame. Reconnects to an ongoing
fight retain the expanded view. Closing stops advancing turns. Reconnect restores HP, skill charge, turn and enemy roster.
Each request sends its expected round so delayed/duplicate requests cannot repeat an attack.

Site definitions choose artwork explicitly and validate enemies against the scene's pool. Desert scenes
use wildlife, raiders, and super mutants; interior scenes use locally appropriate hostiles. Site-only power/HP
multipliers keep the first release forgiving without changing Arena matches. Defeat is terminal, gives
no site loot and resumes travel with the dweller alive. Stat checks remain in the legacy engine for later design.

The expanded battlefield sizes itself against its actual modal container, preserving the scene ratio
without covering the footer. Creature/dweller portraits also shrink for short windows. The journal
reuses Arena's `BattleLog` (turn labels, skill icons, grouped rows and scroll-to-newest); it has its
own scroll area beside the scene on desktop and below it on phones. `/dev/wasteland-scenes` includes
a read-only combat layout preview using the real encounter modal and a long journal.
