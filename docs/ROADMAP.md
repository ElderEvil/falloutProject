# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## In Progress

**Current work:**

- [x] **v2.39.0–v2.39.4 released** — Resource production rate corrections (0.0003 → 0.1) for a livelier economy,
      dweller thumbnail URL fix, release housekeeping.
- [x] **v2.40.0 released** — Training tab UX (occupancy cards, live progress bars), UTC training timestamps, shared
      training-room capacity helper.
- [x] **v2.41.0 released** — Chat WebSocket streaming, vault event system, notification navigation, visual equipment
      consistency, resource depletion warning, exploration rewards via SSE.
- [x] **v2.41.1 released** — Frontend audit CRITICAL/MAJOR fixes (design-token migration, dead camelCase utilities,
      router typing).
- [x] **v2.41.2 released** — Quest storage 500 fix (ValueError → 404/409) and EventBus cross-loop asyncpg race fix.
- [x] **v2.41.3 released** — Postpartum breeding cooldown + last-name inheritance.
- [x] ~~**Postpartum breeding cooldown + last-name inheritance**~~ — ✅ **Done.** Merged in v2.41.3. Mothers can no longer
      re-conceive on the next tick after delivery; newborns take the father's last name by default.
- [ ] **v2.42.0 — The Family Update** — MARRIED relationship stage, lineage API + family tree UI (Family tab),
      migration-safety CI, and Pydantic AI/Logfire verification. See "Version Milestones".
- [ ] **Arena & Incident Combat Update (in review — `feat/arena-incidents`)** — dweller-vs-dweller battle
      playground in the Arena room (assign adults, pick two fighters, countdown start, live HP + floating damage,
      battle journal, one match per assignment, happiness/XP reward), plus incident fairness: active-incident cap
      enforced at spawn and spread behind a per-vault advisory lock, a dedicated 2s incident tick with a Redis
      chain lease (watchdog can no longer spawn duplicate processing chains), session-advisory-locked all-vault
      pass, room-name + compact FIGHT buttons + "send best defenders" in the combat modal, and distinct debug
      spawn errors (disabled → 400, at-cap → 409). Follows the arena prototype previously parked on
      `experiment/arena`.
- [ ] **AI provider profile + LM Studio support (in review — `feat/ai-settings`)** — DB-backed AI provider
      settings (profile overrides env, secrets stay in env), admin UI embedded in the Overseer profile,
      live provider connection test, token-usage estimation for local providers (LM Studio/Ollama), profile
      re-applied at backend startup, and a chat streaming fallback that re-runs the retry-capable structured
      path so action suggestions survive a failed local-model validation. **Needs manual testing:** dweller
      chat streaming + action cards (esp. wasteland exploration via LM Studio), AI Settings tab (save /
      reset / test connection / copy), profile persistence across backend restarts, and the profile page tabs
      (Dossier / Vault Analytics / AI Settings).
- [ ] **Service simplification & unification (in review — `refactor/breeding-exploration-debt`)** — breeding
      and pregnancy data access fully on crud (missing parents/pregnancies raise `ResourceNotFoundException`,
      state rules keep `ValueError`), debug endpoints without string-matched exception mapping, and the
      exploration coordinator split into `event_service` + `rewards_service` with match-based item scoring
      (coordinator keeps complete/recall orchestration only). Follows the game-loop fail-fast narrowing and
      crud/service split shipped in v2.62.x; net source LOC negative across both PRs.

---

## Planned

### Next update target — "The Overseer's Toolkit" (Unreleased)

**Focus**: turn the Overseer’s Office into a dependable command surface while tightening reliability and operations
around it, without displacing the vault workspace. Semantic Release will choose the version when this scope is released.

- ✅ **Overseer Briefing** — summarize incidents, active exploration/training/questing, resource warnings, unassigned
  dwellers, capacity, and happiness in the Overseer’s Office; show unresolved-item count on its room-grid tile and
  link directly to response and dweller review flows.
- ✅ **AI reliability fixes** — stream structured chat output incrementally and share quota-cache key definitions
  across services.
- ✅ **UI consistency & detail polish** — standardize page rails, headers, descriptions, and compact metrics; restore
  the Build control, repair status badge glow tokens, preserve children previews without fake progress data, and
  refine exploration portraits, health trends, terminal meters, and long equipment labels.
- ✅ **Production logging** — create a rotating API log file on a persistent volume, keep stdout enabled, and use
  JSON output in production. Ollama is intentionally local-development-only.
- ✅ **Verification** — unit coverage plus deterministic authenticated Playwright coverage for the briefing route and
  response interaction.

**Success criteria**: an overseer can see the vault's highest-priority state at a glance, reach the right response
flow in one action, and rely on tested production logs and browser behavior without provider-specific setup.

### Frontend Design-System Consolidation (Target: TBD)

**Focus**: Make the terminal UI coherent by having shared primitives consume the same surface, spacing, border, and
interaction tokens instead of compensating with page-level CSS.

- ⬜ Define and document the canonical canvas, panel, inset-control, hover, and overlay surface roles.
- ⬜ Align `UButton`, `UInput`, `USelect`, `UModal`, cards, and badges to those roles, including visible focus and
  disabled states.
- ⬜ Replace repeated feature-local button and control styling as related screens are touched; favor smaller shared
  variants over new one-off CSS.
- ⬜ Add an icon affordance to form labels where it makes an identity or game concept easier to scan, while keeping
  labels as the accessible source of meaning.

#### Intent & emphasis adoption (see STYLEGUIDE → "Intent & Emphasis Semantics")

