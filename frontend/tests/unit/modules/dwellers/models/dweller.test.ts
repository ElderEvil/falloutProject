import { describe, expect, it } from 'vitest'
import { ADULT_AGE_GROUPS, isMature } from '@/modules/dwellers/models/dweller'

/**
 * Regression: `isMature` checked `age_group === 'adult'` while the backend's
 * `ADULT_AGE_GROUPS` also counts elders, so every elder was refused the wasteland,
 * room assignment, and bulk actions the server would have accepted.
 */
describe('ADULT_AGE_GROUPS', () => {
  it('mirrors the backend set, elders included', () => {
    expect([...ADULT_AGE_GROUPS].sort()).toEqual(['adult', 'elder'])
  })
})

describe('isMature', () => {
  const grownUps = ['adult', 'elder'] as const
  const youths = ['teen', 'child'] as const

  it.each(grownUps)('accepts a mature %s', (age_group) => {
    expect(isMature({ is_adult: true, age_group })).toBe(true)
  })

  it.each(youths)('rejects a %s', (age_group) => {
    expect(isMature({ is_adult: true, age_group })).toBe(false)
  })

  it('still requires the is_adult flag', () => {
    expect(isMature({ is_adult: false, age_group: 'adult' })).toBe(false)
  })
})
