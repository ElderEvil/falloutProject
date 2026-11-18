# HTTP Client Consolidation Plan (Axios Boundary)

Status: in progress — Batch 1 merged; chat/radio, exploration, social and rooms transport migrated; remaining stores pending

**Axios remains the supported transport.** This document defines the staged
consolidation of frontend HTTP onto the shared API boundary in
`src/core/utils/api.ts`. Reimplementing token refresh, retries, and request
handling on another transport would add maintenance work without a demonstrated
user benefit (the saving is ~14 kB gzip against a bundle already carrying Vue,
Reka, and Tailwind). Pinning and lockfile policy checks reduce supply-chain
exposure but do not eliminate it — the deciding factor is maintenance cost
without user gain.

## Approved sequence

1. **Completed (Batch 1):** create `src/core/utils/api.ts` as a **typed boundary** over
   `@/core/plugins/axios`. Named helpers (`apiGet`/`apiPost`/`apiPut`), an `api.*` sugar object
   (`api.patch`/`api.delete` inline their single-use wrappers), and `apiRequest` (full `AxiosResponse`
   escape hatch — see below). Errors normalize to `ApiError { status, detail, fields,
   headers, cause }`; `getErrorMessage` reads both `ApiError` and raw `AxiosError`.
2. **In progress:** migrate remaining services and stores in module-sized slices. Chat/radio,
   exploration, social and rooms call sites moved to their module APIs in the dated slices below.
3. **Later (separate slice):** remove the axios interceptor's notifications so toasts are
   caller-owned end to end.
4. **Toasts stay caller-owned as the target state.** The boundary throws and never
   notifies. During migration, the interceptor and callers share error-notification
   ownership through `claimErrorNotification`: a failure and its `cause` chain are
   notified once. Callers use `handleStoreError` or `notifyErrorOnce`; message extraction
   and inline error state still work after another layer has notified. Independent
   failures remain visible, including identical messages from separate requests.
5. **`apiRequest` is for call sites that need status or headers.** Prefer the
   data-returning helpers for ordinary calls; keep response access where status
   or headers matter. No migration deadline — it rides the axios transport.

Batch 1 migrates: core public reads (AssetGalleryView), auth service/views, profile services +
store + SettingsView, and ai-settings service.

## Migration log

| Date | Slice | Result |
| --- | --- | --- |
| 2026-10-28 | Batch 1 boundary (`src/core/utils/api.ts`) | In tree and used by 20 `api/` and `services/` modules. |
| 2026-10-28 | Chat + radio transport | `modules/chat/api/chat.ts` owns history, text and voice calls; `modules/radio/api/radio.ts` owns stats, mode and recruit. `DwellerChat.vue`, `useChatMessages.ts` and `useRadioRoom.ts` no longer import the axios plugin or build Bearer headers. |
| 2026-10-29 | Exploration transport | `modules/exploration/api/exploration.ts` owns dispatch, heading suggestion, send, list, detail, progress, recall, complete, overflow resolution and pending overflow. The exploration store no longer imports the axios plugin or threads a token; only its SSE subscription still passes a token. |
| 2026-10-29 | Social transport | `modules/social/api/relationship.ts` owns list/detail/create/romance/partner/marriage/breakup/compatibility/breeding; `modules/social/api/pregnancy.ts` owns list/detail/deliver. Both social stores no longer import the plugin, and the one-method `relationshipService` pass-through is gone. |
| 2026-10-29 | Rooms transport | `modules/rooms/api/room.ts` owns list, buildable, build, destroy, upgrade, remodel, style, grid config and rush; `modules/rooms/api/barbershop.ts` owns status and appearance changes; `modules/rooms/api/arena.ts` owns state, creatures, fighter selection, match controls/skills and event clearing. Neither the room store nor the arena store imports the plugin or threads a token, and the barbershop service pass-through is gone. |
| 2026-11-18 | No-token services | `storageService`, `craftingService`, `notificationService`, `objectiveService`, `consoleApi`, `lineageService` and `happinessService` now use the boundary; no call-site signature changed. Void endpoints use `apiRequest` so an empty response is never read as `.data`; `happinessService` keeps the full response via `apiRequest`. |
| 2026-11-18 | Token-bearing equipment, trading and response transport | `combat/services/equipment`, `trading/services/tradingService`, `contamination-team/api/roster` and `exploration/api/expeditionSite` use the boundary; the equipment store, response-station store/service, `DwellerEquipment`, `DwellerResponseTeamStatus`, `ResponseStationDetail` and `TradingPostPanel` no longer accept or pass an auth token. Unused `dwellerId` parameters were dropped where the endpoint never used them. Session invalidation now reads `authStore.sessionGeneration` instead of a transport token, so delayed equipment and response-station responses are discarded after an account switch or logout. |
| 2026-11-18 | Incident, dweller, map and training transport | `combat/api/incident`, `dwellers/services/dwellerService`, `map/services/mapService` and `progression/services/trainingService` use the boundary. Incident overflow/team/detail calls, map polling and fetch, training mutations, and dweller roster/detail reads no longer thread a token; stores keep `sessionGeneration` for stale-response and session-change invalidation. SSE headers stay token-based and allowlisted. |
| 2026-11-18 | Dweller, quest and vault stores | `dwellerDeath`, `dwellerGeneration`, `dwellerManagement`, `dwellerMedical`, `exitRequests`, `progression/quest` and `vault` now call module `api/` functions; transport token parameters are gone. `dwellerFilter` uses `sessionGeneration` for in-flight identity. Vault SSE reads the token through `core/utils/authToken` to avoid a vault/auth import cycle. |
| Done | Batch 3 | No consumer imports `@/core/plugins/axios`; only `src/core/utils/api.ts` talks to axios. SSE setup is the only token-bearing path (allowlisted). |

