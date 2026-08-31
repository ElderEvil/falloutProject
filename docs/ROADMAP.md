# Fallout Shelter Game - Development Roadmap

## Vision

Build a fully-featured vault management simulation inspired by Fallout Shelter, with modern web technologies and
AI-powered dweller interactions.

---

## In Progress

**Current work:**

- [x] **v2.39.0–v2.42.0 released** — resource-rate corrections, training/chat/notification UX, vault event system,
      design-token migration, quest storage fix, postpartum breeding cooldown + last-name inheritance, The Family
      Update (married stage, lineage API + family tree, migration-safety CI, Pydantic AI/Logfire verification).
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

### Next update target — "The Overseer's Toolkit" (shipped, awaiting release)

**Shipped:** Overseer Briefing (vault state summary + unresolved-item tile count + direct response links), AI
reliability fixes (incremental structured chat streaming, shared quota-cache keys), UI consistency polish (page
rails/headers/metrics, Build control restored, glow tokens, exploration portraits and meters), production logging
(rotating JSON API log on a persistent volume; Ollama stays local-dev-only), and authenticated Playwright coverage
for the briefing route. Semantic Release picks the version at release time.

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

- ✅ **Shipped** — semantics defined (three intents, `--glow-0..3` tokens, `.badge-info/live/action` classes;
  informational badges demoted to quiet chips) and top offenders wired (`DwellerStats`, `DwellerGridItem`,
  `SidePanel`, `QuestsView`, `ExplorerStatsGrid`). Transient one-shot feedback (stat highlight, level-up
  celebration) stays a sanctioned exception.
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

- ✅ **Shipped** — `modules/rooms/models/roomParts.ts` part registry (`getRoomDetailParts(room)`) drives the ordered
  section list; special-room name-matching (`isRadioRoom`, `isVaultDoor`, `isOverseersOffice`) lives only in the
  registry; `RoomDetailModal` renders each section behind `has(part)`; composition tests assert the part list per
  room type; radio management normalized onto the shared action grid.
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

- ✅ **Shipped** — exploration journal polish (loot/health trail, consolidated progress math), discovery → map
  integration with deep-links and event-authoritative routes, globally seeded neighbor-vault signals (determinism
  fix), quest party-roster rendering, and the discovery-unlock fix (`register_discovery` links the exploring
  dweller; v2.46.1 backfill script repairs pre-fix rows).

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

### v2.34.0 — Pydantic AI Reliability & Observability (shipped; two follow-ups open)

**Shipped:** Logfire tracing of Pydantic AI runs (`include_content=False`, no-op when unconfigured), hardened chat
output contract (instructions migration, output validation/retry rules, deterministic `TestModel` coverage),
optional RustFS no longer delays startup (degraded health instead), and a read-only dweller activity briefing tool
grounding suggestions in live gameplay state.

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

### AI Layer Upgrade — Prompts, LLM Interactions, Admin & New Usage (Delivered through Plan 4 — see `docs/backend/AI_LAYER_PLAN.md`)

**Focus**: Make the AI layer observable, configurable, and cheap — per-consumer decision whether Pydantic AI agents stay, get upgraded, or get replaced with deterministic paths. Plans 0–4 are delivered; Plans 5–6 remain parked.

- ✅ **Plan 0 — Lock down `/objectives/generate`** — `GET /objectives/generate` was unauthenticated, token-spending (`AsyncOpenAI` + hardcoded `gpt-4-turbo`, no quota/logging, no frontend caller). **Deleted**: endpoint + `ChatService.generate_objectives` + dead imports removed; `GET /objectives/generate` now 404.
- ✅ **Plan 1 — Durable interaction metadata** — `LLMInteraction` now snapshots `provider`/`model`/`instructions_hash`/`instructions_snapshot` + `prompt_id` (FK already existed, now populated). Existing rows backfilled via server defaults; migrations `e6f7a8b9c0d1` and `f7a8b9c0d1e2`.
- ✅ **Plan 2 — Prompt Registry (immutable versions)** — `Prompt` now `version: int` + `is_active: bool`, `UNIQUE(prompt_name, version)` + partial unique index `ix_prompt_active_name WHERE is_active`. `PromptService.get_instructions()` reads active row via 60s TTL cache, falls back to hardcoded defaults on DB error. Seed: `backend/app/utils/seed_prompts.py` + `fo-cli seed-prompts` (4 rows: backstory/extend_bio/visual_attributes/chat v1).
- ✅ **Plan 3 — Usage analytics** — `AIUsageResponse` now `by_operation: list[AIOperationStats]` (GROUP BY usage) + `chat_heavy` flag (>80% chat share). `ai_usage_service._aggregate_by_operation` covers totals; daily trend deferred as separate GROUP BY day query. Snapshotted `provider`/`model` enables honest future cost math (image/audio excluded).
- ✅ **Plan 4 — sqladmin** — `LLMInteractionAdmin` shows tokens + provider/model + hash + created_at (search/sort), `PromptAdmin` shows version/is_active/template, `DwellerAdmin` shows bio flag; DRY truncation helper; 3 authenticated render smoke tests.
- ⏸️ **Plan 5 — Pre-generation shift (LM Studio/ComfyUI batch → curated content)** + **Plan 6 — New AI usage ideas** (incident narration, quest flavor, daily digest, dweller ambient chat) — parked, need product decisions + per-operation usage headroom before shipping.