- ✅ **Semantics defined** — three intents (actionable / live status / informational), emphasis tokens `--glow-0..3`,
  and badge utility classes `.badge-info` / `.badge-live` / `.badge-action`; informational badges (gender, rarity,
  age group) demoted to quiet chips; dead glow utilities removed.
- ✅ **Top offenders wired** — `DwellerStats`, `DwellerGridItem`, `SidePanel`, `QuestsView`, `ExplorerStatsGrid`:
  informational text glows removed, headings/panels on `--glow-1`, interactive surfaces on `--glow-2`. Transient
  one-shot feedback (stat highlight, level-up celebration) stays as a sanctioned exception.
- ⬜ **Long tail** — ~30 files still hand-roll glow values (~150 declarations, ~15 distinct radii). Convert to the
  token scale as each screen is touched; replace Tailwind arbitrary `text-shadow-[…]` values on sight; hover
  responses on non-interactive surfaces get removed in the same pass.

**Success criteria**: new management screens can be assembled from shared primitives without custom surface fixes,
and equivalent controls look and behave the same across the vault.

### Room Detail Part Registry (Target: TBD)

**Focus**: Consolidate how the room detail modal decides which sections exist. Today "does this room have part X" is
answered by three implicit mechanisms — category checks (`isArenaRoom`), name string-matching (`isOverseersOffice`,
vault door, radio), and derived computeds (`productionInfo`) — scattered across `RoomDetailModal`, its composables,
and `RoomActions`. Replace them with one explicit, ordered part registry.

- ✅ **Part registry** — `modules/rooms/models/roomParts.ts`: `getRoomDetailParts(room)` returns the ordered section
  list (preview, info, production stats, radio stats/controls, dweller list, arena, overseer briefing, actions),
  driven by room category with centralized special-room overrides.
- ✅ **One decision point for special rooms** — `isRadioRoom`, `isVaultDoor`, and `isOverseersOffice` name-matching
  live only in the registry; `useRadioRoom`, `useRoomUpgrade`, and `useRoomProduction` consume it.
- ✅ **Registry-gated modal** — `RoomDetailModal` renders each section behind `has(part)`; the category/name
  branching and the two-branch template split are gone (`ArenaRoomDetail` is the mapped `arena` part).
- ✅ **Composition tests** — `roomParts.test.ts` asserts the part list per room type (arena, radio, overseer's
  office, vault door, producing/non-producing, training); the existing RoomDetailModal suite guards the zero-visual-
  change refactor.
- ✅ **Composition change: radio management normalized** — the Radio Studio's management section now uses the same
  action grid as every other room (the bespoke `radio-layout` variant is gone; radio controls remain as the
  radio-specific content above the buttons).
- ⬜ **Phase 2 (separate product decisions, think first):** whether further compositions should unify where it makes
  sense — e.g. arena also showing info/dweller list — decided per part, not bundled into refactors. A full
  component-map renderer (replacing the `has(part)` gates) can ride along when a second composition change lands.

**Non-goals:** backend-declared parts (rooms.json describing UI layout — presentation stays a frontend concern); a
`role`/`slug` column on built rooms (migration for zero behavioral gain; seed-data-stable names stay, centralized);
extending the registry to `RoomGridCell` or the build menu (revisit only if the pattern proves itself).

**Success criteria**: adding a room type means adding one registry entry plus its part components; part composition
per room type is asserted by tests; no category or name checks remain outside the registry.

### Dweller Identity & Atmosphere Update (Target: TBD)

**Focus**: Turn the existing `visual_attributes` JSONB data and `backend/app/options/` lore into a legible, animated
identity layer across the vault—without adding new gameplay rules or duplicating option definitions.

- 🔄 **Typed identity metadata** — expose race, faction, state-of-being, and compatible option metadata from the
  existing options modules; validate race/faction combinations whenever visual attributes are saved.
- 🔄 **Identity dossiers** — add reusable race/faction insignia, lore-aware labels, and compact state descriptions to
  dweller cards, grid items, quest parties, exploration, and the dweller detail view.
- 🔄 **Badge & tooltip unification** — identity badges (race, faction) and demographic badges (rarity, gender, age)
  currently mix tooltip implementations (`UTooltip` vs native `title`) and visual treatments; consolidate on one
  badge component and one tooltip pattern, keeping the styleguide's informational intent (`--glow-0`, no fill).
- 🔄 **Appearance presets** — offer the existing archetypes (Vault Dweller, Brotherhood Knight, NCR Ranger, Ghoul
  Mercenary, Institute Courser, and others) as previewable appearance-editor presets; presets only populate visual
  attributes and never grant equipment or stats.
- 🔄 **Terminal motion polish** — use restrained CRT signal sweeps and faction/race accents, with reduced-motion
  support; legendary, ghoul, and synth variants should be distinctive without becoming noisy.

**Delivery**: first ship backend metadata/validation with tests, then apply the shared identity-dossier component to
existing frontend surfaces with component tests.

**Success criteria**: an overseer can immediately recognize a dweller's identity wherever that dweller appears, edit
only lore-valid combinations, and apply a preset safely—while users who prefer reduced motion see a static interface.

### Dweller Domain Schema Composition (Target: TBD)

**Focus**: Gradually make the dweller API domain easier to evolve by composing focused schemas—identity/visual,
vitals, combat, and social/lineage—while retaining a single `Dweller` database aggregate and table unless a concrete
storage lifecycle requires otherwise.

- ⬜ Extract focused Pydantic read/input schemas only where an active feature benefits from them; do not split the
  SQLModel table, CRUD ownership, or migrations speculatively.
- ⬜ Compose compact and full API responses from those shared schemas without changing existing client contracts.
- ⬜ Move the visual identity schema as part of the Dweller Identity & Atmosphere work when it removes duplication;
  defer vitals, combat, and social extraction until their respective workstreams touch them.

