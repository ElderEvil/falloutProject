import { describe, expect, it } from 'vite-plus/test'
import {
  ADULT_AGE_GROUPS,
  hasLowHappiness,
  needsCare,
  type DwellerShort,
  canUseRadaway,
  getDwellerDisplayName,
  getHappinessColor,
  getHappinessLevel,
  isApprentice,
  isMature,
  isSeverelyIrradiated,
  orderRoomDwellers,
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
    expect(isMature({ age_group })).toBe(true)
  })

  it.each(youths)('rejects a %s', (age_group) => {
    expect(isMature({ age_group })).toBe(false)
  })

  it('derives maturity from age_group alone', () => {
    expect(isMature({ age_group: 'adult' })).toBe(true)
    expect(isMature({ age_group: 'elder' })).toBe(true)
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
    expect(getDwellerDisplayName({ first_name: 'Lucy', last_name: 'MacLean' })).toBe('Lucy MacLean')
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

describe('isSeverelyIrradiated', () => {
  it('is true at or above half of max health', () => {
    expect(isSeverelyIrradiated(50, 100)).toBe(true)
    expect(isSeverelyIrradiated(60, 100)).toBe(true)
    expect(isSeverelyIrradiated(5, 10)).toBe(true)
  })

  it('is false below half of max health', () => {
    expect(isSeverelyIrradiated(49, 100)).toBe(false)
    expect(isSeverelyIrradiated(1, 100)).toBe(false)
  })

  it('is false without radiation or a positive maximum', () => {
    expect(isSeverelyIrradiated(0, 100)).toBe(false)
    expect(isSeverelyIrradiated(null, 100)).toBe(false)
    expect(isSeverelyIrradiated(50, 0)).toBe(false)
  })
})

describe('getHappinessLevel', () => {
  it('bands happiness into high / medium / low / critical', () => {
    expect(getHappinessLevel(80)).toBe('high')
    expect(getHappinessLevel(75)).toBe('high')
    expect(getHappinessLevel(74)).toBe('medium')
    expect(getHappinessLevel(50)).toBe('medium')
    expect(getHappinessLevel(49)).toBe('low')
    expect(getHappinessLevel(25)).toBe('low')
    expect(getHappinessLevel(24)).toBe('critical')
  })
})

describe('getHappinessColor', () => {
  it('maps each band to its theme token', () => {
    expect(getHappinessColor(getHappinessLevel(80))).toBe('var(--color-theme-primary)')
    expect(getHappinessColor(getHappinessLevel(60))).toBe('var(--color-terminal-green-dark)')
    expect(getHappinessColor(getHappinessLevel(30))).toBe('var(--color-warning)')
    expect(getHappinessColor(getHappinessLevel(10))).toBe('var(--color-danger)')
  })
})

describe('Roster attention predicates', () => {
  const dweller = {
    status: 'idle',
    health: 100,
    max_health: 100,
    radiation: 0,
    happiness: 50,
    effective_max_health: 100,
  } as DwellerShort

  it('uses the 50% health ceiling plus radiation and excludes deceased dwellers', () => {
    expect(needsCare(dweller)).toBe(false)
    expect(needsCare({ ...dweller, effective_max_health: 120 })).toBe(false)
    expect(needsCare({ ...dweller, health: 59, effective_max_health: 120 })).toBe(true)
    expect(needsCare({ ...dweller, health: 60, effective_max_health: 120 })).toBe(false)
    expect(needsCare({ ...dweller, radiation: 20, effective_max_health: 80 })).toBe(true)
    expect(needsCare({ ...dweller, status: 'dead', health: 0, radiation: 20 })).toBe(false)
  })

  it('matches the low and critical bands, with fifty as the exclusive boundary', () => {
    expect(hasLowHappiness(dweller)).toBe(false)
    expect(hasLowHappiness({ ...dweller, happiness: 49 })).toBe(true)
    expect(hasLowHappiness({ ...dweller, happiness: 10 })).toBe(true)
    expect(hasLowHappiness({ ...dweller, status: 'dead', happiness: 10 })).toBe(false)
  })
})

describe('orderRoomDwellers', () => {
  it('keeps workers in stable order and moves apprentices last', () => {
    const apprentice = { id: 'apprentice', apprentice_stat: 'strength' }
    const workerA = { id: 'worker-a', apprentice_stat: null }
    const workerB = { id: 'worker-b' }

    expect(orderRoomDwellers([apprentice, workerA, workerB]).map((d) => d.id)).toEqual([
      'worker-a',
      'worker-b',
      'apprentice',
    ])
  })

  it('detects apprentices by apprentice_stat only', () => {
    expect(isApprentice({ apprentice_stat: 'strength' })).toBe(true)
    expect(isApprentice({ apprentice_stat: null })).toBe(false)
    expect(isApprentice({})).toBe(false)
    expect(isApprentice(null)).toBe(false)
  })
})
