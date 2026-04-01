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
  - centralized interceptor/token refresh flow in `src/core/plugins/axios.ts`
  - shared helpers in `src/core/utils/api.ts` and `src/core/types/utils.ts`
  - direct usage across stores/services/views and unit tests

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
   - Migrate stores/services/composables in small batches.
   - Replace direct axios imports with adapter/helper usage.
   - Keep each batch test-backed and releasable.

4. Test migration
   - Replace axios mocks with adapter mocks.
   - Ensure behavior tests still cover auth refresh and error handling.

5. Decommission axios
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

- Do not add new direct axios imports in new code.
- Prefer `src/core/utils/api.ts` (or the new adapter) as the only HTTP boundary.
- If legacy axios usage is required temporarily, isolate it and add a migration TODO in the same file.