**Success criteria**: each dweller concern has one clear schema owner, API contracts remain backward-compatible, and
the database remains simple until its shape demonstrably needs to change.

### World Map — Multiplayer-First Architecture (Target: TBD)

**Focus**: Evolve the wasteland map into the game's multiplayer surface — one deterministic shared world
with per-player fog of war, over which async-PvP raiding, cross-vault encounters, and social features layer.
Feature contract: `docs/features/WORLD_MAP.md`; delivery plan: `docs/WORLD_MAP_PLAN.md`.

**Near-term release — "The Wasteland Journal" (shipped in v2.46.0):**

- ✅ **Exploration journal polish** — mid-journey `loot_collected`, cumulative health-change trail,
  consolidated progress math, and dead-component deletion.
- ✅ **Discovery → map integration** — discovery event coordinates/IDs, deep-links, and event-authoritative
  per-exploration routes on `WorldMap` (no migration).
- ✅ **Determinism correction** — globally seeded neighbor-vault signals with regression coverage.
- ✅ **Quest party-members fix** — `QuestsView` populates `questPartyMembersMap`, so party rosters render.
- ✅ **Discovery unlock fix** — `register_discovery` links the exploring dweller so DISCOVERY markers unlock
  immediately; the v2.46.1 backfill script repairs pre-fix rows. Deploy the matching worker image to activate it.

**Current focus — World Map + exploration polish (no multiplayer):**

- 🔧 **Deployment parity** — deploy the v2.46.1 Dramatiq worker image with the discovery-unlock fix so new
  discoveries unlock live (the currently deployed worker runs pre-fix code).
- 🔧 **Polish candidates** — locked-marker discoverability hints (who to chat with to unlock a bio place),
  exploration detail UX, journal edge cases, and any map/exploration bugs surfaced by play.

Feature description: `docs/features/WASTELAND_JOURNAL.md`; delivery checklist and verification:
`docs/WORLD_MAP_PLAN.md`.

**Deferred multiplayer phases** (parked; revisit when the single-vault experience is solid, see
`docs/WORLD_MAP_PLAN.md`):

- ⏸️ **Phase B — async-PvP raiding** — `RaidTarget` snapshots + a `raid` exploration subtype.
- ⏸️ **Phase C — cross-vault fallen dwellers** — global `FallenDwellerRegistry` (dead dwellers as raiders).
- ⏸️ **Phase D — social** — friends, vault visits, leaderboards, global location registry.

**Guardrails:** async only (no live shared-world simulation); names determine shared base coordinates, while
vault-local collision resolution may temporarily offset overlapping markers; no denormalized global registry
until Phase D; respect the v2.35+ net-LOC constraint (journal polish deletes more than it adds).

**Success criteria:** the near-term release delivers a legible per-explorer journey (loot + health-change trail +
map route), discovery events deep-link to their map marker, and neighbor vaults sit at globally-consistent
coordinates — all test-backed.

### Next Big Feature — Family Relations (Target: TBD)

**Focus**: Make the existing breeding/relationship systems into a visible family experience: family trees,
relationship depth, and legacy that persists across generations. This is the natural successor to the breeding
cooldown and naming fixes.

- 🔄 **Family tree visualization** — graph view of parents, children, siblings, and partners per dweller, building on
  the existing `parent_1_id`/`parent_2_id`/`partner_id` fields and the world-map marker system.
- 🔄 **Relationship depth** — affinity already gates conception; add visible relationship stages (acquaintance →
  friends → partners → married) with event/notification hooks and stat bonuses.
- 🔄 **Legacy & lineage** — surface generational data on dweller detail (house/family name, generation number,
  inherited traits from `_calculate_inherited_stats`), and consider a "founder's vault" distinction.
- 🔄 **Postpartum cooldown tuning** — after the cooldown ships, play-test the 6h default against high-affinity
  couples and adjust `birth_cooldown_hours` before building on top of it.

**Guardrails:** delegate to the service layer (never CRUD directly) so events, notifications, and game-loop side
effects fire exactly as they do for REST calls; respect the v2.35+ net-LOC-reduction constraint by extracting shared
lineage/tree helpers instead of duplicating map-marker logic.

**Success criteria:** a player can open any dweller's family tree, see relationship stage progression with
notifications, and identify multi-generation lineage from the detail view — with backend coverage for the tree and
stage-transition logic.

---

### Overseer Reports — CodeRabbit Review Follow-ups (Target: TBD)

**Focus**: Follow-ups from the CodeRabbit review of the Overseer Reports PR (#449). The two stability fixes shipped
with the PR (incident victory notification now fires only after the incident commit succeeds; `notify_owner`
swallows vault-owner lookup failures). The remaining items were deferred or recommended for a follow-up.

- 🔄 **Breeding capacity concurrency** — `check_for_conception` reads `available_slots` without locking, so two
  concurrent ticks can each reserve the last free slot and over-commit pregnancies. Enforce the capacity check and
  the pregnancy insert in one transaction (`SELECT ... FOR UPDATE` on the vault row), at the `create_pregnancy`
  boundary so every conception path is covered. Heavy lift; the in-memory SQLite test harness cannot exercise row
  locks today.
- 🔄 **Pending-report dedup by `exploration_id`** — `usePendingReports` deduplicates by dweller + rewards content, so
  two identical completions from the same dweller are collapsed. Propagate the SSE `exploration_id` through the
  notification metadata and dedup on it instead. Heavy lift (backend metadata change).
- 🔄 **DwellerPanel query-prop sync** — clicking the same dweller's `training_complete` notification again (query-only
  `?tab=stats&stat=X` change) does not update the active tab or badge because the component instance is reused
  without re-running setup. Watch `initialTab`/`highlightStat` props and restart the badge timer on change.
