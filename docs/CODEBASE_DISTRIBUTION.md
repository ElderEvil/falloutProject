# Codebase Distribution Baseline

Measured with `tokei` on 2026-09-08 after the post-#552 test cleanup. This is a reference point for future codebase audits.

## Application and test code

The percentages below use an application/test denominator of 138,394 code lines. Generated output, game-data JSON, documentation, and most configuration files are excluded from this denominator. Percentages use `tokei`'s `Code` column, not physical lines, comments, or blanks.

| Area | Code lines | Share |
|---|---:|---:|
| Backend runtime Python | 40,040 | 28.9% |
| Backend tests | 20,868 | 15.1% |
| Frontend runtime | 53,215 | 38.5% |
| Frontend tests | 24,271 | 17.5% |
| **Total application/test code** | **138,394** | **100%** |

The frontend runtime count includes Vue component templates, scripts, and styles. Embedded Vue languages are counted once as part of the Vue application, not added again as separate files.

## Test distribution

Backend tests are approximately 34% of backend application/test code:

- Service tests: 11,254 code lines (54% of backend tests)
- API tests: 4,482 code lines (21%)
- CRUD tests: 1,783 code lines (9%)
- Model, utility, database, agent, integration, and shared test support: 3,349 code lines (16%)

Frontend tests are approximately 31% of frontend application/test code:

- Unit tests: 22,991 code lines
- End-to-end tests: 1,280 code lines

Overall, tests represent approximately 33% of the application/test denominator.

## Styling and other non-runtime content

- Standalone CSS: 1,222 lines
- CSS embedded in Vue SFCs: 9,454 lines
- Total styling: 10,676 lines, or approximately 20% of frontend runtime code
- Game and configuration JSON: 5,229 lines
- CI/configuration YAML and Markdown documentation are excluded from the application/test denominator.

## Interpretation

This distribution is healthy for a full-stack game application:

- Around 30–50% test code is a useful rough heuristic for production-oriented projects; this repository is near the lower end after the deliberate coverage-shadow cleanup.
- Backend test parity near 34% is respectable, but lower than the previous baseline and worth monitoring by behavior, not by test count alone.
- Frontend test coverage near 30% is normal, particularly when unit tests substantially outnumber slower end-to-end tests.
- A frontend-heavy runtime split is expected for a game with a rich interactive interface.
- Styling at roughly 20% of frontend code is reasonable for a custom visual theme and many Vue components.

The main area to monitor is end-to-end coverage. It is intentionally much smaller than unit coverage, which is common, but should grow around critical player journeys and regressions.

## Reproducing the baseline

Use `tokei` while excluding generated and dependency directories:

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

When updating this document, record the measurement date, the `tokei` version/commands, and preserve the previous baseline for comparison.