**Guardrails:** no Pydantic AI framework migration, no per-request model/temperature per prompt, no retroactive cost truth; template-first.

### v2.35.0 — Release Version Integrity (Released 2026-08-14)

**Shipped:** Semantic Release is the single version authority — it synchronizes `pyproject.toml`/`uv.lock`/
`package.json` in its prepare phase and commits them before tagging; Conventional Commit squash-merge titles drive
SemVer (`feat`→minor, `fix`/`perf`/`refactor`→patch, `!`/BREAKING→major, others non-releasing); both Docker images
build from the release tag; a CI guard fails on any tag/package/changelog version disagreement.

**Engineering constraint (v2.35 onward):** Every update must reduce net source LOC. Features that require new code
must first offset it by removing or compacting existing code, favoring DRY reusable extraction over duplication. The
reduction excludes generated files, lockfiles, and formatting-only changes, and must retain behavior under relevant
tests.

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

### Bio Extension — Pre-Baked Templates + Living Biographies (Target: next updates — HIGH PRIORITY)

**User request**: dwellers should feel alive. Bios today are either empty or one-shot AI-generated text that
never changes. Two-part fix, reusing existing systems end to end.

- ⬜ **Pre-baked template bios** — a library of lore-safe bio templates in `backend/app/options/` (per
  race/faction/personality archetypes, with slot-filled name/origin variants). Applied at dweller creation
  (vault initiation, radio recruitment, breeding) so **every** dweller has a readable bio out of the box — no
  AI generation required, no cost, no latency.
- ⬜ **Action-driven bio updates** — append/rewrite bio entries when life happens:
  - **Exploration** — visited locations and notable events (the exploration event log and `DwellerLocation`
    relations already record the raw material; the bio writer just summarizes deltas).
  - **Marriage/breeding** — partner and children references when `partner_id`/parents are set (breeding service
    already owns these transitions).
  - **User dialogues** — the dweller chat agent already produces structured action cards; let it propose bio
    addenda from memorable conversations (opt-in, size-capped).
- ⬜ **Bio model** — keep `Dweller.bio` as the rendered text but store structured entries (timestamped,
  source-tagged: `template` / `exploration` / `family` / `dialogue`) so updates are additive and re-renderable
  instead of lossy string edits. Blocker: decide JSONB column vs side-table before implementation.
- ⬜ **AI upgrade path** — template bio first, optional AI rewrite of the compiled bio via the existing
  generation service for users who want richer text (quota rules already apply).

**Reuse:** options library, generation service + quotas, exploration event log, breeding service transitions,
chat agent action cards. **Blocker:** structured-entry storage decision (JSONB vs side-table).

### Boosted Vault Rarity & Race/Faction Diversity (Target: next updates — HIGH PRIORITY)

**User request**: boosted vaults should feel special, and vaults should not be 100% human.

- ⬜ **Boosted vault rarity boost** — vault initiation already seeds more dwellers (and apprentices) for boosted
  vaults; extend the seeding tables so boosted vaults get a higher rare/legendary share than the normal roll.
- ⬜ **Race diversity targets** — non-human share in seeded/generated populations: **~15% ghouls, ~10% synths,
  ~5% super mutants** (humans the remaining ~70%). Apply to vault initiation seeding and radio recruitment
  rolls; breeding inherits race from parents (ghoul/synth/mutant lineages stay consistent).
- ⬜ **Faction assignment** — seeded dwellers get lore-plausible factions from the existing faction options
  (vault_dweller dominant, others rare), so the identity dossier and future faction perks have data to work
  with.
- ⬜ **Consistency** — race/faction live in `visual_attributes` today; the Race & Faction Gameplay Mechanics
  fragment (above) is where modifiers/perks hook in. This item only diversifies **who exists**; it does not
  change mechanics.