- 🔄 **ExplorationView vault filter** — pending reports are global (single `localStorage` key), so reports from one
  vault can surface while viewing another. Scope selection/acknowledgement to the active `vaultId`.
- 🔄 **DwellerStats animations → Tailwind utilities** — move the scoped `stat-pulse`/`badge-fade` keyframes into
  `tailwind.css` as utilities with motion-reduce variants (aligns with the Tailwind-utilities-only guideline).
- ⚪ **Nitpicks (optional)** — route exploration-completion notifications through `notify_owner` for consistency with
  the other flows; wrap a >100-char line in `exploration.ts`.

**Guardrails:** keep the resolution-notification ordering fix (notify only after a successful commit) intact when
touching incident handling; any breeding change must keep `population_max=None` unbounded.

---

### v2.34.0 — Pydantic AI Reliability & Observability (Target: TBD)

**Focus**: Make existing dweller agents easier to debug and more reliable at the boundary between structured model
output and gameplay actions. Keep this as one backend/AI release instead of splitting several small library adoptions.

**In progress:**

- ✅ **Trace Pydantic AI runs in Logfire**
  - When Logfire is configured, instrument Pydantic AI in addition to the existing application setup so agent runs,
    tool calls, retry counts, latency, and token usage are visible in one trace.
  - The disabled/no-token path remains a no-op; instrumentation explicitly uses `include_content=False` so prompt
    content is excluded from traces. Unit coverage verifies both paths without using a provider token.
- ✅ **Harden the dweller chat output contract**
  - Migrate agents that do not pass message history from `system_prompt` to static/dynamic `instructions`; preserve
    `system_prompt` only where history retention is intentional.
  - Add output validation/retry rules for action-field combinations before gameplay code consumes them (for example,
    required room data for room assignment and no action payload for `no_action`).
  - Added deterministic `TestModel` coverage for instructions, room-recommendation tool execution, invalid structured
    output retries, and recorded token usage; existing chat-service coverage protects fallback behaviour.
- ✅ **Keep optional RustFS from delaying backend startup**
  - Skip the optional S3 probe during startup; detailed health checks still report RustFS availability.
  - Treat unreachable Botocore endpoints as degraded storage health, with short single-attempt diagnostic probes.
  - Allow core gameplay to run without RustFS configuration and cover the endpoint-connection path with regression tests.
- ✅ **Ground dweller activity suggestions in live gameplay state**
  - Add a read-only activity briefing tool that reports active training/exploration, trainable rooms and capacity,
    available medical supplies, and a bounded exploration pack before the agent suggests a training or wasteland action.
- 🔄 **Activate Pydantic AI Gateway for chat and agents**
  - Configure the deployment-only `PYDANTIC_AI_GATEWAY_API_KEY`; the existing gateway model path becomes active without
    changing agent code.
  - Retain `OPENAI_API_KEY` for native image, TTS, and transcription APIs, which remain direct OpenAI integrations.
- 🔄 **Measure before/after**
  - Baseline and report deterministic agent-contract test count, output-validation retry coverage, and Logfire trace
    completeness for one normal chat and one tool-using chat.
  - Guardrails: no agent framework major-version migration, no gameplay-rule change, and no real-provider calls in the
    unit test suite.

---

### v2.35.0 — Release Version Integrity (Released 2026-08-14)

**Focus**: Make the SemVer Git tag the single release authority. Eliminate manual, separately committed backend and
frontend version bumps, and make release eligibility deterministic from validated Conventional Commit metadata.

**Engineering constraint (v2.35 onward):** Every update must reduce net source LOC. Features that require new code
must first offset it by removing or compacting existing code, favoring DRY reusable extraction over duplication. The
reduction excludes generated files, lockfiles, and formatting-only changes, and must retain behavior under relevant
tests.

**Completed:**

- ✅ **One automated release version**
  - Have Semantic Release calculate the next version, synchronize `backend/pyproject.toml`, `backend/uv.lock`, and
    `frontend/package.json` in its prepare phase, then commit those generated release artifacts before creating the
    `vX.Y.Z` tag.
  - Reconcile the existing manual-release history by validating and tagging the current `v2.34.3` state as the
    migration baseline; do not retroactively invent missing release versions.
  - Remove manual version-bump commits from the normal feature workflow; agents must not choose a release number.
- ✅ **Enforce release intent at merge time**
  - Require Conventional Commit PR titles and squash merges; the resulting `master` commit is the sole input to
    SemVer calculation.
  - Map `feat` to minor, `fix`/`perf`/`refactor` to patch, and `!`/`BREAKING CHANGE` to major; keep
    `docs`, `test`, `chore`, `ci`, and `style` non-releasing.
  - Use human-readable, lower-kebab branch names such as `feat/ai-observability`; branch names provide context only
    and must not encode or determine a version.
- ✅ **Build and verify the release pair**
  - Build and publish both backend and frontend Docker images from the release tag, using the tag's version for both
    image families rather than independently reading manifests on ordinary `master` pushes.
  - Add a CI guard that fails when the release tag, backend package version, frontend package version, or newest
    changelog heading disagree.

**Success criteria:** a release creates exactly one versioned commit and tag, both deployable images carry that same
version, and CI rejects divergent metadata before publication.

---

### Next Automated Release — Container Build Efficiency (Target: TBD)

**Focus**: Make release image builds faster and measure runtime-image size without changing deployment behavior.

**Planned:**

- 🔄 **Maximize reusable build cache** — replace the inline cache with a per-image registry cache in `mode=max` so
  dependency and intermediate multi-stage layers are reusable across ephemeral GitHub Actions builders.
