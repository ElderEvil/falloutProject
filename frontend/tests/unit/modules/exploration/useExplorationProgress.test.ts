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

describe('linearProgress', () => {
  it('returns the clamped elapsed fraction across the window', () => {
    expect(linearProgress(0, 100, 0)).toBe(0)
    expect(linearProgress(0, 100, 50)).toBe(50)
    expect(linearProgress(0, 100, 100)).toBe(100)
  })

  it('clamps outside either end of the window', () => {
    expect(linearProgress(1000, 2000, 500)).toBe(0)
    expect(linearProgress(1000, 2000, 5000)).toBe(100)
  })

  it('reads a zero or negative window as complete', () => {
    expect(linearProgress(1000, 1000, 1000)).toBe(100)
    expect(linearProgress(2000, 1000, 1500)).toBe(100)
  })
})

describe('getProgressPercentage', () => {
  it('clamps a future exploration start time to zero percent', () => {
    expect(getProgressPercentage(exploration, Date.parse('2026-08-21T11:00:00Z'))).toBe(0)
  })

  it('clamps elapsed progress to one hundred percent', () => {
    expect(getProgressPercentage(exploration, Date.parse('2026-08-21T20:00:00Z'))).toBe(100)
  })

  it('reports a returning run as fully explored when return timestamps are missing', () => {
    const returning = { ...exploration, status: 'returning' } as Exploration
    expect(getProgressPercentage(returning, Date.parse('2026-08-21T13:00:00Z'))).toBe(100)
  })

  it('reports the return-leg progress while the dweller is heading home', () => {
    const returning = {
      ...exploration,
      status: 'returning',
      return_started_at: '2026-08-21T13:00:00Z',
      return_completes_at: '2026-08-21T14:00:00Z',
    } as Exploration
    expect(getProgressPercentage(returning, Date.parse('2026-08-21T13:30:00Z'))).toBe(50)
  })

  it('freezes progress at the encounter pause timestamp', () => {
    const paused = { ...exploration, paused_at: '2026-08-21T13:00:00Z' } as Exploration
    expect(getProgressPercentage(paused, Date.parse('2026-08-21T20:00:00Z'))).toBe(25)
  })
})

describe('getTimeRemaining', () => {
  it('shows the return ETA while the dweller is returning', () => {
    const returning = {
      ...exploration,
      status: 'returning',
      return_completes_at: '2026-08-21T13:30:00Z',
    } as Exploration
    expect(getTimeRemaining(returning, Date.parse('2026-08-21T13:00:00Z'))).toBe(
      'Returning — 30m remaining'
    )
  })

  it('freezes remaining time while an encounter is paused', () => {
    const paused = { ...exploration, paused_at: '2026-08-21T13:00:00Z' } as Exploration
    expect(getTimeRemaining(paused, Date.parse('2026-08-21T20:00:00Z'))).toBe(
      getTimeRemaining(exploration, Date.parse('2026-08-21T13:00:00Z'))
    )
  })
})

describe('action gating', () => {
  it('allows recall only while the run is actively exploring', () => {
    expect(canRecall(exploration)).toBe(true)
    expect(canRecall({ ...exploration, status: 'returning' } as Exploration)).toBe(false)
  })

  it('marks completion ready only for an elapsed active run', () => {
    expect(isReadyToComplete(exploration, Date.parse('2026-08-21T20:00:00Z'))).toBe(true)
    expect(isReadyToComplete(exploration, Date.parse('2026-08-21T13:00:00Z'))).toBe(false)
    expect(isReadyToComplete({ ...exploration, status: 'returning' } as Exploration)).toBe(false)
  })
})
