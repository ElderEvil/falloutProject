import { describe, expect, it } from 'vitest'
import {
  ADULT_AGE_GROUPS,
  canUseRadaway,
  getDwellerDisplayName,
  isMature,
} from '@/modules/dwellers/models/dweller'

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

describe('canUseRadaway', () => {
  it.each(['ghoul', 'super_mutant', 'synth'])('blocks %s', (race) => {
    expect(canUseRadaway({ visual_attributes: { race } })).toBe(false)
  })

  it.each(['human', 'unknown'])('allows %s using the backend fallback', (race) => {
    expect(canUseRadaway({ visual_attributes: { race } })).toBe(true)
  })

  it('defaults missing race to human eligibility', () => {
    expect(canUseRadaway({ visual_attributes: null })).toBe(true)
  })
})

describe('getDwellerDisplayName', () => {
  it('joins first and last name', () => {
    expect(getDwellerDisplayName({ first_name: 'Lucy', last_name: 'MacLean' })).toBe(
      'Lucy MacLean'
    )
  })

  it('omits a null last name instead of rendering "null"', () => {
    expect(getDwellerDisplayName({ first_name: 'Gary', last_name: null })).toBe('Gary')
  })

  it('omits an undefined last name', () => {
    expect(getDwellerDisplayName({ first_name: 'Gary' })).toBe('Gary')
  })

  it('returns an empty string without a dweller or first name', () => {
    expect(getDwellerDisplayName(null)).toBe('')
    expect(getDwellerDisplayName(undefined)).toBe('')
    expect(getDwellerDisplayName({ first_name: null, last_name: 'Smith' })).toBe('')
  })
})