- 🔄 **Measure before changing runtimes** — record cold and warm frontend/backend build-and-push durations plus
  published image sizes; `v2.35.0` is the initial timing baseline (26s frontend and 51s backend build-and-push).
- 🔄 **Reduce only demonstrated runtime overhead** — assess direct ownership on `COPY` for the backend and a minimal
  static frontend server only after smoke tests prove unchanged SPA routing and container behavior.

**Success criteria:** record exact before/after frontend and backend build-and-push durations plus published
image bytes, with the CI run or command used for each measurement; improve at least one metric without weakening tag
validation, cache isolation, or runtime behavior.

---

### AI Overseer — MCP Integration (Proposal, Target: TBD)

**Focus**: Expose game capabilities to external AI clients (Claude Desktop, Cursor, custom agents) through the Model
Context Protocol so an external "Overseer assistant" can read live vault state and issue high-level commands without
bespoke glue code. Full design in `docs/backend/MCP.md`. Complementary to the in-game dweller chat agent — it does
NOT replace it.

**Planned:**

- 🔄 **P0 — Read-only MCP resources** — `vault://{id}/state`, `dweller://{id}/bio`, `notifications://{user_id}` behind
  the existing JWT auth; no new tables or migrations.
- 🔄 **P1 — Safe action tools** — `assign_dweller_to_room`, `start_training`, `pause_game`/`resume_game`; routed
  through the existing service layer and quota service, with mutating tools gated behind human approval.
- 🔄 **P2 — Curated prompts** — `overseer_daily_briefing(vault_id)` and `vault_triage(vault_id)` prompt templates.
- 🔄 **P3 — Evaluate usage** — assess before adding exploration/room-building tools or a standalone bridge.

**Guardrails:** tools must delegate to services (never CRUD directly) so events, notifications, and game-loop side
effects fire exactly as they do for REST calls; in-game chat path unchanged; tool exposure is context management, not
access control — permissions live in the service layer.

**Success criteria:** an external MCP client can read live vault state and perform one safe action (e.g., start
training) with ownership checks and quota enforcement, while in-game chat behavior and test suites remain unchanged.
Resource authorization checks are part of the definition of done: loading `dweller://{id}/bio` requires resolving the
dweller and authorizing its vault (`get_user_vault_or_403` / `verify_dweller_access`), and `notifications://{user_id}`
must reject any identifier that does not match the authenticated user.

---

### Deferred Library Adoption (Reassess During a Related Feature)

- **FastAPI** — native SSE is already used; do not introduce `app.frontend()` for the separately deployed Vue SPA.
- **Pydantic / SQLModel** — the current PATCH flow already uses `exclude_unset=True`; consider `MISSING` only when an
  API genuinely needs to distinguish omitted values from explicit `null`, and use `sqlmodel_update()` only when
  touching the shared CRUD update path for another reason.
- **Tailwind CSS** — use newer semantic utilities such as native text shadows, safe alignment, pointer variants, or
  `@source inline()` only in the component that needs them. Avoid a formatting-only CRT-style rewrite.
- **Pydantic AI agent tool scaling** — the dweller chat agent's toolset is small and bounded
  (`DwellerActivityBriefing` already caps tool output); revisit only if the tool catalog grows well past ~10 tools:
  - **Search-then-execute** — replace "one schema per tool" with two tools (search for an action, execute by ID) so
    context stays flat regardless of catalog size.
  - **On-demand tool loading** — keep tools out of context until the agent actually needs them (harness-style
    `defer_loading`).
  - **Tool output limits** — cap oversized tool returns so a large export cannot eat the context window.
  - **Human approval on mutating tools** — gate write actions behind approval, distinct from read tools.

### Item Card Unification — ✅ Done

**Shipped:** `src/core/models/items.ts` is the single source of truth for item display — weapon-subtype/outfit-type
icon maps, rarity color + token-based Tailwind border/text classes, and unified stat-row builders (damage, uses,
accuracy, type, weight, durability, outfit gender, SPECIAL bonuses), plus a shared `useItemImage` composable.
`EquipmentCard` and `StorageItemCard` consume it and now expose the full unified detail set (each previously missed
half of it); `ExplorationLootList` uses the shared rarity tokens with no inline styles. Net source LOC negative.

### Race & Faction Gameplay Mechanics (Target: TBD)

**Focus**: Make race and faction matter mechanically. Today they are purely cosmetic (`visual_attributes` JSONB +
AI appearance/backstory prompts + identity badges). The Combat Power Overhaul's per-type weight table is the hook:
racial modifiers and faction perks slot into the same stat-weighting shape instead of ad-hoc special cases.

- ⬜ **Racial stat modifiers** — small SPECIAL adjustments applied at the stat level (ghoul +Endurance with
  radiation immunity, super mutant +Strength/+Endurance with a Perception penalty, synth stable stats), so every
  consumer (combat, training, production) sees them without per-system branching.
- ⬜ **Racial perks** — a few explicit, testable perks (ghoul radiation healing, synth resistances) wired into
  incident/exploration resolution via the service layer.
- ⬜ **Faction perks** — light bonuses aligned with lore (Brotherhood +energy weapons, Legion +melee, Minutemen
  +incident response), reusing the weapon-type weight lookup rather than new formulas.
- ⬜ **Identity plumbing** — build on the Dweller Identity & Atmosphere metadata so perks/modifiers are declared
  next to the race/faction option definitions in `backend/app/options/`, validated on save, and surfaced in the UI
  dossier ("why is my Ghoul tanky").

**Guardrails:** modifiers live in one options-backed source of truth; no new DB columns unless a modifier must
persist per dweller; balance pass after play-testing; net-LOC rule applies.

