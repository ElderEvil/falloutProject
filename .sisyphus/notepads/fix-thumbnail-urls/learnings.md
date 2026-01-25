## Learnings
- Created a centralized utility `normalizeImageUrl` in `frontend/src/utils/image.ts` to handle image URL protocol normalization.
- This prevents double `http://` prefixes when the backend already provides a protocol.
- Used `@/utils/image` alias for clean imports across the frontend modules.

## Decisions
- Chose to return an empty string `''` for null/undefined inputs in `normalizeImageUrl` to maintain consistency with existing Vue template checks (where `''` is falsy).
- Decided to include `/` as a valid starting character to support relative paths if needed in the future.

## Issues Encountered
- `lsp_diagnostics` for Vue was not available in the environment, so verified changes using `pnpm run lint` (oxlint) and `pnpm run build` (vite build + rolldown).
