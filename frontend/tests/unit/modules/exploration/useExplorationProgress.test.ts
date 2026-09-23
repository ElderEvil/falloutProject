import { describe, expect, it } from 'vitest'
import {
  canRecall,
  getProgressPercentage,
  getTimeRemaining,
  isReadyToComplete,
} from '@/modules/exploration/composables/useExplorationProgress'
import type { Exploration } from '@/modules/exploration/stores/exploration'

const exploration = {
  duration: 4,
  start_time: '2026-08-21T12:00:00Z',
  status: 'active',
} as Exploration

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