**Success criteria:** race/faction choices change outcomes (combat, incidents, exploration) in legible ways, are
visible in the dweller dossier, and are covered by per-race/per-faction unit tests.

---

## Low-Hanging Fruit — Immediate User-Facing Improvements

These items are small, scoped changes that deliver noticeable player value without requiring new systems or heavy
architecture. They are ordered by a rough impact/effort ratio, and they respect the v2.35+ constraint that every
update reduce net source LOC (features that add code must first offset it by removing or compacting existing code).

### P1 — Verification (merged without review)

- [ ] **Backfill tests for merged low-hanging fruit**
  - **Why:** The two checked-off items below (chat WebSocket streaming, dweller visual equipment) were merged without
    code review. They need regression coverage before they can be considered verified.
  - **What:**
    - **Chat WebSocket streaming** (`backend/app/api/v1/endpoints/websocket.py`): integration test covering the full
      chat round-trip over the socket (`ping`/`typing`/`message`), error paths, and the REST fallback removal safety.
    - **Dweller visual equipment** (`backend/app/schemas/dweller.py:90-93`): test that `accessory`/`object_held`
      generation is constrained to equipped/owned inventory items and cannot show unowned items.
  - **Effort:** medium.

### P2 — Quality of Life

- [ ] **Incremental `ty` cleanup** — run `ty` on touched Python files and resolve clear, local diagnostics as part of
      ordinary changes. Keep this non-blocking and avoid widening feature work solely to chase pre-existing type debt.

- [x] ~~**Fix silent incident fetch failure**~~ — ✅ **Done.** `incident.ts` already routes errors through `handleStoreError` (line 75). The `.catch(() => {})` mentioned in the original plan no longer exists at that location.

- [x] ~~**Gate or remove the Objectives debug overlay in production**~~ — ✅ **Done.** The `ObjectivesDebugOverlay.vue` component no longer exists in the codebase. The debug panel was removed in a prior cleanup.

- [x] ~~**Add notification click-through navigation**~~ — ✅ **Done.** `NotificationBell.vue` already has `handleNotificationClick` with `getNotificationRoute()` that navigates to the relevant view based on `notification_type` (exploration, training, quests, dweller detail, etc.).

### P1 — Resource Economy (aligns with current trajectory)

- [x] ~~**Surface resource trend alerts from existing rate/forecast data**~~ — ✅ **Done.** `ResourceBar.vue` already has `isDrainingCritical` (persistent warning when resource is draining and critically low), trend arrows, and tooltip with rate/forecast. The `useResourceWarnings` composable already shows toast warnings from backend `resource_warnings`.

### P1 — Gameplay Gaps

- [x] ~~**Implement the vault-level event system stub**~~ — ✅ **Done.** `game_loop.py:_process_events` (line 576-646) fires weighted random vault events: raider scout (spawns incident), resource cache (awards caps + notification), wanderer (awards caps + notification). Configured via `VaultEventConfig` in `game_config.py`. Only fires when user is online and vault has minimum population.

- [x] ~~**Fix missing exploration rewards**~~ — ✅ **Done.** `coordinator.py:_apply_rewards` (line 411-485) delivers caps to vault, calculates/applies XP with survival + luck bonuses, transfers loot to storage, returns unused stimpaks/radaways, emits item collection events, and publishes SSE completion events with full rewards summary.

### P1 — Combat Power Overhaul (all stats + weapon type) — ✅ Done

**Shipped:** `combat_power()` is now a weighted sum across **all seven SPECIAL stats**, with the weapon type
choosing which stats dominate. Weights are config-driven via `COMBAT_WEAPON_STAT_WEIGHTS` (JSON dict keyed by
weapon type + `unarmed`; replaces the removed `COMBAT_DWELLER_*_WEIGHT` vars):

| Weapon type | Primary stats (0.3)      | Secondary stats (0.15) |
| ----------- | ------------------------ | ---------------------- |
| Melee       | Strength, Agility        | Endurance, Luck        |
| Guns        | Perception, Agility      | Luck, Strength         |
| Energy      | Intelligence, Perception | Endurance, Luck        |
| Heavy       | Strength, Endurance      | Perception, Agility    |

Unarmed uses a balanced spread with a strength lean (0.2 S, 0.1 others). `DwellerReadLess` now exposes the equipped
`weapon_type` (eager-loaded) and the frontend `getCombatPower()` mirrors the same weight table. Arena + incidents
consume the same `combat_power()`; per-type unit tests cover primary-beats-secondary and cross-type reversals.

### P2 — Chat Polish

- [x] **Stream chat messages over the existing WebSocket**
  - **Where:** `backend/app/api/v1/endpoints/websocket.py:44-51`
  - **Issue:** The WebSocket endpoint handles `ping` and `typing`, but for `message` it only acks and tells the client
    to use REST. `DwellerChat.vue` already uses the socket for typing indicators.
  - **Fix:** Move the full chat round-trip to the socket so messages feel immediate and the REST fallback can be
    removed.
  - **Effort:** medium.

### P3 — Consistency

- [x] **Wire dweller visual equipment to actual inventory**
  - **Where:** `backend/app/schemas/dweller.py:90-93`
  - **Issue:** `accessory` and `object_held` are free-text fields marked `# TODO: Choose from inventory`, so generated
    dweller visuals can show items the dweller does not own.
  - **Fix:** Constrain visual-attribute generation to equipped or owned items.
  - **Effort:** medium.
