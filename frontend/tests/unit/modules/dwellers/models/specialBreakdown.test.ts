import { describe, it, expect } from 'vitest'
import { describeBonusSources, getSpecialBreakdown } from '@/modules/dwellers/models/specialBreakdown'
import type { Dweller } from '@/modules/dwellers/models/dweller'

function makeDweller(overrides: Partial<Dweller> = {}): Dweller {
  return {
    S: 10,
    P: 4,
    E: 6,
    C: 3,
    I: 7,
    A: 2,
    L: 8,
    outfit: null,
    identity_modifiers: {
      strength: 0,
      perception: 0,
      endurance: 0,
      charisma: 0,
      intelligence: 0,
      agility: 0,
      luck: 0,
    },
    ...overrides,
  } as unknown as Dweller
}

describe('getSpecialBreakdown', () => {
  it('should return seven rows in SPECIAL order', () => {
    const rows = getSpecialBreakdown(makeDweller())
    expect(rows.map((r) => r.letter)).toEqual(['S', 'P', 'E', 'C', 'I', 'A', 'L'])
  })

  it('should report base equals effective without bonuses', () => {
    const [strength] = getSpecialBreakdown(makeDweller())
    expect(strength.base).toBe(10)
    expect(strength.effective).toBe(10)
    expect(strength.outfitName).toBeNull()
  })

  it('should fold outfit bonus into effective without capping', () => {
    const rows = getSpecialBreakdown(
      makeDweller({ outfit: { name: 'Vault Suit', strength: 5 } as never })
    )
    expect(rows[0].outfit).toBe(5)
    expect(rows[0].outfitName).toBe('Vault Suit')
    expect(rows[0].effective).toBe(15)
  })

  it('should fold identity modifiers into effective', () => {
    const rows = getSpecialBreakdown(
      makeDweller({ identity_modifiers: { charisma: 2 } as never })
    )
    expect(rows[3].identity).toBe(2)
    expect(rows[3].effective).toBe(5)
  })

  it('should floor effective at 1', () => {
    const rows = getSpecialBreakdown(
      makeDweller({ S: 1, identity_modifiers: { strength: -5 } as never })
    )
    expect(rows[0].effective).toBe(1)
  })

  it('should return empty rows for missing dweller', () => {
    expect(getSpecialBreakdown(null)).toEqual([])
    expect(getSpecialBreakdown(undefined)).toEqual([])
  })
})

describe('describeBonusSources', () => {
  it('should describe outfit and identity sources', () => {
    const [strength] = getSpecialBreakdown(
      makeDweller({
        outfit: { name: 'Vault Suit', strength: 5 } as never,
        identity_modifiers: { strength: 1 } as never,
      })
    )
    expect(describeBonusSources(strength)).toEqual(['+5 Vault Suit', '+1 identity'])
  })

  it('should return empty list without bonuses', () => {
    const [strength] = getSpecialBreakdown(makeDweller())
    expect(describeBonusSources(strength)).toEqual([])
  })
})
