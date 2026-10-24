import { describe, expect, it } from 'vitest'
import {
  formatRushPayout,
  formatRushResult,
  rushConsequenceTags,
} from '@/modules/rooms/utils/roomRush'
import type { RoomRushResult } from '@/modules/rooms/models/room'

const success: RoomRushResult = {
  outcome: 'success',
  payout: { power: 12, food: 0, water: 0, stimpack: 0, radaway: 0 },
  caps: 120,
  xp_per_worker: 25,
  happiness_delta: 10,
  incident_id: null,
  incident_type: null,
  stacks_after: 1,
  next_fail_chance: 20,
  message: 'The rush succeeded and produced 12 power.',
}

describe('rushConsequenceTags', () => {
  it('maps incident ids to short terminal tags', () => {
    expect(rushConsequenceTags(['fire', 'radroach_infestation'])).toEqual(['FIRE', 'RADROACH'])
    expect(rushConsequenceTags(['mole_rat_attack', 'radscorpion_attack'])).toEqual([
      'MOLE RAT',
      'RADSCORPION',
    ])
  })

  it('falls back to a readable unknown incident', () => {
    expect(rushConsequenceTags(['custom_thing'])).toEqual(['CUSTOM THING'])
  })

  it('reports no incident when the pool is empty', () => {
    expect(rushConsequenceTags([])).toEqual(['NO INCIDENT'])
  })
})

describe('formatRushPayout', () => {
  it('formats the applied success payout', () => {
    expect(formatRushPayout({ power: 12, food: 0, water: 0, stimpack: 0, radaway: 0 })).toBe(
      '+12 Power'
    )
  })

  it('lists split output', () => {
    expect(formatRushPayout({ power: 1, food: 2, water: 0, stimpack: 0, radaway: 0 })).toBe(
      '+1 Power, +2 Food'
    )
  })

  it('reports capacity when nothing can be stored', () => {
    expect(formatRushPayout({ power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 })).toBe(
      'no resources (at capacity)'
    )
  })
})

describe('formatRushResult', () => {
  it('shows success resources, caps, happiness, and XP', () => {
    expect(formatRushResult(success)).toBe('+12 POWER · +120 CAPS · +10 HAPPINESS · +25 XP')
  })

  it('shows the XP reward when every resource is at capacity', () => {
    expect(
      formatRushResult({
        ...success,
        payout: { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 },
        caps: 0,
        happiness_delta: 0,
      })
    ).toBe('No resources (at capacity) · +25 XP')
  })

  it('labels failure incidents and happiness as consequences', () => {
    expect(
      formatRushResult({
        ...success,
        outcome: 'failure',
        payout: { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 },
        caps: 0,
        xp_per_worker: 0,
        happiness_delta: -10,
        incident_id: 'incident-1',
        incident_type: 'fire',
      })
    ).toBe('FIRE · −10 HAPPINESS')
  })

  it('reports a failure without an incident', () => {
    expect(
      formatRushResult({
        ...success,
        outcome: 'failure',
        payout: { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 },
        caps: 0,
        xp_per_worker: 0,
        happiness_delta: 0,
        incident_id: null,
        incident_type: null,
      })
    ).toBe('NO INCIDENT')
  })
})