- [x] **Bigger status badge in dwellers grid view**
  - **Where:** `frontend/src/modules/dwellers/components/grid/DwellerGridItem.vue`
  - **Issue:** the status badge is small relative to the card, hurting at-a-glance readability compared with the
    list view.
  - **Fix:** moved to a labeled `medium` overlay on the card thumbnail (top-left), out of the cramped header badge
    row; keeps the styleguide's live-status intent.
  - **Effort:** small. ✅ Done

---

## Planned Features (Future)

### Phase 1: Core Gameplay

- Room management improvements (optimal dweller suggestions)
- Crafting system (weapons/outfits with recipes)

### Phase 2: Advanced Gameplay

- Combat enhancements (statistics, log/replay)
- Exploration enhancement (events with choices; "journal" is now the near-term Wasteland Journal release — see World Map plan above)
- ~~Family visualization (relationship graph, family tree)~~ → **now the next big feature** (see Planned above)

### Phase 3: Endgame

- Pet system, legendary dwellers
- Merchant system, economy
- Achievement system, daily/weekly challenges
- **Dead Dweller Reuse System**
  - Soft-delete permanently dead dwellers (keep data)
  - Reuse as raiders attacking other vaults
  - Transformation chance: ghoul, synth, super mutant
  - Cross-vault encounters with former dwellers

### Apprentice System & Pets — design fragments (Issue #470)

Loose fragments from the #470 discussion, recorded so the decisions aren't lost.

- ✅ **Apprentice eligibility & accrual** — `child` **and** `teen` age groups (not `adult`). Shipped: boosted
  vaults seed apprentices, the game tick advances the room's SPECIAL per training-duration interval
  (`_process_apprenticeships`), per-stat gains convert into adult stats at maturity, and room-details render
  apprentice slots.
- ✅ **Apprentice rooms** — `RoomTypeEnum.PRODUCTION` + `RoomTypeEnum.CRAFTING` (covers weapon/outfit crafting
  and research-style production).
- ✅ **Large room placement near elevators** — vault grid widened to 10 tiles (`GRID_X_MAX = 9`); full-width
  crafting rooms place at x=1 beside the elevator shaft without overlapping it.
- ⬜ **Production/crafting bonus** — scaled by the apprentice's accrued SPECIAL skill, not a flat percentage;
  the more skilled the apprentice, the larger the room efficiency bonus. Remaining follow-up.
- **Pets** — assign to **living quarters (`CAPACITY`)** and **training rooms (`TRAINING`)**; intentionally NOT production/crafting rooms (a pet in a power plant or diner makes no sense). Pets remain a larger feature (new `Pet` model + assignment) tracked under Phase 3.

### Phase 4: Multiplayer

- Social features (friends, vault visits, leaderboards)
- Cloud saves, multi-device sync

---

## Technical Debt

### Backend

- [x] Router consolidation: Merge small routers into logical groupings
- [x] MinIO → RustFS migration
- [x] Alembic enum sync — `compare_type=True` in online mode
- [ ] Performance testing: Locust in nightly CI
- [ ] Datetime consistency: Migrate all `datetime.utcnow()` to aware `datetime.now(UTC)`
- [x] Test coverage target 80% — achieved 82.44%; enforced via nightly/master coverage workflow with `--cov-fail-under=80`
- [ ] Reduce test flakiness — the suite runs on an in-memory SQLite engine with a single `StaticPool` connection, which
      serializes cross-session work and limits concurrency-sensitive tests (e.g. row-lock/`FOR UPDATE` guarantees are
      not exercisable). Consider a per-test transactional Postgres/`pytest-postgresql` harness for race-condition
      coverage and to harden `test_vault` segfaults under garbage collection.
- [ ] Docstring coverage: AI settings / chat services sit at ~32% (ruff `D` rules) vs the 80% repo target — add
      module and public-method docstrings to `app/services/ai_service.py`, `app/services/chat_service.py`,
      `app/crud/ai_settings.py`.
- [ ] `AIService.reconfigure` mutates the global `settings` object (save/restore via `setattr`) instead of building a
      scoped override — refactor to a pure settings-builder so concurrent requests can't observe intermediate values.

### Frontend

- [x] Vue architecture refactor → COMPLETED (v2.1.0)
- [ ] Component refactoring: Break down large components (DwellerCard, RoomGrid)
- [ ] Reduce Vitest teardown flakiness — parallel runs intermittently hit `EnvironmentTeardownError`
      ("Cannot load ... after the environment was torn down", e.g. `RoomGrid.test.ts` / `RoomDetailModal.vue`).
      Investigate module-teardown ordering / `sequence` isolation so CI is deterministic.
- [ ] Chat error accessibility: announce send failures through a live region (`role="alert" aria-live="polite"`) in the
      chat UI instead of only console logging.
- [ ] `useChatMessages.ts` error mapping: fall back to `detail ?? 'Failed to send'` so API `detail` strings surface to
      the user instead of a generic message.

### DevOps

- [x] Docker build automation → COMPLETED
- [ ] Deploy immutable images: build and promote commit-SHA tags; production deployments select an explicit tested tag,
      never `latest`
- [ ] Run database migrations as a dedicated, pre-rollout Kubernetes Job and abort deployment if it fails
- [ ] Add migration safety checks to backend CI (`alembic check` and `alembic current --check-heads` against PostgreSQL)
- [ ] Add deterministic seed data and critical Playwright journeys, including stable visual regression baselines
- [ ] Test the rollback workflow against a known image tag; automate staging while retaining manual production approval

---

## Progress Metrics

### Current Stats (Aug 2026)

- **Backend**: 25+ routers, 100+ endpoints, 19+ services, **82.44% coverage**
- **Frontend**: 60+ Vue components, 10 feature modules
- **Tests**: Frontend 867+, Backend 1500+
- **Models**: 20+ database models

