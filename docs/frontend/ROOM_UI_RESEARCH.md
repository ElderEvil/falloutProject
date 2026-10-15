# Room UI: scenes and management

Research date: 2026-10-15. Code baseline: `92af9103` on `feat/arena-ui-clarity`.
This is a code, component, asset, and documentation audit—not a measured usability or performance study.
Recommendations below are proposals, not implemented changes.

## Direction

Make the preview the place where the room feels alive. Keep a compact, room-specific management area
below it. Start with **ambient room animation and simple characters**, as requested; full character
animation is a separate experiment, not a prerequisite for improving room UI.

The common structure should be recognizable, but the management content should follow the room's
purpose. Arena needs team composition and match controls. Response Station needs hazard-team information,
equipment visibility, and active/reserve management. A production room does not need either interface.

Preserve the decisions already made for Arena: preview first, assignment through preview slots, compact
underlined Duel/Brawl/Hunt tabs, informative bench cards, and management locked during a match. Do not
bring back numbered steps, a mode dropdown, a second assignment toolbar, or a redundant assigned count.

```text
Room detail
├── Header: name, level, essential room state
├── Scene: room art + ambient layers + simple occupants + contextual effects
│   └── Accessible assignment/inspection targets where appropriate
├── Management: Arena OR Response Station OR production/training/crafting/...
├── Journal/results when relevant
└── Shared room actions: upgrade / unassign / destroy
```

On narrow screens, keep this order. Begin with one scroll surface rather than a fixed-height scene
and several nested scrolling panels. An optional desktop side panel can be evaluated later if actual
team-management tasks benefit; it should not make the scene or controls unusably small.

## What we have today

Paths in this document are relative to the repository root unless linked.

| Surface | Current implementation | Keep / improve |
|---|---|---|
| Detail shell | `RoomDetailModal.vue`, `RoomDetailHeader.vue`, `TerminalModal` | Keep shell, title, error boundary, and domain composition. Reduce repeated metadata. |
| Ordinary room preview | `RoomPreviewSection.vue` | Keep image fallbacks and assignment interactions. Separate room composition from the current bottom row of portraits/icons. |
| Production | `ProductionStats.vue`, `useRoomProduction` | Keep calculations; use a compact responsive facts grid. Scene can convey activity, while numbers remain in management. |
| Capacity/basic rooms | Generic preview and `RoomActions.vue` | Keep simple. A quiet room does not need invented activity, extra tabs, or a dashboard. |
| Radio | `RadioControls.vue` and radio statistics | Keep consequential mode/recruitment controls. Avoid stating the current mode twice. |
| Training | `RoomTrainingSection.vue`, shared `TrainingProgressCard` | Keep trainee eligibility, progress, collect/cancel actions. Ambient activity must reflect actual training state. |
| Crafting | Crafting module's `CraftingPanel.vue` | Keep recipes, queue, progress, and cancellation in the crafting module. Do not move job logic into the scene. |
| Overseer's Office | `OverseerBriefing.vue` | Keep the briefing as its own management content; optional console ambience can support it. |
| Arena | `ArenaRoomDetail.vue`, `ArenaModal.vue`, fighter/creature slots | Keep match behavior. Scene and combat cards currently represent participants separately; eventually give the scene ownership of the visual encounter. |
| Response Station | `ResponseStationDetail.vue`, shared `ResponseTeamsPanel.vue` | Keep active/reserve management and protection facts. Add clear information zones without conflating staffing and team membership. |
| Active incident | `RoomIncidentDetail.vue`, `IncidentScene.vue`, journal adapter | Keep responder actions and authoritative incident state. Reuse presentation pieces after the first scene pilot. |
| Aftermath | `IncidentAftermath.vue` | Preserve reward review, overflow decisions, and dismissal. Results are gameplay, not disposable decoration. |
| Vault grid / build menu | `RoomGridCell.vue`, `RoomMenu.vue` | Keep grid lightweight and static. Build-menu accessibility is a separate cleanup, not a reason to animate every tile. |

