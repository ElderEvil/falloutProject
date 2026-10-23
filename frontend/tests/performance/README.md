# UI performance probe

Run `pnpm run e2e:install` once, then `pnpm run perf:ui`. It lints and typechecks the probe, builds the production frontend once, and runs each workload five times sequentially in Chromium at 1280×900 with fresh browser contexts. Use `UI_PERF_REPEATS=1 pnpm run perf:ui` for a diagnostic run, or `UI_PERF_WORKLOAD=large pnpm run perf:ui` to run only the larger vault (`small` selects the basic workload).

Playwright's full tracing is off during normal measurements to avoid screenshot/DOM snapshot recording overhead. Use `UI_PERF_TRACE=1 UI_PERF_REPEATS=1 pnpm run perf:ui` to retain a diagnostic trace under `test-results/playwright/`. The summary records whether tracing was enabled; compare only runs with the same setting.

The scenarios load the overview, open a room, open its assignment picker, assign and unassign a dweller, open dweller details, drag a dweller between rooms, and navigate to dwellers, training, exploration, and back to overview. Each action checks its visible result. Section navigation also waits for its data response. Unexpected API requests, runtime errors, and visible error toasts fail the probe.

Measurements:

- **Ready elapsed time:** navigation start to overview readiness, or the time around the Playwright action and its readiness assertions. Action measurements include automation and assertion overhead; they are not pure input latency.
- **Event Timing:** browser-reported durations ≥16 ms, grouped by interaction ID. Chromium does not consistently give HTML drag events interaction IDs; an absent sample remains unreported.
- **Long Animation Frames:** frames >50 ms, with blocking duration and script/layout attribution. Each action starts a new observation window so late entries from previous actions are excluded.
- **Scrolling frame intervals:** requestAnimationFrame intervals while a paced wheel gesture traverses the roster, including median, p95, maximum, and the count over 32 ms. These sample main-thread frame delivery, rather than the display's exact FPS. The scroll scenario's elapsed time includes the deliberate gesture pacing.

The small workload has two production rooms and two dwellers; training and exploration are empty. The large workload has **100 dwellers, 54 rooms, and 42 active trainees across 21 full training rooms**. It covers loading the overview, opening an occupied production room, rendering and scrolling the first 20-dweller page, measuring the next-page interaction, traversing all five pages to open the 100th dweller, loading the populated training queue, collapsing/expanding a stat group, and opening a full training room. Setup assertions reject overlapping rooms and overfilled worker slots.

The large layout retains the boosted vault's five-floor shape from [the backend room builder](../../../backend/app/services/vault/seeding.py). `boosted-rooms.json` is a frozen snapshot produced by `prepare_initial_rooms(..., is_boosted=True)`, with the three storage rooms fused using `build_room(..., size=9)` as happens during seeding. The larger fixture repeats the existing training, housing, production, and elevator blocks below it. Regenerate that snapshot with those backend helpers when intentionally updating the benchmark layout; performance runs themselves do not load Python or connect to the database.

API responses are stateful mocks, including their pagination limit. Portraits, silhouettes, and room art are served from the repository. There is no backend/database dependency; real backend latency, active expeditions, mobile input, and populations above the API's default 100-row response limit remain outside this benchmark.

Measurement version 5 covers the paginated roster. Roster-opening measurements can be compared with version 4's full-list baseline using the same fixture and browser: both fetch the same 100 dwellers and retain the same dashboard aggregates. Scrolling now covers a shorter page, and opening the last dweller follows additional page changes, so those scenarios are not equivalent comparisons with version 4.

Local measurements on 2026-10-23 used Chromium 153.0.8010.12 at 1280×900, five fresh-context runs per version, production builds and tracing disabled. Roster opening fell from **764.7 ms to 320.4 ms median** (58% faster); its longest observed frame fell from **387.9 ms to 128.5 ms**. Moving to the next page took **132.9 ms median**, with a longest frame of 74.5 ms. All ten final small/large workload runs passed, including reaching the 100th dweller. Raw artifacts are local and git-ignored; these are diagnostic measurements, not CI budgets or backend-latency results.

`test-results/performance-history/<run-id>/` stores separate sample files per workload and `summary.json`, whose `workloads.small` and `workloads.large` contain their own medians, worst samples, browser version, and fixture details. The console prints a comparison table. Results are git-ignored and kept across probe invocations. Compare the same measurement version, fixture, machine, and browser before introducing timing budgets.
