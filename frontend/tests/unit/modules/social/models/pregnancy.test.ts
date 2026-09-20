import { describe, expect, it } from 'vitest'
import { pregnancyForCouple, type Pregnancy } from '@/modules/social/models/pregnancy'

function pregnancy(overrides: Partial<Pregnancy>): Pregnancy {
  return {
    id: 'p1',
    mother_id: 'm1',
    father_id: 'f1',
    conceived_at: '2026-01-01T00:00:00Z',
    due_at: '2026-01-01T03:00:00Z',
    status: 'pregnant',
    progress_percentage: 50,
    time_remaining_seconds: 5400,
    is_due: false,
    ...overrides,
  }
}

describe('pregnancyForCouple', () => {
  it('matches a pregnant couple in mother/father order', () => {
    const p = pregnancy({})
    expect(pregnancyForCouple([p], 'm1', 'f1')).toBe(p)
  })

  it('matches a pregnant couple in reversed order', () => {
    const p = pregnancy({})
    expect(pregnancyForCouple([p], 'f1', 'm1')).toBe(p)
  })

  it('returns null when the couple has no pregnancy', () => {
    const p = pregnancy({})
    expect(pregnancyForCouple([p], 'm1', 'other')).toBeNull()
  })

  it('ignores delivered pregnancies', () => {
    const p = pregnancy({ status: 'delivered' })
    expect(pregnancyForCouple([p], 'm1', 'f1')).toBeNull()
  })

  it('ignores miscarried pregnancies', () => {
    const p = pregnancy({ status: 'miscarried' })
    expect(pregnancyForCouple([p], 'm1', 'f1')).toBeNull()
  })

  it('returns null for an empty list', () => {
    expect(pregnancyForCouple([], 'm1', 'f1')).toBeNull()
  })
})
