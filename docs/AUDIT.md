# Codebase Audit — 2026-09-17

> Consolidated follow-up to the 2026-09-01 audit. Every retained item was
> re-checked against the current tree. Resolved and superseded historical
> findings remain in the verification log to prevent stale work from returning.

## Validation performed

- `cd backend && uv run pytest app/tests/test_architecture/test_service_layer_guard.py -q` — 15 passed.
- `cd frontend && pnpm run lint && pnpm run typecheck` — passed.
- Read-only scans of endpoint/CRUD imports, frontend Axios imports, type escapes,
  inline styles, Compose files, CI, and test mocks.

The generated API types were already modified in the working tree and were not
changed during this audit.

## Priority findings

### P0 — Unauthenticated personal-notification WebSocket

- `backend/app/api/v1/endpoints/websocket.py:81-91` accepts `/ws/{user_id}` and
  registers it with `ConnectionManager` without authenticating the peer or
  comparing an authenticated principal to `user_id`.
- `frontend/src/modules/profile/views/ProfileView.vue:56-61` opens that route
  without a token. `ConnectionManager.send_personal_message()` routes personal
  notification payloads by this user ID.
- The adjacent chat route correctly validates its query token before accepting
  (`websocket.py:94-107`), making the omission unambiguous.

**Impact:** anyone who knows or guesses a user UUID can subscribe to that
user's personal WebSocket messages, including notification payloads.

**Recommendation:** use the chat route's token validation and ID match, or
retire this legacy socket in favour of the authenticated SSE stream. Add tests
for no token, an invalid token, and a valid token for another user.

### P0 — Any logged-in user can create a notification for any user

- `backend/app/api/v1/endpoints/notifications.py:54-65` accepts a client-supplied
  `NotificationCreate`, including `user_id`, but uses only `CurrentActiveUser`;
  the value is deliberately unused.
- The endpoint says it is for “admin/system use,” yet it has neither
  `CurrentSuperuser` nor an ownership restriction. There is no frontend caller,
  so it need not be a public player API.

**Impact:** an authenticated player can spoof arbitrary notifications to other
users and use the endpoint as a stored-notification spam primitive.

**Recommendation:** remove the public route if services are the only caller;
otherwise require `CurrentSuperuser`. Add a regression API test proving a
regular user is rejected and that the actor cannot select another user ID.

### P1 — Backend layer direction is enforced below services, but not at router entry

- The service/CRUD guard is green and raw SQL is no longer present in services.
- Nevertheless, 12 endpoint files/import sites still call CRUD directly:
  `notifications`, `relationship`, `storage`, `exploration`, `training`,
  `user`, `weapon`, `outfit`, `quest`, and `websocket`.
- Examples include training's domain orchestration and error mapping in
  `endpoints/training.py:19-48`, and quest-party validation/CRUD calls in
  `endpoints/quest.py:193-222`.

**Why it matters:** business rules, authorization sequencing, and exception
translation are still split between routers and services, contrary to the
project's endpoint → service → CRUD direction. It makes policy changes harder
to test outside HTTP and leads to repeated transport exceptions.

**Recommendation:** migrate vertical slices, not a broad mechanical rewrite:
start with notification, training, and quest-party application services. Then
add an AST guard for endpoint → CRUD imports, with a shrinking baseline only
where a direct read is intentionally retained.

### P1 — Frontend Store → Service → API boundary is still bypassed

- 23 non-service frontend modules import `@/core/plugins/axios` directly.
- This includes 15 stores: rooms, vault, exploration, radio, profile,
  progression (`quest`, `objectives`), social (`relationship`, `pregnancy`),
  and six dweller stores.
- `modules/rooms/stores/room.ts:3-145` illustrates the result: HTTP paths,
  bearer-header construction, Axios-specific error extraction, refresh
  orchestration, and Pinia state coexist in one store.
- Notification UI repeats the same pattern in
  `vault/components/shell/NotificationBell.vue:10-72` even though it is a
  cross-cutting domain with no module service.

**Recommendation:** introduce module API adapters/services (`roomService`,
`notificationService`, then progression services). Let the Axios interceptor
own auth headers, services own request/response typing, and stores own state
and user-visible action coordination. This is an application-service façade,
not a new generic abstraction.

### P2 — Test suite remains mock-heavy

- Current scan: 1,404 `AsyncMock`/`MagicMock` occurrences in 61 backend test
  files (down from 1,796 in the prior audit).
- Largest current concentrations: `test_dweller_ai.py` (130),
  `test_vault_service.py` (96), `test_game_loop.py` (95), and
  `test_crud/test_room.py` (92).

**Recommendation:** treat this as targeted test debt rather than a deletion
campaign. For CRUD tests already backed by SQLite, replace mock wiring with
real persistence assertions. Preserve distinct public-contract, regression,
authorization, concurrency, and error-path coverage per the test-pruning
policy.

