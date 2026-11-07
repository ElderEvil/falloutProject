import { describe, expect, it } from 'vite-plus/test'
import { isSetupComplete, parseSetupPreference } from '@/modules/profile/models/setup'

describe('setup preference', () => {
  it('reads a completed setup record', () => {
    expect(parseSetupPreference({ version: 1, completed: true, skipped: false })).toEqual({
      version: 1,
      completed: true,
      skipped: false,
    })
  })

  it('defaults a missing skipped flag to false', () => {
    expect(parseSetupPreference({ version: 1, completed: true })).toEqual({
      version: 1,
      completed: true,
      skipped: false,
    })
  })

  it.each([
    null,
    undefined,
    'done',
    [],
    {},
    { version: 2, completed: true },
    { version: 1, completed: 'yes' },
    { version: 1, completed: true, skipped: 'no' },
  ])('treats malformed records as incomplete: %j', (raw) => {
    expect(parseSetupPreference(raw)).toBeNull()
  })

  it('only reports completion for a valid completed record', () => {
    expect(isSetupComplete({ setup: { version: 1, completed: true, skipped: false } })).toBe(true)
    expect(isSetupComplete({ setup: { version: 1, completed: false, skipped: false } })).toBe(false)
    expect(isSetupComplete({ setup: { version: 1, completed: true, skipped: 'no' } })).toBe(false)
    expect(isSetupComplete({})).toBe(false)
    expect(isSetupComplete(null)).toBe(false)
  })
})
