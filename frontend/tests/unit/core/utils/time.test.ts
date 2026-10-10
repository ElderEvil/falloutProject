import { formatClock } from '@/core/utils/format'
import { describe, expect, it } from 'vitest'
import {
  computeRemainingSeconds,
  formatDaysRemaining,
  formatDuration,
  formatRelativeTime,
  formatRemaining,
  parseUtcMs,
} from '@/core/utils/time'

describe('parseUtcMs', () => {
  it('parses an explicit ISO UTC timestamp', () => {
    expect(parseUtcMs('2026-08-21T12:00:00Z')).toBe(Date.parse('2026-08-21T12:00:00Z'))
  })

  it('treats a space-separated zoneless timestamp as naive UTC', () => {
    expect(parseUtcMs('2026-08-21 12:00:00')).toBe(Date.parse('2026-08-21T12:00:00Z'))
  })

  it('treats a T-separated zoneless timestamp as naive UTC', () => {
    expect(parseUtcMs('2026-08-21T12:00:00')).toBe(Date.parse('2026-08-21T12:00:00Z'))
  })

  it('preserves an explicit numeric offset', () => {
    expect(parseUtcMs('2026-08-21T12:00:00+02:00')).toBe(Date.parse('2026-08-21T10:00:00Z'))
  })
})

describe('formatRemaining', () => {
  it('shows hours and minutes when at least an hour remains', () => {
    expect(formatRemaining(3661)).toBe('1h 1m remaining')
  })

  it('omits the hour segment under an hour', () => {
    expect(formatRemaining(1800)).toBe('30m remaining')
    expect(formatRemaining(59)).toBe('0m remaining')
  })
})

describe('formatDuration', () => {
  it('truncates hours and minutes by default', () => {
    expect(formatDuration(3661)).toBe('1h 1m')
    expect(formatDuration(59)).toBe('0h 0m')
  })

  it('adds a truncated seconds branch when includeSeconds is set', () => {
    expect(formatDuration(3661, { includeSeconds: true })).toBe('1h 1m')
    expect(formatDuration(125, { includeSeconds: true })).toBe('2m 5s')
    expect(formatDuration(45, { includeSeconds: true })).toBe('45s')
  })

  it('rounds minutes under the round strategy', () => {
    expect(formatDuration(3661, { rounding: 'round' })).toBe('1h 1m')
    expect(formatDuration(3600, { rounding: 'round' })).toBe('1h')
    expect(formatDuration(90, { rounding: 'round' })).toBe('2m')
    expect(formatDuration(30, { rounding: 'round' })).toBe('1m')
  })

  it('floors the seconds remainder for fractional input', () => {
    expect(formatDuration(65.9, { includeSeconds: true })).toBe('1m 5s')
    expect(formatDuration(59.9, { includeSeconds: true })).toBe('59s')
  })

  it('drops the hour segment under an hour when omitZeroHours is set', () => {
    expect(formatDuration(1800, { omitZeroHours: true })).toBe('30m')
    expect(formatDuration(3661, { omitZeroHours: true })).toBe('1h 1m')
  })

  it('appends the optional suffix', () => {
    expect(formatDuration(60, { suffix: 'remaining' })).toBe('0h 1m remaining')
    expect(formatDuration(45, { includeSeconds: true, suffix: 'left' })).toBe('45s left')
  })
})

describe('formatClock', () => {
  it('formats audio-style m:ss with unpadded minutes by default', () => {
    expect(formatClock(65, { showHours: false, padMinutes: false })).toBe('1:05')
    expect(formatClock(5, { showHours: false, padMinutes: false })).toBe('0:05')
  })

  it('allows padded minutes without overflowing to hours', () => {
    expect(formatClock(65, { showHours: false, padMinutes: true })).toBe('01:05')
    expect(formatClock(3661, { showHours: false, padMinutes: true })).toBe('61:01')
  })

  it('pads hours and minutes when showHours is set', () => {
    expect(formatClock(65, { showHours: true })).toBe('00:01:05')
    expect(formatClock(3661, { showHours: true })).toBe('01:01:01')
  })
})

describe('formatRelativeTime', () => {
  const now = Date.parse('2026-08-21T12:00:00Z')

  it('returns Just now under a minute', () => {
    expect(formatRelativeTime('2026-08-21T11:59:30Z', now)).toBe('Just now')
  })

  it('returns minutes past a minute', () => {
    expect(formatRelativeTime('2026-08-21T11:58:00Z', now)).toBe('2m ago')
  })

  it('returns hours past an hour', () => {
    expect(formatRelativeTime('2026-08-21T09:00:00Z', now)).toBe('3h ago')
  })

  it('returns days past a day', () => {
    expect(formatRelativeTime('2026-08-19T12:00:00Z', now)).toBe('2d ago')
  })

  it('parses a space-separated zoneless timestamp', () => {
    expect(formatRelativeTime('2026-08-21 11:00:00', now)).toBe('1h ago')
  })
})

describe('formatDaysRemaining', () => {
  it('singularizes one day', () => {
    expect(formatDaysRemaining(1)).toBe('1 day remaining')
  })

  it('pluralizes zero and many days', () => {
    expect(formatDaysRemaining(0)).toBe('0 days remaining')
    expect(formatDaysRemaining(3)).toBe('3 days remaining')
  })
})

describe('computeRemainingSeconds', () => {
  const now = Date.parse('2026-08-21T12:00:00Z')

  it('rounds positive remaining seconds', () => {
    expect(computeRemainingSeconds('2026-08-21T12:00:30Z', now)).toBe(30)
  })

  it('clamps an elapsed end timestamp to zero', () => {
    expect(computeRemainingSeconds('2026-08-21T11:59:00Z', now)).toBe(0)
  })

  it('handles a zoneless end timestamp', () => {
    expect(computeRemainingSeconds('2026-08-21 12:01:00', now)).toBe(60)
  })
})