### P2 — Type contracts still leak `any` at domain boundaries

- `StorageItemCard.vue` has a prop typed as `any` and nine casts.
- `TrainingStartModal.vue` casts dwellers to index SPECIAL stats dynamically.
- Chat WebSocket messages, notification SSE payloads, game balance settings,
  and several API responses also use `any`.
- The shared Axios error guard in `core/types/utils.ts:11-20` itself depends on
  `as any`, while callers also hand-roll Axios error parsing.

**Recommendation:** model storage as a discriminated union, model SPECIAL stat
keys explicitly, and centralize runtime event narrowing in typed adapters. Use
Axios's `isAxiosError` in the shared error adapter so module code only handles
`unknown` and domain-safe messages.

### P2 — Large components and repeated visual styling remain maintenance hotspots

- Current component sizes: `QuestCard.vue` 848 lines, `DwellerAppearanceEditor.vue`
  749, and `ArenaModal.vue` 710. Arena was reduced from the prior audit, while
  the other two remain large enough to mix UI and orchestration concerns.
- There are 80 `:style` bindings across 32 Vue files (down from about 155).
  The largest clusters are `PreferencesView.vue` (13), `VaultList.vue` (11),
  and `HappinessDashboard.vue` (8).

**Recommendation:** extract only cohesive composables—countdown state from
quest cards, appearance form state from the editor, and arena fight flow from
the modal. Add static `text-theme-*`/`border-theme-*` utilities for color
bindings; retain runtime styles only where the selected theme changes the value.

### P3 — Environment and CI hygiene drift persists

- `docker-compose.infra.yml` mounts Postgres at `/var/lib/postgresql`, while
  the default and local files mount `/var/lib/postgresql/data` for the same
  `postgres:18-alpine` image.
- Local RustFS maps `9000/9001`; default and infra map `9002/9003`.
  The worker shutdown command also differs between default/infra and local.
- `.gitignore` does not list `.uv-cache/` or a root `logs/` directory;
  `.codegraph` remains only in local `.git/info/exclude`.
- `frontend-ci.yml` still runs `pnpm run test -- --run` instead of the designated
  `pnpm run test:run`; several CI workflows use floating major action tags.

**Recommendation:** decide which Compose file is authoritative and document
intentional deviations; otherwise factor shared service definitions. Use the
package-script contract in CI and adopt one action-pinning policy.

## Simplification backlog

These are candidate reductions in accidental complexity identified during a
read-only source scan. They are intentionally separate from the priority
findings above: each needs a small, test-backed vertical slice rather than a
large mechanical refactor. Do not collapse the mandatory endpoint → service →
CRUD or frontend module boundaries while pursuing them.

### High confidence — one owner for pregnancy state

- `modules/social/stores/relationship.ts` and `pregnancy.ts` both own a
  `pregnancies` collection and independently request
  `/api/v1/pregnancies/vault/{vault_id}`.
- This creates duplicate loading/error policy and can leave the relationship
  view stale after an action handled by the pregnancy store.

**Recommendation:** retain `usePregnancyStore` as the sole pregnancy-state
owner and have relationship views consume it. Move HTTP access into the
module's service/API adapter as part of the existing Store → Service → API
migration.

### High confidence — retire the generic personal-notification WebSocket

- The generic `core/composables/useWebSocket.ts` contains URL management,
  reconnection, handler registration, wildcard dispatch, and untyped messages.
- Its only consumers are chat and the profile's legacy personal-notification
  socket. The latter duplicates authenticated notification SSE and is also the
  P0 unauthenticated socket above.

**Recommendation:** migrate profile updates to notification SSE, remove the
legacy socket, then colocate a typed, chat-specific WebSocket client in the
chat module. Avoid preserving a generic handler registry for one remaining
protocol.

### Medium confidence — consolidate history-aware navigation

- `useBackNavigation.ts` and `useGoBack.ts` both inspect browser history and
  select a fallback, but have distinct implementations and fallback rules.
- The former additionally supplies labels and breadcrumbs, while the latter
  interpolates route metadata.

**Recommendation:** establish one tested primitive for “history or fallback”;
let the breadcrumb helper layer labels on top. Preserve the current back versus
replace semantics and route-parameter interpolation.

### Medium confidence — remove the single-provider storage factory if no
provider roadmap exists

- `services/storage/base.py` defines a broad protocol and
  `services/storage/factory.py` always constructs the sole implementation,
  `RustFSAdapter`.
- There is no provider selection configuration or alternative adapter.

**Recommendation:** if supporting another object-store provider is not a
committed requirement, replace the factory with a cached RustFS dependency and
use a small capability protocol only where substitution is useful for tests.
Keep the adapter if a multi-provider roadmap is confirmed.