The room section registry already centralizes composition in
[`roomParts.ts`](../../frontend/src/modules/rooms/models/roomParts.ts). Arena currently takes precedence
over incidents; other rooms replace their ordinary sections with incident or aftermath content.
Keeping the scene visible while an incident occurs changes that composition policy: make it an explicit
follow-up decision, not an accidental consequence of moving components.

## Reuse first

| Existing building block | Recommended use |
|---|---|
| `TerminalModal` and local shadcn-vue Dialog | Keep modal behavior and accessible title/focus handling in one place. |
| Local Card, Button, Badge, Progress, Tabs, Alert, Skeleton, Tooltip | Shared management vocabulary; use semantic theme tokens and existing variants. |
| `DwellerPortrait` | Compact identity in management, assignment pickers, and simple initial scene markers. Portraits are not full-body sprite assets. |
| `RoomPreviewSection` assignment events | Preserve inspect / assign worker / assign apprentice / unassign semantics while improving scene presentation. |
| `useFallbackImage` and `roomScenes.ts` | Keep curated scene → fallback image → empty state behavior. A missing animation layer must not break assignment. |
| `ResponseTeamsPanel` and `ResponseTeamMemberRow` | Already reusable between station and dedicated team page. Extend these instead of making station-only duplicate rosters. |
| `BattleLog` | Already shared by Arena and incidents, including grouped messages and follow-newest behavior. Keep the incident adapter. |
| `RoomActions` | Keep common upgrade/unassign/destroy presentation, with explicit disabled reasons from the room's controller. |
| `usePolling` | Keep request overlap protection and lifecycle cleanup. Render animation locally between state updates. |
| `useVisualEffects` | Reuse the reduced-motion preference pattern. Do not equate a room-animation toggle with CRT flicker or pausing the game. |

