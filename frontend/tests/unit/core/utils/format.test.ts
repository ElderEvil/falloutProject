import { describe, expect, it } from 'vitest'
import {
  capitalize,
  formatDate,
  formatDateTime,
  formatLongDateTime,
  formatMonthDay,
  formatShortDate,
  humanize,
  humanizePreserveCase,
  threatName,
} from '@/core/utils/format'

describe('humanize', () => {
  it('title-cases underscore-separated words and lowercases the rest', () => {
    expect(humanize('rare_outfit')).toBe('Rare Outfit')
    expect(humanize('two_handed_pistol')).toBe('Two Handed Pistol')
    expect(humanize('ENERGY')).toBe('Energy')
  })

  it('renders a missing value as empty', () => {
    expect(humanize(undefined)).toBe('')
    expect(humanize(null)).toBe('')
    expect(humanize('')).toBe('')
  })
})

describe('humanizePreserveCase', () => {
  it('capitalizes each word but preserves the original casing', () => {
    expect(humanizePreserveCase('super_mutant')).toBe('Super Mutant')
    expect(humanizePreserveCase('NCR')).toBe('NCR')
    expect(humanizePreserveCase('raider_attack')).toBe('Raider Attack')
  })
})

describe('capitalize', () => {
  it('upper-cases only the first character', () => {
    expect(capitalize('daily')).toBe('Daily')
    expect(capitalize('weekly')).toBe('Weekly')
    expect(capitalize('')).toBe('')
  })
})

describe('threatName', () => {
  it('renders an upper-case incident label', () => {
    expect(threatName('raider_attack')).toBe('RAIDER ATTACK')
    expect(threatName('radroach_infestation')).toBe('RADROACH INFESTATION')
  })
})

describe('date helpers', () => {
  it('formatDateTime mirrors the runtime toLocaleString', () => {
    const date = new Date(2026, 0, 2, 15, 4, 5)
    expect(formatDateTime(date)).toBe(date.toLocaleString())
    expect(formatDateTime(date.toISOString())).toBe(date.toLocaleString())
  })

  it('formatDate mirrors the runtime toLocaleDateString', () => {
    const date = new Date(2026, 0, 2, 15, 4, 5)
    expect(formatDate(date)).toBe(date.toLocaleDateString())
    expect(formatDate(date.toISOString())).toBe(date.toLocaleDateString())
  })

  it('formatMonthDay renders a long en-US month and day', () => {
    expect(formatMonthDay(new Date(2026, 1, 1))).toBe('February 1')
  })

  it('formatShortDate parses a YYYY-MM-DD string as local time', () => {
    expect(formatShortDate('2026-02-01')).toBe('Feb 1, 2026')
  })

  it('formatLongDateTime renders a long en-US date and time', () => {
    expect(formatLongDateTime(new Date(2026, 0, 2, 15, 4))).toBe('January 2, 2026 at 03:04 PM')
  })
})
