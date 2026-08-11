# HTTP Client Migration Plan (Axios -> Fetch Adapter)

Status: planned (intent declared)

This document defines the staged migration away from `axios` to a native-fetch-based adapter.
No runtime behavior changes are part of this planning update.

## Why this migration

- Reduce dependency footprint and supply-chain exposure in the frontend runtime.
- Keep Vite+ config and tooling lean with fewer optional extras.
- Standardize HTTP behavior behind one adapter boundary for easier testing and future changes.

## Scope and non-goals

- In scope: frontend HTTP layer, service/store call sites, and tests that mock the HTTP client.
- Out of scope for planning phase: API contract changes, backend endpoint changes, and UX redesign.

## Baseline snapshot (before migration)

- Validation status: `pnpm run lint`, `pnpm run typecheck`, `pnpm run test:run`, and `pnpm run build` pass.
- Tests: 845 passed, 1 skipped.
- Build artifact currently includes an axios chunk (`dist/assets/axios-*.js`) around 36 kB (about 14 kB gzip).
- Axios coupling includes:
  - `src/core/plugins/axios.ts` is the main coupling point (29 files import from `@/core/plugins/axios` across `src`, 25 under `src/modules`)
  - `src/core/utils/api.ts` is only an optional typed wrapper used by ~2 files
  - Shared types/helpers in `src/core/types/utils.ts`
  - Many files (e.g., authService.ts, storageService.ts, equipment.ts and many others) import directly from `@/core/plugins/axios`
  - 6 files also import Axios types directly from `axios` (AxiosResponse, AxiosError)
  - Centralized interceptor/token refresh flow located in `src/core/plugins/axios.ts` (lines 64-232)
  - Guardrail policy below is the target for new/updated code during migration, not the current baseline usage.

## Migration phases

1. Adapter foundation
   - Introduce `src/core/plugins/httpClient.ts` with native fetch.
   - Preserve current behavior: auth header injection, refresh-on-401 flow, and normalized error mapping.
   - Add parity tests for success, 401 refresh, validation errors, and retry behavior.

2. Shared API helper migration
   - Update `src/core/utils/api.ts` to use the new adapter.
   - Remove axios-specific response/error types from helper internals.
   - Keep public helper function signatures stable where practical.

3. Call-site migration (incremental)
   - Scan and identify all direct imports of `@/core/plugins/axios` (29 files).
   - Scan and identify all type imports from `axios` (6 files importing AxiosResponse, AxiosError).
   - Migrate stores/services/composables in small batches.
   - Replace direct `apiClient` imports from `@/core/plugins/axios` with adapter/helper usage from `src/core/utils/api.ts`.
   - Replace direct Axios type imports with adapter-compatible types.
   - Keep each batch test-backed and releasable.

4. Interceptor/token refresh migration
   - Consolidate or adapt the interceptor/token refresh flow from `src/core/plugins/axios.ts` (lines 64-232) into the new fetch-based adapter.
   - Preserve auth header injection, refresh-on-401 flow, error notification handling, and retry logic.
   - Ensure localStorage token management helpers are reused or adapted for the new adapter.

5. Test migration
   - Replace axios mocks with adapter mocks.
   - Ensure behavior tests still cover auth refresh and error handling.

6. Decommission axios
   - Remove remaining axios imports.
   - Remove `axios` from `package.json`.
   - Remove obsolete plugin/re-export files once references are zero.

## Done criteria

- Zero `axios` imports in `frontend/src` and `frontend/tests`.
- No axios-specific types in app code.
- Lint/typecheck/tests/build all green.
- Auth refresh and error-handling behavior parity verified by tests.
- Build output no longer contains an axios chunk.

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