The installed shadcn-vue set already covers the first iteration. Card supplies visual grouping; Tabs
express actual alternate panels such as Arena modes. Neither requires every small statistic to become
its own card. See the official [Card](https://www.shadcn-vue.com/docs/components/card) and
[Tabs](https://www.shadcn-vue.com/docs/components/tabs) documentation.

Use plain semantic lists and description lists for compact data. Native `details` can hide secondary
explanations. Accordion, Collapsible, Popover, and ScrollArea are not currently installed locally; add a
component only when a concrete interaction requires it. Do not add Nuxt UI or a second component library.

## Consolidate or drop

1. **Duplicate facts:** Response Station repeats its stationed count in a header badge and a statistics
   cell. Keep one clear staffing fact; spend the space on useful readiness information.
2. **Inconsistent participant chrome:** fighter slots use shared Card presentation while creature slots
   retain a custom card and overlay picker. Align spacing, health, selection, and focus treatment;
   keep their different selection rules. Do not create a universal participant card with dozens of props.
3. **Two visual battlefields:** Arena's preview shows assigned dwellers while separate cards carry live
   combat HP. In the eventual encounter scene, render selected fighters and bots there; keep compact
   identities and editing controls below. Room assignment and fighter selection remain distinct actions.
4. **Misleading names:** `ArenaModal` is embedded content, not a modal; `DwellerList` is an assignment
   picker. Rename when those components are refactored, rather than adding wrapper files to hide names.
5. **Mixed responsibilities:** `useRoomProduction` also resolves room artwork. Move artwork ownership
   only when introducing a real scene consumer; do not duplicate the resolver now.
6. **Unused registry markers:** `preview` and `info` are returned by the registry but have no matching
   `has(...)` checks in the detail renderer. Either make them control real sections or remove them with
   their expectations updated. Avoid a pretend plugin system.
7. **One-off modal mechanics:** migrate the build menu's custom dialog to the existing modal primitive
   in a separate accessibility change. Keep the room-building workflow.

Keep a component when it owns distinct gameplay or accessibility behavior. A shared journal adapter,
training progress card, and response-team row are useful boundaries, not needless files.

## Room-specific management

### Arena

The scene should answer “who is fighting, on which side, and what is happening?” Management answers
“who will fight next, which mode, and can I start or heal?”

- Initially keep existing combat cards authoritative for HP while adding restrained room ambience.
  This avoids coupling the first visual improvement to an encounter rewrite.
- Later put selected fighters, opponents, and support bots into the scene. Assigned-but-unselected
  dwellers belong in the bench, not on the fighting floor as apparent participants.
- Keep visible underlined mode tabs and compact team selection below the scene. Put match status and
  the primary action together; secondary recovery/reward explanations may stay collapsed.
- Reuse creature artwork mapping in `core/utils/creatureAssets.ts`. Bots and creatures must face their
  opponents; keep facing on a separate wrapper from movement transforms so animation cannot undo mirroring.
- Preserve vault-stock healing, failure feedback, and management locks through countdown and combat.
  Scene animation must never control those rules.

### Response Station

Use the scene to show a staffed response facility, with understandable fire/radiation equipment areas.
Below it, present two hazard-team sections using the existing shared panel and member rows.

- Keep **room staffing**, **active/reserve membership**, **matching gear/protection**, and **current
  availability** distinct. Current aggregate “Gear ready” measures matching gear among active members;
  it does not establish that everyone is available to dispatch.
- Show qualifications and automatic-response behavior in concise text. Do not imply the player must
  press a new dispatch button when existing team behavior is automatic.
- Suggested scene information zones: fire equipment, radiation/decontamination equipment, and staffing.
  These are presentation proposals, not new inventories or simulation systems. Connect only to data
  that exists; do not invent precise readiness percentages or physical equipment stock.
- If a zone is interactive, make it a labelled button that focuses/reveals the corresponding management
  section. Repeat essential information below; an illustration hotspot must not be the only access path.
- Keep merged footprints **3 / 6 / 9** and staffing **2 / 4 / 6**. No separate Expand feature.

### Original rooms and incidents

Use ambient treatment sparingly: a working console, a localized light, or a machine effect can convey
activity without characters performing elaborate actions. Radio recruitment, production, and training
must remain understandable with every animation disabled.

Incident presentation needs urgency and responder clarity, not more idle motion. Keep containment,
damage, results, and reward decisions explicit. Decide separately whether incidents share the persistent
scene or retain their current replacement view; preserve Arena's current precedence until agreed otherwise.

## Ambient animation before character animation

The existing scenes are flattened, opaque WebPs. Their consoles and equipment cannot move independently
without masks or extra assets. Start with one localized overlay per pilot room, reviewed against the
actual art; reject arbitrary glowing dots, whole-image shaking, or a bobbing portrait presented as activity.

| Pilot state | Scene treatment | Management stays explicit |
|---|---|---|
| Arena idle | Quiet console or localized light; simple occupied/empty assignment targets | Bench, mode, team selection, and why a match cannot start |
| Arena countdown / match | A distinct console/status treatment; selected participants identified without invented attack motion | Countdown, authoritative HP, journal, and locked management reason |
| Arena finished | Settled scene with an explicit result | Winner, recovery, and next-match controls |
| Response Station | Fire/radiation equipment areas and simple staffing markers; restrained console ambience | Active/reserve members, actual protection, staffing, and automatic-response explanation |
| Loading / unavailable data | Static backdrop or skeleton; no invented “ready” signal | Loading/error/retry, distinguished from an empty roster |

The first ambient effect should improve recognition of the room or its state. If players cannot connect
an effect to either, it is decoration and can be dropped. Do not animate a responder leaving or returning
unless the available data actually establishes that transition.

| Approach | Fit now | Limitation |
|---|---|---|
| CSS/SVG ambient overlays over the existing image | Best first pilot: lighting, a console indicator, restrained equipment effects | Needs art-aligned positions and meaningful state; cannot articulate baked-in objects. |
| Simple portraits/static cutouts with selection/status | Keeps identity and interaction usable with existing assets | Explicitly not full-body character animation. |
| Frame-based character sprites | Candidate for the separate character experiment | Needs new art, transitions, equipment variants, and a measured payload budget. |
| Layered character rig | Other candidate for that experiment | Needs compatible layers and joint/occlusion rules; greater authoring complexity. |
| Canvas/WebGL game renderer | No demonstrated need for this room UI yet | Adds rendering, hit-testing, accessibility, and asset-pipeline obligations. |

Use Vue to select scene state and mount layers. CSS is sufficient for simple loops; Vue Transition and
TransitionGroup are for entering/leaving elements and list changes, not a combat simulation. Prefer
transform/opacity effects over layout animation. See [Vue transitions](https://vuejs.org/guide/built-ins/transition.html).
Use the native [Web Animations API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Animations_API/Using_the_Web_Animations_API)
only if coordinated playback needs it. No animation dependency is justified by this audit.

The fresh character experiment in [#818](https://github.com/ElderEvil/falloutProject/issues/818) remains
separate: no production renderer or asset pipeline is selected, and the discarded #850 implementation
is not its foundation. [#817](https://github.com/ElderEvil/falloutProject/issues/817) permits independently
reassessing useful manifest/fallback work. Ambient-first work can proceed without choosing either
character-animation approach or expanding the backend actor schema.

## Asset geometry and data limits

The [scene manifest](../../frontend/public/assets/room-scenes/manifest.json) has six backgrounds:
three Arena tiers and three Response Station footprints. Response images have native aspect ratios
1:1, 2:1, and 3:1; Arena images are 3:1. Preserve that distinction in responsive previews.

Every current manifest entry has only two actor anchors, even the six-person station. Runtime components
do not currently consume the anchors or floor baseline; tests inspect them. Before placing scene actors
or equipment zones, define enough positions, scales, and safe areas for the real room capacity.
Anchor coordinates must refer to the rendered image rectangle, accounting for contain/cover and letterboxing,
not blindly to the outer preview box. Replace the URL-specific size-6 aspect exception with explicit
scene geometry when that work begins.

Keep geometry and provenance under one asset source of truth; expose only the small runtime subset needed
by the renderer rather than shipping generation prompts. Do not introduce a second hand-maintained
coordinate catalog. Unsupported scenes should keep the static preview and usable controls.

There is also a limit to what we can animate honestly:

- [`ArenaMatchEventOut`](../../backend/app/schemas/arena.py) supplies ID, round sequence, kind, and message,
  but no structured attacker, target, or damage amount. Current UI derives damage effects from HP deltas.
  Ambient motion and health-change feedback need no API change; accurate attack choreography would.
- Incident rendering uses aggregate event data and displays a latest effect. Do not distribute an
  aggregate damage value among invented individual hits.
- On entry/reconnect, show the current state without replaying historical attacks. Any later event-driven
  animation must deduplicate by event identity and handle skipped updates.
- The server owns combat, timers, rewards, and availability. Animation is cosmetic and can be paused
  without stopping gameplay. Do not parse journal text to reconstruct a second combat engine.

## Accessibility and runtime behavior

Continuous nonessential ambience needs a pause/off control as well as reduced-motion support; the
[WCAG pause/stop/hide guidance](https://www.w3.org/WAI/WCAG22/Understanding/pause-stop-hide.html) covers
qualifying automatic animation lasting more than five seconds. In reduced-motion mode, use static
state changes rather than moving damage labels. Reuse the existing preference pattern and preserve
meaningful status text when effects are off.

Pause visual work when the modal is closed or the document is hidden, then synchronize authoritative
state on return. The [Page Visibility API](https://developer.mozilla.org/en-US/docs/Web/API/Page_Visibility_API)
supports this lifecycle. Do not update Pinia every animation frame, animate every grid tile, or increase
API polling to obtain smoother motion. Profile the pilot before setting budgets or adding a renderer;
follow [Vue's performance guidance](https://vuejs.org/guide/best-practices/performance.html).

Keep semantic buttons, visible keyboard focus, and click/touch alternatives to dragging. Essential
facts and actions must not live only in hover tooltips. These follow the
[Web Interface Guidelines](https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md).
Use [Reka Tooltip](https://reka-ui.com/docs/components/tooltip) for supplementary explanations, not
as a replacement for a management section.

### Concrete cleanup findings

These are code findings/candidates, not claims of completed browser accessibility testing.

| Evidence | Finding / next action |
|---|---|
| `ResponseStationDetail.vue:74`, `:89` | Stationed count is repeated. Keep one instance. |
| `ProductionStats.vue:138` | Four-column grid has no narrow-screen override in this component. Validate at 390px; use fewer columns when needed. |
| `IncidentScene.vue:205`, `:325` | Reduced-motion rule stops flame animation but omits floating effect animation. Include all moving effects. |
| `RoomMenu.vue:45` | Custom dialog handles Escape but does not implement focus trapping/restoration itself. Reuse the established dialog primitive. |
| `RoomPreviewSection.vue:37` | Scene layout special-cases one image URL. Use explicit geometry when adding aligned scene layers. |
| `ArenaModal.vue:107`, `backend/app/schemas/arena.py:62` | HP-difference feedback is available; structured per-attack choreography is not. Keep that limit explicit. |
| `roomParts.ts:110`, `RoomDetailModal.vue` | Registry returns unused `preview`/`info` markers. Make the contract real or remove the markers. |

Focus contrast and small targets in the existing custom preview/picker styles also warrant browser
checks. Removing an outline is not automatically a failure if an adequate visible focus treatment replaces it.

## Management locks: share presentation before policy

Arena currently disables management buttons through its room-detail composition. Grid drag/drop and
upgrade handlers are separate entry paths, so disabled buttons are not a complete cross-room policy.

Do not generalize to “any active room disables everything.” Training cancellation, crafting collection,
incident responders, staffing, and destruction have different implications. When expanding the policy,
decide permission and reason per action, enforce required invariants server-side, and reuse the UI
presentation. A generic capability framework is unnecessary for the ambient scene pilot.

## Suggested delivery slices

1. **Presentation cleanup:** remove repeated facts; align participant styling; fix incident reduced-motion
   coverage; validate the existing layout at desktop and narrow widths. Preserve current gameplay behavior.
2. **Ambient pilot in Arena and Response Station:** retain preview-first layout and existing controls.
   Add one meaningful ambient layer each, geometry matched to the art, pause/reduced-motion behavior,
   and static fallback. Compare both rooms at real modal sizes before expanding the shared scene surface.
3. **Share what the two pilots prove:** reuse scene sizing, fallback, lifecycle, and layer placement.
   Keep Arena/Response management and their stores in their existing modules; avoid a universal room config DSL.
4. **Integrate simple encounter participants:** only after positioning/selection works, move live Arena
   participant presentation into the scene and reduce duplicate combat cards. Response information zones
   can link to the existing team management below. No full animated-character requirement.
5. **Broaden deliberately:** revisit incident/aftermath composition, then individual original rooms.
   Continue the fresh character-animation experiment independently under #818 if wanted.

For each slice check: desktop and 390px widths; Arena modes and tiers; station sizes 3/6/9 and occupants
2/4/6; empty/loading/error/image-failure states; long names; keyboard and touch; reduced motion and pause;
correct enemy mirroring; match locks and re-enablement; modal close/reopen; and no accumulating timers
or requests. New behavior and bug fixes need focused tests; purely decorative changes need visual
comparison, not assertions that merely repeat CSS classes.

The research itself changed no runtime code, dependencies, API contracts, or room rules.

## Pre-shipping follow-up

The subsequent small reuse pass extracted `ArenaDamageNumbers.vue` from fighter and creature slots,
sharing the damage overlay and its reduced-motion behavior. It also keeps Arena room management
disabled until match state is known. Both fixes have regression coverage. The wider scene and
management proposals above remain future work.