**Reuse:** vault initiation seeding, radio recruitment rolls, `backend/app/options/` race/faction definitions,
breeding service. **Blocker:** none hard — seeding tables and roll weights are self-contained; coordinate with
the identity-metadata work so race is read from one source of truth.

---

## Low-Hanging Fruit — Immediate User-Facing Improvements

These items are small, scoped changes that deliver noticeable player value without requiring new systems or heavy
architecture. They are ordered by a rough impact/effort ratio, and they respect the v2.35+ constraint that every
update reduce net source LOC (features that add code must first offset it by removing or compacting existing code).

### P1 — High Priority (user-requested)

- [ ] **Bio extension** — pre-baked template bios for every dweller + living biographies updated on exploration,
      marriage, and dialogues. Full design in "Bio Extension" (Planned above). Start with the storage decision
      (JSONB vs side-table), then template application at creation — that alone is shippable.
  - **Effort:** medium (templates first), larger for action-driven updates.

- [ ] **Boosted vault rarity + race/faction diversity** — boosted vaults roll higher rare/legendary shares;
      seeded/recruited populations target ~15% ghouls, ~10% synths, ~5% super mutants. Full design in "Boosted
      Vault Rarity & Race/Faction Diversity" (Planned above). Self-contained seeding/roll changes.
  - **Effort:** small–medium.

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

- [x] **Done:** silent incident fetch failure (already routed through `handleStoreError`), Objectives debug overlay
      (removed), notification click-through navigation (`NotificationBell` routes by `notification_type`), resource
      trend alerts (`ResourceBar` draining-critical warning + `useResourceWarnings` toasts), vault-level event system
      (`game_loop._process_events`: raider scout / resource cache / wanderer), exploration rewards
      (`coordinator._apply_rewards`: caps, XP, loot transfer, SSE summary).

### P1 — Combat Power Overhaul (all stats + weapon type) — ✅ Done

**Shipped:** `combat_power()` is a weighted sum across all seven SPECIAL stats, weights config-driven via
`COMBAT_WEAPON_STAT_WEIGHTS` (JSON keyed by weapon type + `unarmed`; melee S/A primary, guns P/A, energy I/P, heavy
S/E; unarmed balanced with a strength lean). `DwellerReadLess` exposes the equipped `weapon_type` (eager-loaded); the
frontend `getCombatPower()` mirrors the table. Arena + incidents consume the same `combat_power()`; per-type unit
tests cover primary-beats-secondary and cross-type reversals.

### P2 — Chat Polish

- [x] **Chat streaming over WebSocket** — shipped in v2.41.0; regression coverage still owed (see P1 Verification).

### P3 — Consistency

- [x] **Done:** dweller visual equipment wired to actual inventory (generation constrained to equipped/owned items);
      bigger status badge in the dwellers grid view (labeled `medium` overlay on the card thumbnail, live-status
      intent preserved).

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

- ✅ **Shipped** — apprentice eligibility (`child` + `teen`), accrual via the game tick
  (`_process_apprenticeships`), apprentice rooms (`PRODUCTION` + `CRAFTING`), large-room placement beside the
  elevator shaft (`GRID_X_MAX = 9`), and room-detail apprentice slots.
- ⬜ **Production/crafting bonus** — scaled by the apprentice's accrued SPECIAL skill, not a flat percentage;
  the more skilled the apprentice, the larger the room efficiency bonus. Remaining follow-up.
- **Pets** — assign to **living quarters (`CAPACITY`)** and **training rooms (`TRAINING`)**; intentionally NOT production/crafting rooms (a pet in a power plant or diner makes no sense). Pets remain a larger feature (new `Pet` model + assignment) tracked under Phase 3.

### Onboarding — Guided Game Mechanics (design fragment, Target: TBD)

User requests for a first-session onboarding that teaches the game mechanics step by step. Written as the
player-facing requests the feature should satisfy; sequence and copy are up to implementation.

- ⬜ **Welcome & goal** — as a new Overseer, I want a short intro explaining my role and the vault goal, so I
  understand what I am doing before my first action.
- ⬜ **Power first** — guide me to build/assign my first power plant and explain why power gates everything else.
- ⬜ **Production chain** — walk me through water and food production, and show me what happens when a resource
  runs out.
- ⬜ **Assigning dwellers** — show me how SPECIAL stats map to rooms and let me try the auto-assign tools with an
  explanation of what they do.
- ⬜ **Vault expansion** — point me at building/elevators/room upgrades and merging at the right moment.
- ⬜ **Population basics** — explain living quarters capacity, breeding, and growth (radio recruitment later).
- ⬜ **Incidents & defense** — introduce incidents, weapons, and the arena when the vault is stable enough to
  survive a demo fight.
