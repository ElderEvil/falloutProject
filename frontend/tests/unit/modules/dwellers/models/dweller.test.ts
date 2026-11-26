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
  passesAsHuman,
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
  it.each([
    ['adult', true],
    ['elder', true],
    ['teen', false],
    ['child', false],
  ] as const)('judges %s maturity as %s', (age_group, mature) => {
    expect(isMature({ age_group })).toBe(mature)
  })
})

describe('passesAsHuman', () => {
  it.each([
    ['human', undefined, true],
    ['synth', 'gen_3', true],
    ['synth', undefined, true],
    ['ghoul', 'sane', false],
    ['super_mutant', 'behemoth', false],
    ['synth', 'gen_1', false],
    ['synth', 'gen_2', false],
  ] as const)('judges %s/%s human-presenting as %s', (race, state_of_being, passes) => {
    expect(passesAsHuman({ visual_attributes: { race, state_of_being } })).toBe(passes)
  })
})

describe('canUseRadaway', () => {
  it.each([
    ['ghoul', undefined, false],
    ['super_mutant', undefined, false],
    ['synth', 'gen_1', false],
    ['synth', 'gen_2', false],
    ['synth', undefined, false],
    ['synth', 'gen_3', true],
    ['human', undefined, true],
    ['unknown', undefined, true],
  ] as const)('judges %s/%s eligibility as %s', (race, state_of_being, eligible) => {
    expect(canUseRadaway({ visual_attributes: { race, state_of_being } })).toBe(eligible)
  })

  it('defaults a missing race to human eligibility', () => {
    expect(canUseRadaway({ visual_attributes: null })).toBe(true)
  })
})

describe('getDwellerDisplayName', () => {
  it.each([
    [{ first_name: 'Lucy', last_name: 'MacLean' }, 'Lucy MacLean'],
    [{ first_name: 'Gary', last_name: null }, 'Gary'],
    [{ first_name: 'Gary' }, 'Gary'],
    [null, ''],
    [undefined, ''],
    [{ first_name: null, last_name: 'Smith' }, ''],
  ] as const)('names %o as %j', (dweller, name) => {
    expect(getDwellerDisplayName(dweller)).toBe(name)
  })
})

describe('isSeverelyIrradiated', () => {
  it.each([
    [50, 100, true],
    [60, 100, true],
    [5, 10, true],
    [49, 100, false],
    [1, 100, false],
    [0, 100, false],
    [null, 100, false],
    [50, 0, false],
  ] as const)('judges radiation %s of %s as severe: %s', (radiation, maxHealth, severe) => {
    expect(isSeverelyIrradiated(radiation, maxHealth)).toBe(severe)
  })
})

describe('happiness', () => {
  it.each([
    [80, 'high'],
    [75, 'high'],
    [74, 'medium'],
    [50, 'medium'],
    [49, 'low'],
    [25, 'low'],
    [24, 'critical'],
  ] as const)('bands %i happiness as %s', (happiness, level) => {
    expect(getHappinessLevel(happiness)).toBe(level)
  })

  it.each([
    [80, 'var(--color-theme-primary)'],
    [60, 'var(--color-terminal-green-dark)'],
    [30, 'var(--color-warning)'],
    [10, 'var(--color-danger)'],
  ] as const)('maps %i happiness to its theme token', (happiness, color) => {
    expect(getHappinessColor(getHappinessLevel(happiness))).toBe(color)
  })
})

describe('roster attention predicates', () => {
  const dweller = {
    status: 'idle',
    health: 100,
    max_health: 100,
    radiation: 0,
    happiness: 50,
    effective_max_health: 100,
  } as DwellerShort

  it.each([
    [{}, false],
    [{ effective_max_health: 120 }, false],
    [{ health: 59, effective_max_health: 120 }, true],
    [{ health: 60, effective_max_health: 120 }, false],
    [{ radiation: 20, effective_max_health: 80 }, true],
    [{ status: 'dead', health: 0, radiation: 20 }, false],
  ] as const)('flags care needs from the 50% ceiling plus radiation (%o)', (patch, care) => {
    expect(needsCare({ ...dweller, ...patch })).toBe(care)
  })

  it.each([
    [{}, false],
    [{ happiness: 49 }, true],
    [{ happiness: 10 }, true],
    [{ status: 'dead', happiness: 10 }, false],
  ] as const)('flags low happiness below the exclusive fifty boundary (%o)', (patch, low) => {
    expect(hasLowHappiness({ ...dweller, ...patch })).toBe(low)
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

  it.each([
    [{ apprentice_stat: 'strength' }, true],
    [{ apprentice_stat: null }, false],
    [{}, false],
    [null, false],
  ] as const)('detects apprentices by apprentice_stat only (%o)', (dweller, apprentice) => {
    expect(isApprentice(dweller)).toBe(apprentice)
  })
})
