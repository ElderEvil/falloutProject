# Interactive Expedition Sites

Bare-bones idea + mockup for user-in-the-loop exploration dungeons in the style of the
original game (Super Duper Mart, Red Rocket gas station): a dweller discovers a
hand-authored building, the player clears it room by room through combat and
question nodes, and a finale pays a reward above the random-event budget.

Status: **design mockup, nothing is wired**. All names, numbers, and schemas below are
proposals. Nothing here changes runtime behavior until the rollout plan in §13 lands.

## 1. Why

Exploration today is fire-and-forget: send a dweller, watch the event log, collect.
The original game punctuates this with named locations where the player makes
decisions (fight, sneak, answer, loot) for outsized rewards. We have every building
block already (timed events, combat math, loot tables, discovery map links, quest
parties, reward modals) but no place where the user acts *during* an expedition.
Expedition sites fill exactly that gap.

Goals:

- Give the player 2–5 minutes of agency per site: enter rooms, resolve nodes, risk
  health/supplies for better-than-random loot.
- Reuse existing systems (combat, loot, discoveries, rewards, SSE, modals) instead of
  inventing parallel ones.
- Stay farm-proof: a site pays its big reward once per clear, then goes quiet.

Non-goals (§12 lists the rest): no real-time combat, no multiplayer, no new currency,
no changes to the random-event economy.

## 2. Concept in one paragraph

While exploring, a dweller can discover an **expedition site** (a named building with
2–4 rooms) instead of a generic discovery. Entering pauses the normal timed event
stream. Each room presents one **node**: a fight, a choice/riddle, a skill check, a
trap, or a loot cache. Resolving nodes advances a room cursor; the finale room pays
a **reward vault** (caps + XP + one rolled item at elevated rarity). The player can
retreat at any room boundary (keeping room loot, forfeiting the finale) or die trying
(existing dweller-death flow, no special cases).

## 3. Site anatomy

```text
Site (static definition, JSON-seeded like enemies/loot)
├── meta: id, name, flavor, min_dweller_level, biomes/tags
├── rooms: ordered list (linear for v0; branching is a later phase)
│   └── Room
│       ├── id, name, description seed
│       └── node: Combat | Choice | SkillCheck | Trap | Cache | Finale
└── reward_vault: budget + loot table overrides for the finale
```

### 3.1 Node types (v0 set)

- **Combat**: one enemy pack (1–3 enemies from the existing enemy table, difficulty
  pinned per room, §5). Resolved with `combat_calculator.calculate_combat_outcome`
  per enemy in sequence; defeat on any loss does not end the run — it deals damage
  and offers retreat vs. push on (see §6).
- **Choice**: 2–3 fixed options, each tagged with a SPECIAL stat and difficulty.
  Example: "Sneak past (Agility)", "Reason with them (Charisma)", "Kick the door
  (Strength)". Roll: `d20 + stat*2 >= 10 + difficulty*2`. Failure routes to a
  fallback branch (usually a combat or a trap), never a dead end.
- **SkillCheck**: single-stat variant of Choice for locks/terminals/first-aid
  (Perception, Intelligence, Agility). Success opens a cache; failure triggers the
  trap attached to the same room.
- **Trap**: automatic on entry unless disarmed by a preceding SkillCheck. Fixed
  damage range + optional radiation (reuses `apply_radiation_gain` semantics).
- **Cache**: free loot roll from the site table (no check). Keeps momentum between
  hard rooms.
- **Finale**: locked until all prior rooms resolve; pays the reward vault (§8) and
  marks the site cleared.

### 3.2 What v0 deliberately omits

Branching room graphs, NPC dialogue trees, multi-dweller parties inside sites
(quest parties stay outside), and consumable ammo. All are phase-2 candidates.

## 4. Mockup site A — Super Duper Mart

Three rooms, recommended dweller level 5+, theme: raiders squatting a pre-war
supermarket, prize stock in the back.

### Room 1 — Parking Lot (Combat)

- Seed: "Shopping carts rust in rows. Movement between the burned-out cars."
- Pack: 2 × "Feral Ghoul" (difficulty 2, stock table) + 1 × "Raider" (difficulty 2).
- Victory: +XP each, small caps scatter (cache roll, common table).
- Defeat on any round: take rolled damage, offered **push on / retreat** prompt.

### Room 2 — Collapsed Aisles (Choice + Cache)

- Seed: "Shelves form a maze. Something glints three aisles down — and something
  nests above it."