- ⬜ **Wasteland** — send my first dweller exploring with an explanation of stimpaks/radaways and recall.
- ⬜ **Progression loop** — objectives, quests, training, and where to find each system (links into the sidebar).
- ⬜ **Soft hooks** — after onboarding, surface the Overseer Briefing attention items instead of the tutorial.

Design notes: step order should follow actual dependency order (power → water/food → population → defense →
exploration); each step needs a skippable/dismissable state so returning players are not forced through it;
completion state should persist per user (localStorage or server-side).

### Celldweller Easter Egg (idea, Target: TBD)

In-game homage to the band Celldweller (fits the Fallout aesthetic — electro/industrial wasteland vibes).
Loose ideas, none committed:

- A legendary dweller named "Klayton" (or a wanderer named after band lore) with unique dialogue lines and
  Celldweller lyric references in their bio.
- A rare radio-station event: "Celldweller — Own Little World" plays as a special broadcast with a happiness
  bonus for the vault.
- A discoverable wasteland location on the world map (e.g. "Cell 23" / "End of an Empire" landmark) with a
  one-time loot drop or unique encounter.
- A crafting recipe or outfit skin referencing the band's visual style (chrome/black, glowing red accents).

Keep it optional, non-breaking, and discoverable — easter eggs should reward curiosity, never gate progress.

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
| v2.46.0 | Aug 21, 2026 | The Wasteland Journal: exploration journal polish, discovery → map deep-links, determinism fix                                         |
| v2.42.0 | Aug 20, 2026 | The Family Update: MARRIED stage + lineage API + Family tab; QoL test backfill + migration-safety CI; Pydantic AI/Logfire verification |
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

### v2.42.0 Observability Measurement (Pydantic AI & Logfire) — ✅ recorded

Gateway path verified live and documented (`docs/backend/PYDANTIC_AI_GATEWAY.md`): `PYDANTIC_AI_GATEWAY_API_KEY` sets
`ai_provider_mode == "gateway"`; Logfire instruments Pydantic AI with `include_content=False`. Measured: 12
deterministic agent-contract tests, output-validation retry coverage via `TestModel`, 3 Logfire config tests. No
agent code changes required; no gaps found.

---

Keep it optional, non-breaking, and discoverable — easter eggs should reward curiosity, never gate progress.

### Sound System — Fallout-Themed Music & SFX (Target: next updates — HIGH PRIORITY)

**User request**: a sound system with music and effects close to the original Fallout atmosphere (1950s radio,
ambient hums, terminal beeps, incident alarms). **The asset blocker is resolved** — a full Fallout-Shelter-style
library (music loops, per-room ambience, interface SFX) is available locally in `/assets/audio/` (git-ignored
source; curated copies land in `frontend/public/audio/`).

- ✅ **Audio manager foundation** — `core/audio/audioManager.ts` singleton with `ui`/`sfx`/`music` buses, persisted
  volumes + mute, autoplay-policy unlock on first interaction (pending loops start on unlock), silent no-op for
  missing assets; `soundManifest.ts` maps semantic keys to `/audio/...` URLs; `useSound()` composable.
- ✅ **First wiring** — notification chime on new SSE notifications (`NotificationBell`), vault ambient music loop
  on the vault view (`playLoop('vaultAmbient')`, stopped on unmount).
- 🔄 **UI & feedback SFX pass** — wired: global button-click `select` (delegated listener in the audio manager),
  room-modal `modalOpen` (close intentionally silent), chat typewriter key per keystroke in the message input
  (`typeKey`, fires on `beforeinput`), and `messageReceive` on dweller replies (WS + REST + audio paths via the
  shared messages watcher). Remaining: `cardDrop` on dweller drag-and-drop assignment, `upgrade` on room upgrades,
  `success` on completions, incident alarm on incident spawn (needs an incident event hook).
- ✅ **Preferences controls** — Sound card in PreferencesView (master enable + per-bus volume sliders), bound to
  the manager's persisted settings. **Sound is disabled by default**; enabling starts any pending music loop.
- ⬜ **Radio station integration** — the radio room already streams a station concept; pipe music through it
  instead of the view-level loop.
- ⬜ **Ambient layers** — per-room ambience loops from `assets/audio/sounds/ambience/` (armory, cafeteria,
  barbershop, ...) layered under the music loop.
- ⬜ **Curated-copy growth** — extend `frontend/public/audio/` from the source library per feature (keep the
  committed set small; the 295MB source library stays git-ignored).