## Action notifications

- Show one final confirmation per action; use existing busy state for progress instead of an extra informational toast.
- Bulk actions report one total. A partial failure keeps the remaining work available and must not report full success.
- Preserve the original error or its `cause` when rethrowing, so HTTP/store/UI handlers recognize the same failure.
- `_skipErrorNotification` leaves the caller responsible for feedback, including expected responses explained in the UI.
- Distinct progression events and partial-success warnings remain visible; they are not duplicate confirmations.

## Migration parity checklist (per slice)

Before removing a token parameter or an internal header, confirm:

- **Response unwrapping** — `apiGet`/`apiPost` return the payload; callers that read `.data` move to `apiRequest`.
- **Void endpoints** — use `apiRequest`, not the data-returning helpers, so an empty response is never dereferenced.
- **Status/headers** — call sites that need them keep `apiRequest` (full `AxiosResponse`).
- **Cancellation** — `signal` is forwarded through `ApiRequestOptions`.
- **Token refresh** — the axios interceptor remains the only refresh owner; migrated call sites must not reimplement it.
- **Error normalization** — failures surface as `ApiError`; `getErrorMessage` still reads both shapes.
- **Duplicate-toast suppression** — `claimErrorNotification` remains the single notification owner; do not add a second toast.
- **Module ownership** — transport stays in `modules/<name>/api` or `services`; stores never own HTTP calls.
- **Session invalidation** — account-owned stores capture `authStore.sessionGeneration` and discard late responses on change; never substitute the transport token for session identity.

Bearer allowlist: `core/plugins/axios.ts` (interceptor), auth-session code, and SSE/WebSocket setup may construct
`Authorization` headers. No module service or store may build one for a plain HTTP call.

## Why this consolidation (and why not fetch)

- Standardize HTTP behavior behind one typed boundary for easier testing and future changes.
- Keep the axios transport: its auth-refresh interceptor and error handling keep
  working byte-for-byte, and no test mocking has to be reinvented.
- A native-fetch rewrite was considered and rejected: ~14 kB gzip saved against
  reimplementing refresh, retries, and request configuration with no user-visible gain.

## Scope and non-goals

- In scope: frontend HTTP layer, service/store call sites, and tests that mock the HTTP client.
- Out of scope for planning phase: API contract changes, backend endpoint changes, and UX redesign.
- Out of scope for Batch 1: removing interceptor notifications, migrating SSE.
- Non-goals: replacing the axios transport, API contract changes, backend endpoint
  changes, UX redesign.

## Baseline snapshot (before migration)