- Options:
  - **Sneak (Agility, difficulty 2)**: success → quiet cache (uncommon+ table);
    failure → ambush combat (1 × difficulty-3 enemy).
  - **Loud sweep (Strength, difficulty 1)**: success → cache + bonus XP;
    failure → trap (falling shelves, 4–9 damage).
  - **Call out (Charisma, difficulty 3)**: success → a cornered scavenger trades
    (cache at rare table, costs 25 caps on the spot); failure → they flee, room
    downgrades to a plain cache.
- Regardless of path, one cache roll is guaranteed so the room never feels empty.

### Room 3 — Storage Room / Finale (Combat + Reward vault)

- Seed: "The shutter is chained from inside. The boss of the parking lot lives here."
- Boss: 1 × "Raider Boss" (difficulty 4, +50% HP flavor via max-damage bump).
- Reward vault: 150–250 caps, full XP share, one item roll at **rare-or-better**
  (weights shifted two tiers up from the standard table), plus a guaranteed junk
  bundle for crafting.

## 5. Mockup site B — Red Rocket Gas Station

Two rooms plus finale, recommended level 3+, theme: protect the pump, crack the
bunker. Smaller and earlier than the Mart — the tutorial site.

### Room 1 — Forecourt (Trap + Choice)

- Seed: "The pumps still tick over. The concrete is mined — someoneImprovised."
- Entry trap (4–7 damage) unless disarmed.
- Options:
  - **Disarm (Perception, difficulty 1)**: success → no damage + 10–20 caps in
    the till; failure → trap fires at half damage.
  - **Detour (Luck, difficulty 2)**: success → skip clean; failure → full trap.
  - **Tank it (Endurance, difficulty 1)**: walk through, damage reduced by
    endurance × 2 (same mitigation as combat), gain +XP grit bonus.

### Room 2 — Garage (Combat)

- Pack: 2 × "Mole Rat" (difficulty 1) + 1 × "Raider" (difficulty 2).
- Workbench flavor: victory also grants a junk bundle (garage scrap).

### Finale — Bunker Cache (SkillCheck + Reward vault)

- Terminal (Intelligence, difficulty 2): success → reward vault opens at full
  budget; failure → vault opens at half budget (never zero — see §7).
- Reward vault: 80–140 caps, XP share, one item roll at **uncommon-or-better**,
  one guaranteed stimpak (tutorial generosity, once per vault ever).

## 6. Interaction model (user-facing flow)

1. Discovery event fires as today (map link, journal entry), but flagged
   `site_id`. The event description ends with an **Enter / Ignore** prompt.
2. Enter pauses the timed event generator for that exploration (cooldown clock
   freezes; no ambushes while reading). Ignore continues exactly as today.
3. Each room renders a modal: room art/flavor, node prompt, legal actions
   (fight is automatic on confirm; choices show stat + odds; retreat always
   visible at room boundaries, never mid-combat-roll).
4. Resolution appends to the exploration event log with a `site_room` marker so
   the journal, SSE feed, and triage labels keep working unchanged.
5. Progression red line: site entry, finale, and death-each surface a modal or
   toast **in addition to** the notification bell entry, never bell-only.
6. Retreat keeps room loot, forfeits the finale, unpauses the event stream.
   Death follows the existing dweller-death flow (revival, trading post, bio).

## 7. Failure philosophy (no dead ends, no zero payouts)

- Every node has a defined failure branch that costs health, supplies, caps, or
  budget — never progress. A failed run is always resumable by retreating.
- Finale budget scales down on partial clears (Red Rocket terminal) but never to
  zero once the finale room is reached.
- Difficulty checks show odds before committing (stat + difficulty are visible),
  so losses feel earned, not random.

## 8. Reward economy (bare-bones v0 numbers)

All payouts assume one site clear ≈ 3× the loot of the same minutes on random
events, paid once:

| Site | Caps | XP | Item roll | Guaranteed extra |
|---|---|---|---|---|
| Red Rocket (lvl 3+) | 80–140 | 1.0× share | uncommon-or-better ×1 | 1 stimpak (once/vault) |
| Super Duper Mart (lvl 5+) | 150–250 | 1.2× share | rare-or-better ×1 | junk bundle |

Anti-farm rules:

- Cleared sites go quiet per vault: finale cannot retrigger for 7 days (timestamp
  on the run record); rooms still yield nothing on revisit (no loot regen).
- Site discovery weighting respects level gates; gray (trivial) sites for
  overleveled dwellers pay caps only, no item roll.
- Reward budgets live in server config (`game_config.exploration` sibling block),
  tunable without code changes.

## 9. State model (proposal)

New table `expedition_run` (one row per site attempt), because run state must
survive ticks, restarts, and SSE reconnects — the events JSON log is history, not
state:

```text
expedition_run
├── id, exploration_id (FK), dweller_id, vault_id, site_id
├── room_cursor: int (index into site.rooms)
├── status: ENTERED | IN_ROOM | RETREATED | CLEARED | DIED
├── hp_snapshot / supplies_snapshot (for death/retreat rollback display)
├── flags: JSON (disarmed traps, spent caches, granted once-only bonuses)
└── cleared_at (anti-farm timestamp; NULL until finale)
```

Static site definitions live beside the enemy/loot JSON consumed by
`data_loader` (same authoring ergonomics, no migration to add a site).

## 10. Integration seams (concrete files)

- `exploration/event_generator.py`: discovery draw gains a site-entry variant
  (level-gated, weighted like the discovery flat roll); generator stays random,
  sites stay authored.
- `exploration/event_service.py::process_event`: when the event is a site entry,
  freeze the event clock and emit the Enter/Ignore prompt instead of loot/combat
  handling. New `exploration/expedition.py` service owns room resolution; it may
  call `combat_calculator`, `loot_calculator`, `radiation` helpers, and
  `exploration.add_event` — no new persistence paths.
- Schemas: extend `exploration_event.py` with `SiteEventSchema`
  (`site_id`, `room_id`, `node_type`, `prompt`, `options[]`); event `type` gains
  `site`. Frontend `getEventIcon/getEventColor` gain one branch.
- Map: site discoveries reuse `register_discovery` + a `SITE` location marker
  variant; deep-link opens the site modal instead of the place card.
- Quests (optional link): site clear can satisfy a `site_cleared` requirement via
  the existing `individual_meets_requirement` path — no quest changes needed.
- Notifications: entry/finale/death notify via `notification_service` like quest
  completion does today.

## 11. API sketch (v0)

```text
POST /explorations/{id}/site/enter        -> SiteRoomView (room 0 + node prompt)
POST /explorations/{id}/site/resolve      {choice_id | confirm} -> SiteRoomView (next room or finale)
POST /explorations/{id}/site/retreat      -> ExplorationRead (stream unpaused)
GET  /explorations/{id}/site              -> current SiteRoomView (reconnect-safe)
```

```text
SiteRoomView { site_id, room_index, room_name, flavor, node: {kind, prompt,
  options[{id, label, stat, difficulty, odds}], enemy_preview?}, can_retreat,
  finale_preview? }
```

SSE: existing exploration channel carries `site` event records; a `site_prompt`
push wakes the client modal. All endpoints thin (parse → expedition service →
map exceptions); service never issues raw `select()` (CRUD owns queries).

## 12. Frontend sketch (v0)

- `ExpeditionSiteModal.vue`: room card (flavor + node prompt), option buttons with
  stat/odds chips, retreat button at boundaries; resolution swaps to outcome pane
  (damage taken, loot gained) with Continue.
- Finale reuses `ExplorationRewardsModal` with a site banner — one rewards surface,
  per the granted-reward display contract.
- Store: `useExpeditionSite` (enter/resolve/retreat/current), SSE listener flips
  the modal open on `site_prompt`. CRT styling, existing `UButton/UModal`.
- Journal: site rooms render in `ExplorationEventLog` via the new `site` type +
  icon/color branch; loot lines reuse `getLootDisplay`.

## 13. Rollout plan

- **Phase 0 (this doc)**: agree on node set, anti-farm rules, reward budgets.
- **Phase 1**: site JSON + `data_loader` + `expedition.py` resolution engine +
  unit tests per node type (fixed RNG seeds) + `expedition_run` migration.
- **Phase 2**: endpoints + SSE + `SiteEventSchema` + journal rendering.
- **Phase 3**: modal + store + rewards reuse + tutorial copy for Red Rocket.
- **Phase 4**: balance pass (clear-rate telemetry per site/level), second site
  batch, branching rooms.

Test plan: unit per node (success/fail/edge), full Red Rocket run-through on
SQLite, anti-farm (reclear pays nothing), death mid-site follows existing flow,
retreat keeps room loot only, SSE reconnect mid-site recovers via `GET site`.

## 14. Open questions

1. Parties in sites: solo only for v0, or reuse quest parties from the start?
2. Should Jev score riddle answers (free text) or stay with fixed options in v0?
   (Fixed options now; Jev-graded riddles are a natural phase-4 node type.)
3. Stimpak use mid-site: allow at room boundaries (recommended) or anytime?
4. Do cleared-site markers expire ever, or stay cleared for the vault lifetime?
5. PvP-adjacent content (raider boss names from other vaults)? Explicitly out
   until moderation story exists — note `content_moderation_service` (Jev spike)
   as the future gate.

## 15. Explicit non-goals for v0

Real-time or animated combat; consumable ammo; site editor UI (JSON + review);
trading site clears; leaderboard; changes to random-event weights, enemy table,
or loot tables (sites only shift weights within their own vault budget).