**Reuse:** `GameEvent`/SSE streams as trigger sources, Preferences persistence pattern, radio room UI.
**Blockers:** none hard remaining — remaining work is wiring + curation.
**Deploy:** verified end-to-end — Vite copies `public/` into `dist/`, the frontend image serves it via `serve -s`,
and the git-ignored source library never reaches CI. No pipeline changes needed; revisit cache headers or
object storage only if the curated set grows large.

### Quests Improvements — Building Quests, Locked Chains, Puzzles (design fragment, Target: TBD)

User request: richer quest handling — construction-driven quests, properly locked quest chains, and
quiz/puzzle quests. Reuse-first: the quest model already has `chain_id`/`chain_order`, `previous_quest_id`/
`next_quest_id` links, and `QuestRequirement`/`QuestReward` relations; the objectives system and room
construction flow already emit state that quests can key off.

- ⬜ **Locked quest chains** — chain visibility/lock state in the UI: show the next chain quest as "locked"
  with its unlock requirement instead of hiding it. Blocker: chain unlocking today is purely linear
  (`previous_quest_id`); requirement-based unlocking (vault level, population, resource thresholds) needs a
  decision on whether `QuestRequirement` rows gain a condition type or a new gating model is added.
- ⬜ **Building quests** — quests whose completion condition is a construction action ("build a Water
  Treatment", "upgrade to tier 2"). Reuse the objectives system's condition checking if it can watch room
  events; blocker: room construction currently emits no quest-checkable event, so the objectives/quest
  completion path needs a hook into room create/upgrade.
- ⬜ **Quiz / puzzle quests** — timed quest with a question/choice step instead of auto-resolve. Blocker:
  quests are timer+party based (`duration_minutes`); there is no interactive step model, no question content
  format, and no frontend interaction surface. Needs a small content schema (question, choices, reward
  mapping) and a quest-detail interaction UI.
- ⬜ **Separate handling per quest kind** — type-specific completion flows (auto-resolve vs construction vs
  interactive) behind the existing `quest_type`/`quest_category` fields rather than new tables.

**Blockers (in order):**

1. Chain gating model decision (requirement conditions vs new table) — blocks locked chains.
2. Room construction → quest event hook — blocks building quests.
3. Interactive-step content schema + UI — blocks quiz/puzzle quests; largest of the three.

---

## Roadmap Direction & Blockers

Standing direction for picking work, in order:

1. **Low-hanging fruits first** — the P1/P2 items in "Low-Hanging Fruit" above always outrank new feature
   fragments when effort is comparable.
2. **Reuse & integration over new systems** — a feature that composes existing services (event bus, quest
   chains, recycling pipeline, objectives) beats a green-field design at equal value.
3. **Unblock before building** — when a feature is blocked, prefer work that removes the blocker over
   workarounds.

Current blocker map (what stalls what):

| Blocker                               | Stalls                                                                          | Unblocking work                                                              |
| ------------------------------------- | ------------------------------------------------------------------------------- | ---------------------------------------------------------------------------- |
| ~~Audio assets & licensing~~ resolved | Sound System → **HIGH PRIORITY** (manager shipped; SFX pass + Preferences open) | Assets available locally; curated copies in `frontend/public/audio/`         |
| Chain gating model decision           | Locked quest chains                                                             | Decide `QuestRequirement` condition types vs new gating table                |
| Room construction events              | Building quests                                                                 | Emit quest-checkable events on room create/upgrade                           |
| Interactive quest-step schema + UI    | Quiz/puzzle quests                                                              | Content schema + quest-detail interaction surface (largest quest item)       |
| Trading PoC validation                | Trading Post graduation (weapons/outfits tabs, coverage re-inclusion)           | Playtest the dweller loop, then graduate per the WIP sidebar marker          |
| Bio structured-entry storage decision | Bio extension (action-driven updates)                                           | Decide JSONB vs side-table; template bios are NOT blocked and can ship first |
| Onboarding step persistence decision  | Onboarding feature                                                              | Choose localStorage vs server-side completion state                          |
| World Map / multiplayer architecture  | Cross-vault encounters, Dead Dweller Reuse                                      | See World Map plan above                                                     |

---

## Priority System

- **P0**: Blocking bugs, security issues - fix immediately
- **P1**: Current sprint, essential features
- **P2**: Quality of life, UX polish
- **P3**: Technical debt, refactoring
- **P4**: Future features, nice-to-have

---

_Last updated: 2026-08-30_ (apprentice fragments updated; Onboarding, Celldweller easter egg, Sound System, Quests
Improvements, Bio Extension, and Boosted Vault Rarity & Race/Faction Diversity fragments added; Roadmap Direction &
Blockers map added; completed work compressed to shipped summaries.)
