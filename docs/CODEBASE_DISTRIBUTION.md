# Codebase Distribution

Latest measurement: `tokei 14.0.0` on 2026-09-17. The measurement includes the
current working tree, including uncommitted work, and is a reference point for
the consolidated [codebase audit](AUDIT.md).

## Application and test code

The percentages below use an application/test denominator of 157,007 code
lines. Generated output, game-data JSON, documentation, and most configuration
files are excluded from this denominator. Percentages use `tokei`'s `Code`
column, not physical lines, comments, or blanks.

| Area | 2026-09-08 | 2026-09-17 | Change | Share |
|---|---:|---:|---:|---:|
| Backend runtime Python | 40,040 | 44,461 | +4,421 | 28.3% |
| Backend tests | 20,868 | 27,861 | +6,993 | 17.7% |
| Frontend runtime | 53,215 | 56,771 | +3,556 | 36.2% |
| Frontend tests | 24,271 | 27,914 | +3,643 | 17.8% |
| **Total application/test code** | **138,394** | **157,007** | **+18,613** | **100%** |

The frontend runtime count includes Vue component templates, scripts, and styles. Embedded Vue languages are counted once as part of the Vue application, not added again as separate files.

## Test distribution

Backend tests are approximately 39% of backend application/test code:

- Service tests: 15,662 code lines (56% of backend tests)
- API tests: 5,560 code lines (20%)
- CRUD tests: 2,314 code lines (8%)
- Model, utility, database, agent, integration, and shared test support: 4,325 code lines (16%)

Frontend tests are approximately 33% of frontend application/test code:

- Unit tests: 26,634 code lines
- End-to-end tests: 1,280 code lines

Overall, tests represent approximately 36% of the application/test denominator.

## Styling and other non-runtime content

- Standalone CSS: 1,260 lines
- CSS embedded in Vue SFCs: 9,641 lines
- Total styling: 10,901 lines, or approximately 19% of frontend runtime code
- Game and configuration JSON: 6,698 lines
- CI/configuration YAML and Markdown documentation are excluded from the application/test denominator.

## Frontend production bundle

Measured with `pnpm run analyze` on 2026-09-17. The command produces an ignored
interactive treemap at `frontend/dist/stats.html`; it is the source of truth for
module-level attribution. This table keeps only the largest emitted assets so
future distribution reviews can spot material changes without committing a
generated report.

| Asset | Raw size | Gzip size | Loading note |
|---|---:|---:|---|
| `index.css` | 118.94 kB | 18.11 kB | Global stylesheet |
| `vendor` | 96.87 kB | 31.14 kB | Shared third-party chunk |
| `iconify` | 84.84 kB | 32.88 kB | Shared icon library chunk |
| `index` | 75.38 kB | 24.79 kB | Main application entry |
| `RoomDetailModal` | 68.29 kB | 20.15 kB | Route/component chunk |
| `DwellerDetailView` | 55.73 kB | 16.95 kB | Route chunk |
| `VaultView` | 50.72 kB | 16.95 kB | Route chunk |
| `axios` | 50.19 kB | 18.85 kB | Shared HTTP client chunk |
| `ui-components` | 39.83 kB | 14.07 kB | Shared UI component chunk |

These are emitted chunk sizes, not a first-load total: route chunks load on
demand, and shared chunks may be requested by several routes. The clearest
optimization candidate to investigate is `iconify`, the largest gzip-compressed
JavaScript chunk. Confirm actual icon usage in the treemap and a browser network
trace before changing imports or manually splitting chunks.

## Interpretation

This distribution is healthy for a full-stack game application:

- Around 30–50% test code is a useful rough heuristic for production-oriented projects; this repository is in that range.
- Backend test parity rose from 34% to 39%. The increase is healthy only where it represents distinct contracts and regressions; monitor behavior, not test count alone.
- Frontend test parity rose from 31% to 33%, with unit tests still substantially outnumbering slower end-to-end tests.
- A frontend-heavy runtime split is expected for a game with a rich interactive interface.
- Styling at roughly 20% of frontend code is reasonable for a custom visual theme and many Vue components.

The main area to monitor is end-to-end coverage. It is intentionally much smaller than unit coverage, which is common, but should grow around critical player journeys and regressions.

## Reproducing the baseline

Use `tokei 14.0.0` while excluding generated and dependency directories:

```bash
tokei . --exclude .git,node_modules,.venv,dist,build,coverage,__pycache__
```

For accurate category comparisons, measure these paths separately because Vue SFCs contain nested HTML, JavaScript, and CSS:

```bash
tokei backend/app --exclude tests
tokei backend/app/tests
tokei frontend/src
tokei frontend/tests
```

Generate the matching bundle report with:

```bash
cd frontend && pnpm run analyze
```

When updating this document, record the measurement date, `tokei` version and
commands, preserve the previous baseline for comparison, and state whether the
worktree was clean.
