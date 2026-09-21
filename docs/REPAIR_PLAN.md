# Repair Plan — audit findings, waved for review

> Source: codebase audit (2026-09-21) + `docs/AUDIT.md` (active P0: authorization flaws). This is a **plan only** — no code changes yet. Review the waves, then approve wave-by-wave for implementation.
> Rules that govern every wave: bug-fix workflow (failing test first), thin endpoints (parse → service → map), `endpoints → services → CRUD` never upward, `item_factory` for catalog rows, backfill-in-same-migration for data-bearing columns, progression events surface via modal/toast **in addition** to the bell.

## How to read this plan

- Each wave is independently shippable and ends with explicit **exit criteria** (tests + diagnostics).
- Waves are ordered by blast radius: data loss first, crash-loops second, architecture third, UI last.
- `P0/P1/P2` match the audit severities. Anything marked **verify** is a command to run before marking the wave done.

## Wave 0A — Authorization fixes (P0, before everything else)

**Goal:** close the two active authorization flaws (`docs/AUDIT.md` P0).

1. **Retire `/ws/{user_id}`** (`backend/app/api/v1/endpoints/websocket.py:81-91`) in favour of the authenticated SSE stream; remove its `ProfileView.vue:54-61` consumer (legacy unauthenticated socket — retire, do not extend). Keep the chat socket separate. Tests: no token, malformed token, mismatched subject, owner — handshake rejected before `manager.connect()`.
2. **Lock down `POST /notifications`** (`endpoints/notifications.py:54-65`): remove the public route (server-side callers already go through `NotificationService.create_and_send()`); if an operator endpoint is a real requirement, gate behind `CurrentSuperuser` with no player-facing recipient field. Tests: regular user rejected, actor cannot select another user ID.

**Exit:** regression tests green, touched-file `ty` check clean (see Wave 1 exit), full backend suite passes.

## Wave 0 — Data safety (P0, smallest, do first)

**Goal:** stop silent data corruption; no behavior change otherwise.

1. **Backfill `fire_resist` / `radiation_resist`** for pre-existing outfit rows.
   - Context: `backend/app/alembic/versions/2026_09_18_0002-7b2c4d9e1f30_add_outfit_hazard_resist.py:19-26` added `fire_resist NOT NULL default 0` + nullable `radiation_resist` with no backfill, while catalog declares values (`backend/app/data/items/outfits/rare.json:90,117`, `legendary.json:219-220`, asserted in `backend/app/tests/test_services/test_vault_service.py:455`).
   - Approach: new migration, name-keyed idempotent backfill (`LOWER(TRIM(name))`, update only rows still at default), `downgrade()` documented no-op. Copy `2026_09_19_0002`. Decision: keep `fire_resist` NOT NULL and backfill known catalog rows — do not make an established typed field nullable.
   - Test-first: extend `backend/app/tests/test_alembic/test_data_migrations.py` with a migration case (seed old rows → upgrade → assert catalog values; downgrade is no-op). Add/extend a `test_db/` fragment mirroring `test_backfill_outfit_special_bonuses.py`.
   - Verify: `uv run pytest app/tests/test_alembic/test_data_migrations.py app/tests/test_db/test_backfill_outfit_special_bonuses.py -q`; `uv run alembic upgrade head && uv run alembic check`.
2. **Assess `item.item_type` default `misc`** (`2026_09_01_0001:18`, no backfill). Confirm whether legacy generic-`item` rows can be non-misc; if yes, same backfill pattern, else record why the default is correct in the PR.
3. **Cover the untested repair migration** `2026_09_20_1200-f0e1d2c3b4a5` (`:42-128` greedy dedup): add a `test_data_migrations` case + `test_db/` fragment before touching anything else, so the next data repair is pinned.

**Exit:** new migration(s) green on fresh + existing DBs, migration tests pass, full backend suite passes.

## Wave 1 — Tick reliability + error contracts (P0)

**Goal:** end poisoned-session cascades, timezone drift, error leaks. No API shape changes except status-code corrections below.

1. **Rollback before reuse (poisoned sessions).**
   - Files: `backend/app/services/game_loop.py:72-74,149-151`, `game_tick/guard.py:21-25`, `game_tick/dwellers_tick.py:78-80`, `game_tick/family_tick.py:254-319`, `backend/app/api/tasks.py:246-263`.
   - Approach: `await session.rollback()` in every `except` that continues to reuse the session. `guard_phase` (`game_tick/guard.py:14`) takes no session, so the caller owns the rollback — or add an explicit session parameter; either way, decide once and apply uniformly. Keep `incident_tick.py:95,110` as the reference pattern.
   - Test-first: failing test with a real SQL transaction failure (not just a generic exception), e.g. second vault still processes after first vault DB error; per-entity guard test proving next entity proceeds.
