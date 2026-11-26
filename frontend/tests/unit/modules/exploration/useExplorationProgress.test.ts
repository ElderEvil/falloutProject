import { describe, expect, it } from 'vite-plus/test'
import {
  canRecall,
  getProgressPercentage,
  getTimeRemaining,
  isReadyToComplete,
  linearProgress,
} from '@/modules/exploration/composables/useExplorationProgress'
import type { Exploration } from '@/modules/exploration/stores/exploration'

const exploration = {
  duration: 4,
  start_time: '2026-08-21T12:00:00Z',
  status: 'active',
} as Exploration

const at = (time: string) => Date.parse(`2026-08-21T${time}:00Z`)

describe('linearProgress', () => {
  it.each([
    [[0, 100, 0], 0],
    [[0, 100, 50], 50],
    [[0, 100, 100], 100],
    [[1000, 2000, 500], 0], // before the window
    [[1000, 2000, 5000], 100], // after it
    [[1000, 1000, 1000], 100], // zero-length window
    [[2000, 1000, 1500], 100], // inverted window
  ] as [number[], number][])('returns the clamped elapsed fraction for %o', (args, expected) => {
    expect(linearProgress(...(args as [number, number, number]))).toBe(expected)
  })
})

describe('getProgressPercentage', () => {
  it('clamps a future exploration start time to zero percent', () => {
    expect(getProgressPercentage(exploration, at('11:00'))).toBe(0)
  })

  it('clamps elapsed progress to one hundred percent', () => {
    expect(getProgressPercentage(exploration, at('20:00'))).toBe(100)
  })

  it('reports a returning run as fully explored when return timestamps are missing', () => {
    const returning = { ...exploration, status: 'returning' } as Exploration
    expect(getProgressPercentage(returning, at('13:00'))).toBe(100)
  })

  it('reports the return-leg progress while the dweller is heading home', () => {
    const returning = {
      ...exploration,
      status: 'returning',
      return_started_at: '2026-08-21T13:00:00Z',
      return_completes_at: '2026-08-21T14:00:00Z',
    } as Exploration
    expect(getProgressPercentage(returning, at('13:30'))).toBe(50)
  })

  it('freezes progress at the encounter pause timestamp', () => {
    const paused = { ...exploration, paused_at: '2026-08-21T13:00:00Z' } as Exploration
    expect(getProgressPercentage(paused, at('20:00'))).toBe(25)
  })
})

describe('getTimeRemaining', () => {
  it('shows the return ETA while the dweller is returning', () => {
    const returning = {
      ...exploration,
      status: 'returning',
      return_completes_at: '2026-08-21T13:30:00Z',
    } as Exploration
    expect(getTimeRemaining(returning, at('13:00'))).toBe('Returning — 30m remaining')
  })

  it('freezes remaining time while an encounter is paused', () => {
    const paused = { ...exploration, paused_at: '2026-08-21T13:00:00Z' } as Exploration
    expect(getTimeRemaining(paused, at('20:00'))).toBe(getTimeRemaining(exploration, at('13:00')))
  })
})

describe('action gating', () => {
  it('allows recall only while the run is actively exploring', () => {
    expect(canRecall(exploration)).toBe(true)
    expect(canRecall({ ...exploration, status: 'returning' } as Exploration)).toBe(false)
  })

  it('marks completion ready only for an elapsed active run', () => {
    expect(isReadyToComplete(exploration, at('20:00'))).toBe(true)
    expect(isReadyToComplete(exploration, at('13:00'))).toBe(false)
    expect(isReadyToComplete({ ...exploration, status: 'returning' } as Exploration)).toBe(false)
  })
})
