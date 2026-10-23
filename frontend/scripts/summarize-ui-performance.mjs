import { readdir, readFile, writeFile } from 'node:fs/promises'
import { join, resolve } from 'node:path'

const runDirectory = process.argv[2]
if (!runDirectory) throw new Error('Pass the directory containing the repeated run JSON files')

const files = (await readdir(runDirectory))
  .filter((file) => /^(?:(?:small|large)-)?run-\d+\.json$/.test(file))
  .sort()
if (files.length === 0) throw new Error(`No performance run files found in ${runDirectory}`)

const runs = await Promise.all(
  files.map(async (file) => JSON.parse(await readFile(join(runDirectory, file), 'utf8')))
)

function median(values) {
  const sorted = [...values].sort((a, b) => a - b)
  const middle = Math.floor(sorted.length / 2)
  return sorted.length % 2 ? sorted[middle] : (sorted[middle - 1] + sorted[middle]) / 2
}

function stats(values, samples = values) {
  const observed = values.filter(Number.isFinite)
  return {
    medianMs: Number(median(observed).toFixed(1)),
    worstMs: Number(Math.max(...observed).toFixed(1)),
    observedRuns: observed.length,
    samplesMs: samples.map((value) => (Number.isFinite(value) ? Number(value.toFixed(1)) : null)),
  }
}

function summarize(runs) {
  const scenarioNames = [
    ...new Set(runs.flatMap((run) => run.scenarios.map(({ scenario }) => scenario))),
  ]
  const scenarios = Object.fromEntries(
    scenarioNames.map((scenarioName) => {
      const reports = runs.map((run) =>
        run.scenarios.find(({ scenario }) => scenario === scenarioName)
      )
      const interactionSamples = reports.map((report) => {
        const durations = report.interactionDurationsMs ?? []
        return durations.length ? Math.max(...durations) : null
      })
      const frameSamples = reports.map((report) =>
        Math.max(0, ...(report.longAnimationFramesOver50ms ?? []).map(({ duration }) => duration))
      )
      const frames = reports.flatMap((report, runIndex) =>
        (report.longAnimationFramesOver50ms ?? []).map((frame) => ({ run: runIndex + 1, ...frame }))
      )
      const scenario = {
        runs: reports.length,
        eventTimingEntries: reports.map((report) => report.eventTimingEntries ?? 0),
        longAnimationFrameRuns: frameSamples.filter((duration) => duration > 0).length,
        longestFrame: frames.sort((a, b) => b.duration - a.duration)[0] ?? null,
      }

      if (reports.some((report) => typeof report.elapsedMs === 'number')) {
        scenario.elapsedMs = stats(
          reports.map((report) => report.elapsedMs).filter(Number.isFinite)
        )
      }
      if (reports.some((report) => report.interactionDurationsMs?.length)) {
        scenario.interactionMs = stats(
          interactionSamples.filter(Number.isFinite),
          interactionSamples
        )
      }
      if (frames.length > 0) scenario.maxLongAnimationFrameMsPerRun = stats(frameSamples)
      const intervals = reports
        .flatMap((report) => report.animationFrameIntervalsMs ?? [])
        .sort((a, b) => a - b)
      if (intervals.length)
        scenario.animationFrames = {
          samples: intervals.length,
          medianMs: Number(median(intervals).toFixed(1)),
          p95Ms: Number(intervals[Math.ceil(intervals.length * 0.95) - 1].toFixed(1)),
          worstMs: Number(Math.max(...intervals).toFixed(1)),
          intervalsOver32ms: intervals.filter((value) => value > 32).length,
        }
      return [scenarioName, scenario]
    })
  )

  return {
    recordedAt: new Date().toISOString(),
    runCount: runs.length,
    browser: runs[0].browser,
    browserVersion: runs[0].browserVersion,
    viewport: runs[0].viewport,
    measurementVersion: runs[0].measurementVersion,
    tracing: runs[0].tracing,
    fixture: runs[0].fixture,
    scenarios,
  }
}

const workloads = Object.fromEntries(
  [...new Set(runs.map((run) => run.workload ?? 'small'))].map((workload) => [
    workload,
    summarize(runs.filter((run) => (run.workload ?? 'small') === workload)),
  ])
)
const summary = { recordedAt: new Date().toISOString(), runCount: runs.length, workloads }
const summaryPath = resolve(runDirectory, 'summary.json')
await writeFile(summaryPath, JSON.stringify(summary, null, 2))

console.table(
  Object.entries(workloads).flatMap(([workload, { scenarios }]) =>
    Object.entries(scenarios).map(([scenario, result]) => ({
      workload,
      scenario,
      'ready median ms': result.elapsedMs?.medianMs ?? '—',
      'ready worst ms': result.elapsedMs?.worstMs ?? '—',
      'Event Timing median ms': result.interactionMs?.medianMs ?? 'unreported',
      'longest frame ms': result.maxLongAnimationFrameMsPerRun?.worstMs ?? 'none >50ms',
      'rAF interval p95 ms': result.animationFrames?.p95Ms ?? '—',
      'runs with long frames': `${result.longAnimationFrameRuns}/${result.runs}`,
    }))
  )
)
console.log(`[ui-performance-summary] saved ${summaryPath}`)
