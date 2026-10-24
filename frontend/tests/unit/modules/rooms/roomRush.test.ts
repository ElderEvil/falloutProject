import { describe, expect, it } from 'vite-plus/test'
import { formatRushPayout, rushConsequenceTags } from '@/modules/rooms/utils/roomRush'

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
