import { describe, expect, it } from 'vitest'
import { getProgressPercentage } from '@/modules/exploration/composables/useExplorationProgress'
import type { Exploration } from '@/modules/exploration/stores/exploration'

const exploration = {
  duration: 4,
  start_time: '2026-08-21T12:00:00Z',
} as Exploration

describe('getProgressPercentage', () => {
  it('clamps a future exploration start time to zero percent', () => {
    expect(getProgressPercentage(exploration, Date.parse('2026-08-21T11:00:00Z'))).toBe(0)
  })

  it('clamps elapsed progress to one hundred percent', () => {
    expect(getProgressPercentage(exploration, Date.parse('2026-08-21T20:00:00Z'))).toBe(100)
  })
})