- Validation status: `pnpm run lint`, `pnpm run typecheck`, `pnpm run test:run`, and `pnpm run build` pass.
- Tests: 845 passed, 1 skipped.
- Build artifact currently includes an axios chunk (`dist/assets/axios-*.js`) around 36 kB (about 14 kB gzip).
- Axios coupling includes:
  - `src/core/plugins/axios.ts` is the main coupling point (29 files import from `@/core/plugins/axios` across `src`, 25 under `src/modules`)
  - `src/core/utils/api.ts` is the new typed boundary (Batch 1); Batch 1 migrates 11 source files to it
  - Shared types/helpers in `src/core/types/utils.ts`
  - Many files (e.g., authService.ts, storageService.ts, equipment.ts and many others) import directly from `@/core/plugins/axios`
  - 6 files also import Axios types directly from `axios` (AxiosResponse, AxiosError)
  - Centralized interceptor/token refresh flow located in `src/core/plugins/axios.ts` (lines 64-232)
  - Guardrail policy below is the target for new/updated code during migration, not the current baseline usage.

## Consolidation phases

1. Boundary foundation (Batch 1, merged)
   - `src/core/utils/api.ts`: named helpers, `api.*` sugar, `apiRequest` escape hatch,
     `ApiError` normalization.
   - Migrate core public reads, auth, profile, ai-settings (11 source files).
   - Add boundary unit tests + `createApiClientMock`.

2. Call-site migration (incremental)
   - Scan and identify remaining direct imports of `@/core/plugins/axios`.
   - Migrate remaining stores/services/composables in small batches to `src/core/utils/api.ts`.
   - Keep each batch test-backed and releasable.

3. Toast ownership slice (separate, behavior-changing)
   - Remove axios interceptor notifications so toasts are caller-owned end to end.
   - Audit callers that rely solely on interceptor notifications first.

## Done criteria

- No direct `apiClient` calls outside `src/core/utils/api.ts` and its tests.
- Lint/typecheck/tests/build all green.
- Auth refresh and error-handling behavior verified by tests.

## Risks and mitigations

- Risk: auth refresh regressions.
  - Mitigation: add explicit parity tests before migration and keep fallback-safe retry logic.
- Risk: inconsistent error messages after type changes.
  - Mitigation: centralize normalization in one helper and test common backend error payloads.
- Risk: migration drags due to broad call-site usage.
  - Mitigation: move in module-sized batches with strict definition of done per batch.

## Guardrail policy during transition

- **Prohibited in feature code**: Any new direct runtime imports from the `axios` package (e.g., `import axios from 'axios'`) (type-only imports like `import type { AxiosResponse } from 'axios'` are allowed).
- **Prohibited**: Any new direct plugin-level axios consumers (e.g., `import apiClient from '@/core/plugins/axios'`).
- **Required**: Use the centralized HTTP boundary in `src/core/utils/api.ts` for runtime calls (e.g., `apiGet`, `apiPost`, `apiPut`, or `api.patch`/`api.delete`).
- **Allowed**: Type-only imports from `axios` for typing purposes only (e.g., `import type { AxiosResponse } from 'axios'`), but prefer migrating to adapter-compatible types.
- **Legacy code**: If legacy direct axios usage already exists:
  - Wrap it with a `// TODO: Migrate to src/core/utils/api.ts - see HTTP_CLIENT_MIGRATION.md` comment.
  - Immediately replace direct calls with the adapter/api functions (use `apiGet`, `apiPost`, etc. from `src/core/utils/api.ts`).
  - If a specific pattern is not yet supported, add a short-term shim in `src/core/utils/api.ts` that delegates to `apiClient` and add a migration note pointing to `api.ts` as the single source of truth.

The transport infrastructure (`core/plugins/axios.ts` and `core/utils/authSession.ts`)
uses Axios directly. The shared refresh request bypasses the authenticated client
so it cannot recursively trigger its own interceptor. Feature calls still go
through `api.ts`.

## Background requests

`usePolling` and GET SSE streams pause while the tab is hidden, the browser is
offline, or the session is absent. Returning refreshes the visible data once;
missed timer ticks are not replayed. Explicitly paused subscriptions stay paused.
One shared refresh operation serves HTTP, SSE, and the proactive refresh timer.
Invalid credentials use HTTP 401; permission failures remain 403. Rejected refresh
credentials end the session, while temporary failures preserve it and back off.
GET streams reconnect with the current token. The bell reloads its latest
notifications on reconnect and surfaces new unread progression events through
the same delivery handler. A submitted POST stream may finish while hidden and is never automatically replayed.

Store-owned subscriptions created outside a component scope must call `stop()`
(polling) or `close()` (SSE) when replaced, so their activity listeners are disposed.