2. **Background session compatibility.**
   - Files: `backend/app/api/tasks.py:65,166-168,73,174`, `backend/app/db/session.py:18-20,52`, `objectives/notifications.py:53`, `evaluators/base.py:64`.
   - Approach: route `game_tick`/`process_vault_tick` through `task_session()` (which carries the UTC `connect_args`) instead of inline engines; specify a ContextVar token/reset lifecycle for `set_current_session_maker` (reset after engine dispose) and bind the loop-local maker at the actor boundary, including for `task_session` actors (`incident_tick`, `arena_tick`), so handlers never use a dead-loop global maker.
   - Test-first: regression asserting tick sessions carry UTC settings and a post-dispose event handler does not reuse a disposed engine.
3. **Auth + error-mapping corrections.**
   - `api/deps.py:56-68`: catch `ValueError/TypeError` from `UUID(token_data.sub)` → 403, not 500. Test: signed token with bad/`None` sub → 403.
   - `deps.py:88,104-108`, `endpoints/user.py:146-149`: 400 → 403 (`AccessDeniedException`).
   - `endpoints/user.py:201-211,234-247`: replace broad `except Exception → 500 str(e)` with domain exceptions; never leak `str(e)`.
   - `endpoints/relationship.py:104-143,194-197`: stop mapping raw `ValueError` (wraps DB text at `relationship_service.py:309-312,508-511`); raise/map `ValidationException` in service.
   - `endpoints/pregnancy.py:56-84`: `AccessDeniedException` → 403, not 404.
   - Verify: endpoint tests asserting codes + no internal text in `detail`.

**Exit:** tick-failure tests green, touched-file `ty` check clean (`uv run ty check --output-format concise 2>&1 | grep <path>` empty for each touched file, except the `datetime.utcnow` convention), full backend suite passes.

## Wave 2 — Backend layering (P1)

**Goal:** endpoints thin; queries in CRUD, logic in services. Shrink guard baselines, never extend.

1. **Queries out of routers:** `game_control.py:158-162` (`select(Room)` → CRUD), `:218` + `objective.py:122` (`db_session.get` → CRUD/service). Drop `select/col` imports from endpoints.
2. **Workflows into services:** `quest.py:267-291` (`start_quest` get/refresh/availability/detail-string → `quest_service`; remove local re-import `:270`); `game_control.py:44-88` balance payload → assembler/service; `dweller.py:474-485` enrichment loop → `death_service`; `training.py:110-115` `TrainingProgress(**model_dump…)` → service; `user.py:83-91` `UserUpdate` assembly → `user_service`; `radio.py:111-112` range rule → `radio_service`; `storage.py:54-111`, `pregnancy.py`, `exploration.py:133-165`, `crafting.py`, `vault.py` response assembly → services.
3. **Access + encapsulation:** replace inline `vault_id !=` checks (`game_control.py:214-216,385-387`) with shared helpers (`get_user_vault_or_403` / `verify_dweller_access` / service check); `relationship.py:236-238` stop calling private `game_loop_service._process_breeding` — expose a public entrypoint honoring tick-session rules.
4. **Service coverage for CRUD-only routers:** migrate meaningful vertical slices into services for `notifications.py` (all 6 handlers), `weapon.py`, `outfit.py`, `junk.py`, `room.py`, `quest.py:61-167` — no thin forwarding modules. The only exception is narrowly documented read-only endpoint passthrough, enforced by a new AST endpoint→CRUD/session-query guard with a shrinking baseline. Keep `services/*_service.py` naming, flat `crud/`.
5. **Enums toward single source, one domain at a time:** migrate colocated enums into `app/core/enums.py` with compatibility re-exports at old import paths (`models/incident.py`, `notification.py`, `exploration.py`, `quest.py`, `quest_reward.py`, `quest_requirement.py`, `crafting_order.py`, `training.py`, `schemas/happiness.py`, `schemas/exploration_event.py`, `services/health_check.py:33`). Relocation alone creates no `ALTER TYPE` migration — update `PG_ENUM_LABELS_SNAPSHOT` + manual PostgreSQL migration only when values change, in the same commit.

**Exit:** architecture guards still green with smaller baselines, `ruff check`, `ty` on touched files, backend suite + `pnpm run types:generate` (wire shapes may shift).

## Wave 3 — Frontend progression + service layer (P1)

**Goal:** red-line compliance (modal/toast for every progression event) + `Store → Service → API`.