### Version Milestones

| Version | Release      | Highlights                                                                                                                             |
| ------- | ------------ | -------------------------------------------------------------------------------------------------------------------------------------- |
| Next    | In review    | Arena & Incident Combat Update: battle playground, incident cap + fast tick, room fight UI                                             |
| v2.42.0 | TBD          | The Family Update: MARRIED stage + lineage API + Family tab; QoL test backfill + migration-safety CI; Pydantic AI/Logfire verification |
| v2.41.2 | Aug 19, 2026 | Quest storage 500 fix, EventBus cross-loop race fix                                                                                    |
| v2.41.1 | Aug 18, 2026 | Frontend audit CRITICAL/MAJOR fixes (design tokens)                                                                                    |
| v2.41.0 | Aug 17, 2026 | Chat WebSocket, vault events, notification navigation                                                                                  |
| v2.40.0 | Aug 15, 2026 | Training tab UX (occupancy cards, live progress)                                                                                       |
| v2.39.x | Aug 14, 2026 | Resource production corrections, thumbnail URL fix                                                                                     |
| v2.38.0 | Aug 14, 2026 | Safe room construction, visual inventory                                                                                               |
| v2.32.0 | Aug 12, 2026 | Ruff rule cleanup + Google-style docstrings                                                                                            |
| v2.31.0 | Aug 12, 2026 | Map registration retry + failure notification, bio backfill fixes                                                                      |
| v2.30.0 | Aug 11, 2026 | Frontend refactor (async actions, SSE fallback, typecheck)                                                                             |
| v2.29.0 | Aug 10, 2026 | Map unlock on chat, dweller-location `is_unlocked`, UI polish                                                                          |
| v2.28.0 | Aug 09, 2026 | Template-based bio filler + retroactive bio place backfill                                                                             |
| v2.27.0 | Aug 2026     | Test coverage push, pytest-xdist speed-up                                                                                              |
| v2.26.0 | Aug 07, 2026 | Alembic enum sync + PG enum regression tests                                                                                           |
| v2.25.0 | Aug 07, 2026 | Map declutter, 160-world scaling, pregen service                                                                                       |
| v2.24.0 | Aug 07, 2026 | World Map (schematic map, discoveries, bio places)                                                                                     |
| v2.23.1 | Jul 13, 2026 | Vue 3.5 Reactive Destructure Migration                                                                                                 |
| v2.23.0 | Jul 01, 2026 | Chat WebSocket migration                                                                                                               |
| v2.22.0 | Jun 28, 2026 | Terminal Background Cleanup                                                                                                            |
| v2.21.0 | Jun 24, 2026 | SSE Polish (incident/game-tick SSE)                                                                                                    |
| v2.20.0 | Jun 22, 2026 | FE Simplification (YAGNI + DRY)                                                                                                        |
| v2.19.0 | Jun 21, 2026 | SSE streaming + Dict-to-Pydantic refactoring                                                                                           |
| v2.18.0 | Jun 21, 2026 | Library skills audit                                                                                                                   |
| v2.17.0 | Jun 19, 2026 | Medical storage refactor                                                                                                               |
| v2.16.0 | Jun 18, 2026 | Accessibility, CRT theme, test fixes                                                                                                   |
| v2.15.0 | Jun 18, 2026 | Dweller visual unification                                                                                                             |
| v2.14.4 | Jun 17, 2026 | Security dep bumps                                                                                                                     |
| v2.13.1 | May 19, 2026 | Security hardening                                                                                                                     |
| v2.13.0 | May 01, 2026 | Dramatiq migration                                                                                                                     |
| v2.12.0 | Apr 23, 2026 | Test suite green, MinIO removed                                                                                                        |
| v2.11.0 | Mar 19, 2026 | Vite+ toolchain                                                                                                                        |
| v2.10.9 | Mar 13, 2026 | AI quota system                                                                                                                        |
| v2.10.0 | Feb 10, 2026 | Quest & Objective system                                                                                                               |
| v2.9.0  | Feb 07, 2026 | Chat exploration actions                                                                                                               |
| v2.8.0  | Jan 29, 2026 | Easter eggs, changelog system                                                                                                          |

### v2.42.0 Observability Measurement (Pydantic AI & Logfire)

Verified the Gateway path is live and documented (see `docs/backend/PYDANTIC_AI_GATEWAY.md`): `PYDANTIC_AI_GATEWAY_API_KEY`
sets `ai_provider_mode == "gateway"` and `AIService._initialize_gateway()` builds the Gateway provider; Logfire
instruments Pydantic AI with `include_content=False`.

| Metric                             | Value                                                                                                             |
| ---------------------------------- | ----------------------------------------------------------------------------------------------------------------- |
| Deterministic agent-contract tests | 12 (`test_agents/test_dweller_agent_contracts.py`)                                                                |
| Output-validation retry coverage   | covered via `TestModel` (`validate_dweller_chat_output`, `test_invalid_structured_output_retries_before_failing`) |
| Logfire config tests               | 3 (`test_logfire_config.py`) — config + `instrument_pydantic_ai(include_content=False)` both paths                |
| C4 verification run                | `test_logfire_config.py` + `test_dweller_agent_contracts.py` → 13 passed                                          |

No agent code changes were required — the Gateway path and instrumentation were already correctly wired; measurement
recorded per D8. No gaps found; no future ROADMAP items added from this workstream.

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

_Last updated: 2026-08-30_ (apprentice fragments updated: eligibility/accrual, rooms, and elevator-adjacent
placement shipped; the SPECIAL-scaled production/crafting bonus remains open, tracked in #470. Service
simplification & unification is in review on `refactor/breeding-exploration-debt`.)
