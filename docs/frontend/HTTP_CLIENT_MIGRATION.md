# HTTP Client Consolidation Plan (Axios Boundary)

Status: in progress — Batch 1 in review, not yet merged

**Axios remains the supported transport.** This document defines the staged
consolidation of frontend HTTP onto the shared API boundary in
`src/core/utils/api.ts`. Reimplementing token refresh, retries, and request
handling on another transport would add maintenance work without a demonstrated
user benefit (the saving is ~14 kB gzip against a bundle already carrying Vue,
Reka, and Tailwind). Pinning and lockfile policy checks reduce supply-chain
exposure but do not eliminate it — the deciding factor is maintenance cost
without user gain.

## Approved sequence

1. **Now (Batch 1):** create `src/core/utils/api.ts` as a **typed boundary** over
   `@/core/plugins/axios`. Named helpers (`apiGet`/`apiPost`/`apiPut`/`apiPatch`/`apiDelete`),
   an `api.*` sugar object, and `apiRequest` (full `AxiosResponse` escape hatch —
   see below). Errors normalize to `ApiError { status, detail, fields,
   headers, cause }`; `getErrorMessage` reads both `ApiError` and raw `AxiosError`.
2. **Batches 2–4:** migrate remaining services, stores, and the exploration/chat call sites in
   module-sized slices.
3. **Later (separate slice):** remove the axios interceptor's notifications so toasts are
   caller-owned end to end.
4. **Toasts stay caller-owned as the target state.** The boundary throws and never
   notifies — but the axios interceptor's notifications remain byte-identical for now,
   so both layers can notify today. Removing interceptor notifications is a separate
   behavior-changing slice, not part of the boundary work.
5. **`apiRequest` is for call sites that need status or headers.** Prefer the
   data-returning helpers for ordinary calls; keep response access where status
   or headers matter. No migration deadline — it rides the axios transport.

Batch 1 migrates: core public reads (AssetGalleryView), auth service/views, profile services +
store + SettingsView, and ai-settings service.

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

1. Boundary foundation (Batch 1, in review)
   - `src/core/utils/api.ts`: named helpers, `api.*` sugar, `apiRequest` escape hatch,
     `ApiError` normalization.
   - Migrate core public reads, auth, profile, ai-settings (11 source files).
   - Add boundary unit tests + `createApiClientMock`.

2. Call-site migration (incremental, Batches 2–4)
   - Scan and identify all direct imports of `@/core/plugins/axios` (29 files).
   - Migrate stores/services/composables in small batches to `src/core/utils/api.ts`.
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

- **Prohibited**: Any new direct runtime imports from the `axios` package (e.g., `import axios from 'axios'`) (type-only imports like `import type { AxiosResponse } from 'axios'` are allowed).
- **Prohibited**: Any new direct plugin-level axios consumers (e.g., `import apiClient from '@/core/plugins/axios'`).
- **Required**: Use the centralized HTTP boundary in `src/core/utils/api.ts` for runtime calls (e.g., `apiGet`, `apiPost`, `apiPut`, `apiPatch`, `apiDelete`).
- **Allowed**: Type-only imports from `axios` for typing purposes only (e.g., `import type { AxiosResponse } from 'axios'`), but prefer migrating to adapter-compatible types.
- **Legacy code**: If legacy direct axios usage already exists:
  - Wrap it with a `// TODO: Migrate to src/core/utils/api.ts - see HTTP_CLIENT_MIGRATION.md` comment.
  - Immediately replace direct calls with the adapter/api functions (use `apiGet`, `apiPost`, etc. from `src/core/utils/api.ts`).
  - If a specific pattern is not yet supported, add a short-term shim in `src/core/utils/api.ts` that delegates to `apiClient` and add a migration note pointing to `api.ts` as the single source of truth.
