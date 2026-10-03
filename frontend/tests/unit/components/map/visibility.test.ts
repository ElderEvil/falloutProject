import { describe, expect, it } from 'vitest'
import { isHintLocation, isKnownLocation } from '@/modules/map/utils/visibility'

describe('discovery-only visibility', () => {
  it('treats unlocked locations and the home vault as known', () => {
    expect(isKnownLocation({ type: 'discovery', is_unlocked: true })).toBe(true)
    expect(isKnownLocation({ type: 'home_vault', is_unlocked: false })).toBe(true)
    expect(isKnownLocation({ type: 'origin' })).toBe(true)
  })

  it('treats locked non-signal locations as hints', () => {
    expect(isKnownLocation({ type: 'discovery', is_unlocked: false })).toBe(false)
    expect(isHintLocation({ type: 'discovery', is_unlocked: false })).toBe(true)
  })

  it('never treats the home vault or a vault signal as a hint', () => {
    expect(isHintLocation({ type: 'home_vault', is_unlocked: false })).toBe(false)
    expect(isHintLocation({ type: 'vault' })).toBe(false)
    expect(isHintLocation({ type: 'discovery', is_unlocked: true })).toBe(false)
  })
})