### Medium confidence, higher regression risk — make simple objective
evaluators declarative

- `services/objective_evaluators.py` uses eight subclasses and an explicit
  registration list. Several only supply event types, a simple target-field
  match, and a constant increment.
- `ReachEvaluator` has genuinely distinct absolute-progress behavior and must
  remain specialized.

**Recommendation:** preserve the shared transactional progress engine and
`ReachEvaluator`; model only the straightforward incrementing evaluators as
declarative registrations or predicates. Add characterization tests before
changing progression behavior.

### Low confidence / low risk — centralize sorted changelog reads

- `ChangelogService.get_entries()` and `get_latest()` both parse and sort the
  same changelog collection.

**Recommendation:** add one sorted-read helper. Decide explicitly whether an
invalid `since` version should remain silently ignored or return validation.

## Historical finding verification

| 2026-09-01 item | Current status | Evidence / disposition |
| --- | --- | --- |
| Unauthenticated debug mutation endpoints | Resolved | `endpoints/debug.py` no longer exists. |
| Dweller CRUD/game logic in router | Mostly resolved | Dweller actions moved into services and service-layer baselines are empty. Router→CRUD bypasses persist elsewhere; retained as P1. |
| Frontend direct Axios imports | Open, improved in places | Still 23 non-service consumers; retained as P1. |
| `game_loop` and `chat_service` god services | Resolved as originally scoped | Reduced from 891/659 lines to 323/214, with chat helpers and tick responsibilities split. |
| Mock-heavy tests | Improved, still open | Down from 1,796 to 1,404 occurrences; retained as P2. |
| Broad list of untested modules | Superseded | The old filename-derived list is no longer reliable: many named services now have direct tests. A future decision needs fresh coverage-context data. |
| Compose drift | Open | Reconfirmed; retained as P3. |
| Inline theme styles | Improved, still open | Down to 80 uses; retained as P2. |
| `as any` cluster | Improved, still open | Storage and training examples remain; retained as P2. |
| Swallowed errors / giant components | Partly open | `ProfileView.vue` still has two empty catches; the named large components remain. Folded into P2. |
| Repo hygiene | Open | Reconfirmed; retained as P3. |

## Merged audit verification

This section absorbs the former frontend skill audit, UI consolidation audit,
and test-coverage analysis. The source files are removed after this update;
feature-specific balance findings remain in `docs/features/BALANCE_FINDINGS.md`.

### Frontend skill audit (2026-08-18)

- **Resolved:** scans find no remaining camel-case terminal token utilities or
  references to the former undeclared `--color-terminal-green-*` variables.
  The router no longer patches its prototype or uses `any`; it wraps the router
  instance with a typed location and `unknown` error instead.
- **Retained elsewhere:** direct local-storage and Axios use overlap with the
  P1 frontend-boundary finding. The remaining 15 index-based `v-for` keys and
  49 raw timer calls are incremental review targets, not blanket violations:
  stable static lists and timers with explicit lifecycle cleanup are valid.
- **Not retained as a separate finding:** hardcoded-color and inline-style
  counts require a UI-context decision. The current 80 inline styles are
  retained in the P2 UI consistency finding instead of carrying stale file and
  line lists forward.

### UI consolidation audit (2026-09-04)

- **Resolved:** the old duplicate reward modal shell is gone; exploration
  duration and dweller equipment use `UModal`. Quests and Objectives use
  `UTabs`, and several simple progress indicators use `UProgressBar`.
- **Backlog, not defects:** standardizing async states, auth layout, controls,
  badges, navigation items, and remaining button variants should happen only
  alongside feature work. These are documented design-system opportunities,
  not a mandate to replace every domain-specific UI.
- **Retained elsewhere:** oversized components and duplicated styling remain
  covered by the P2 UI consistency finding above. Keep `UModal` as the modal
  foundation and require accessible labels/focus states on future icon actions.

### Test coverage analysis (historical)

- The old 70.93% baseline, 933-test count, per-file gaps, and four-week plan
  are obsolete. The document itself reported 82.44% coverage as of 2026-09;
  CI now enforces 80% and runs pytest with xdist, while `pyproject.toml` also
  configures parallel execution.
- No new coverage percentage is claimed here because a full coverage run was
  outside this documentation consolidation. Use a fresh coverage-context run
  before selecting new test work; the mock-heavy P2 finding is the current
  evidence-backed test-quality priority.

## Suggested order

1. Add failing regression tests and fix the two P0 authorization flaws.
2. Establish the notification module service/API adapter, then migrate training
   and quest-party flows through application services.
3. Remove direct Axios usage module by module, beginning with rooms and
   progression.
4. Address test mocks and UI/type cleanup as scoped follow-up batches.
