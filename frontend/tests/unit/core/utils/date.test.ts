import { describe, expect, it } from 'vitest'
import { parseUtcDate } from '@/core/utils/date'

describe('parseUtcDate', () => {
  it('treats naive API timestamps as UTC', () => {
    expect(parseUtcDate('2026-08-28T10:00:00').toISOString()).toBe('2026-08-28T10:00:00.000Z')
    expect(parseUtcDate('2026-08-28 10:00:00').toISOString()).toBe('2026-08-28T10:00:00.000Z')
  })

  it('preserves explicit timezone offsets', () => {
    expect(parseUtcDate('2026-08-28T10:00:00Z').toISOString()).toBe('2026-08-28T10:00:00.000Z')
    expect(parseUtcDate('2026-08-28T10:00:00+03:00').toISOString()).toBe('2026-08-28T07:00:00.000Z')
  })
})