1. **Progression visibility (red line):** define an explicit event→surface matrix for the rule's scope — level-up, loot, training completion, quest/objective completion (`docs/backend/GAME_MECHANICS.md`) — each with bell entry **plus** modal/toast, never notification-only.
   - `vault/components/shell/NotificationBell.vue:117-140` (the SSE consumer) toasts only `hazard_team_joined` — add the matrix surfaces there.
   - Wire up `dwellers/components/LevelUpNotification.vue` (currently dead export) to the level-up event. `ProfileView.vue`'s legacy WebSocket is retired in Wave 0A — do not build baby/death toasts on it.
   - Test-first: component/store tests asserting each matrix event produces bell entry **plus** toast/modal.
2. **Route stores/views through services:** remove direct `axios`/`apiClient` from stores (`vault.ts:4`, `dwellerManagement.ts:3`, `dwellerMedical.ts:2`, `dwellerGeneration.ts:2`, `dwellerDeath.ts:3`, `exitRequests.ts:3`, `quest.ts:3`, `objectives.ts:3`, `relationship.ts:3`, `pregnancy.ts:3`, `profile.ts:7`, `exploration.ts:3`, `room.ts:3`, `radio.ts:3`), composables (`useRadioRoom.ts:10`, `useChatMessages.ts:3`), and views/components (`NotificationBell.vue:11`, `SettingsView.vue:464,497`, `ResetPasswordView.vue:4,40`, `ForgotPasswordView.vue:3,22`, `VerifyEmailView.vue:4,25`, `DwellerChat.vue:4,203`). Extend `authService` (reset/forgot/verify) and add missing vault/quest/objective services.
3. **Error handling:** replace 9× inline `toast.error + response.data.detail` in `progression/stores/quest.ts`, `catch (err:any)` in auth views, local `actionError` in `useRoomDwellers/Upgrade/Destroy`, raw toast in `changelogService.ts:33,43` with `getErrorMessage`/`handleStoreError`; fix silent `catch{}` (`ProfileView.vue:129,147`) and `.catch(()=>{})` (`profile.ts:129`, `useSoundProfileSync.ts:34`, `PreferencesView.vue:59`).
4. **Types + markup hygiene (separate cosmetic PRs, last):** delete local dups in favor of `api.generated.ts` (`objective.ts:19-50`, `relationship.ts:49-77`, `equipment.ts:1-72`, `pregnancy.ts:8-40`, `NotificationBell.vue:13-23`, `changelogService.ts:4-14`); replace static inline `style="color: var(--…)"` (`RadioStatsPanel.vue:102,120,142`, `NavBar.vue:197`, `GaryOverlay.vue:34,39`, `DwellerCard.vue:137`, `VaultList.vue`, `PreferencesView.vue`) with tokens/utilities; prefer `U*` over native buttons/inputs in high-density files; fix `DwellerDetailContext.ts` location, `storage/routes.ts` naming, `SettingItem.vue` prefix.

Ship Wave 3 as: (a) notifications/social state ownership first, then (b) one feature domain per PR, with (c) cosmetic cleanup separate and last.

**Exit:** `pnpm run lint && pnpm run typecheck`, `pnpm run test:run` green; no store/component imports `axios` directly (except service/api layers).

## Wave 4 — Migration + test hygiene (P2)

1. **Decouple migrations from app code:** freeze data/logic inside `2026_09_12_0001:134`, `2026_09_12_0002:78-83`, `2026_08_14_*`, `2026_01_26`, `2026_01_08` (copy the `2026_09_19_0002` frozen-snapshot rationale) so future refactors can't break `alembic upgrade head`.
2. **Lint the unlinted:** either include `app/alembic` in ruff/ty or add a migration-specific check; fix 120-col breaches; document no-op `downgrade()`s (`2026_08_12_0001:24`, `2026_09_13_0004:28`, `2026_09_19_0001:31`).
3. **Tests:** remove dead `unit`/`e2e` marker defs (`pyproject.toml:254-257`) or use them; move `RSS_GROWTH_MAX` (`test_memory_regression.py:91`) out of class state; keep one behaviorally-distinct test per contract when pruning (record scope/count/coverage delta in PR).

**Exit:** `uv run prek run` clean on staged files, `alembic upgrade head && alembic check && alembic current --check-heads`, backend suite + coverage delta reported.

## Suggested order & sizing

- Wave 0A (1 PR, security) → Wave 0 (1 PR, small) → Wave 1 (2–3 PRs: rollback, sessions, error codes) → Wave 2 (3–4 PRs by domain: game_control/quest, dweller/training/user, enums per-domain last) → Wave 3 (notifications/social first, then one feature domain per PR, cosmetics separate) → Wave 4 (1–2 PRs).
- Each PR: failing test first, `feat:`/`fix:` commits on `feat|fix/` branches, no pushes/merges without approval, `pnpm run types:generate` after any backend API change, touched-file `ty` check (`uv run ty check --output-format concise 2>&1 | grep <path>` empty, except `datetime.utcnow`).
