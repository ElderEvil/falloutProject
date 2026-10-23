import { spawnSync } from 'node:child_process'
import { resolve } from 'node:path'

const runId = new Date().toISOString().replaceAll(/[:.]/g, '-')
const resultsDirectory = resolve('test-results/performance-history', runId)
const repeats = process.env.UI_PERF_REPEATS ?? '5'
if (!/^[1-9]\d*$/.test(repeats)) throw new Error('UI_PERF_REPEATS must be a positive integer')
const workload = process.env.UI_PERF_WORKLOAD
if (workload && !['small', 'large'].includes(workload))
  throw new Error('UI_PERF_WORKLOAD must be small or large')
const run = spawnSync(
  'pnpm',
  [
    'exec',
    'playwright',
    'test',
    '--config=playwright.perf.config.ts',
    `--repeat-each=${repeats}`,
    '--max-failures=1',
    ...(workload ? ['--grep', `\\[${workload}\\]`] : []),
  ],
  {
    env: { ...process.env, UI_PERF_RESULTS_DIR: resultsDirectory },
    stdio: 'inherit',
  }
)

if (run.error) throw run.error
if (run.status !== 0) process.exit(run.status ?? 1)

const summary = spawnSync(
  process.execPath,
  ['scripts/summarize-ui-performance.mjs', resultsDirectory],
  { stdio: 'inherit' }
)
if (summary.error) throw summary.error
process.exit(summary.status ?? 1)
