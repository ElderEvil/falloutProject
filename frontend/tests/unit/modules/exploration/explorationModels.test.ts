import { describe, it, expect } from 'vitest'
import {
  EXPLORATION_EVENT_TYPES,
  EVENT_COLOR_MAP,
  EVENT_ICON_MAP,
  getRarityColor,
} from '@/modules/exploration/models/exploration'

describe('exploration event model maps', () => {
  it('covers every canonical event type with an icon and color', () => {
    for (const type of EXPLORATION_EVENT_TYPES) {
      expect(EVENT_ICON_MAP[type], `icon for ${type}`).toBeTruthy()
      expect(EVENT_COLOR_MAP[type], `color for ${type}`).toBeTruthy()
    }
  })

  it('has no orphaned keys besides default', () => {
    const canonical: Set<string> = new Set(EXPLORATION_EVENT_TYPES)
    for (const key of Object.keys(EVENT_ICON_MAP)) {
      if (key !== 'default') expect(canonical.has(key), `orphan icon key ${key}`).toBe(true)
    }
    for (const key of Object.keys(EVENT_COLOR_MAP)) {
      if (key !== 'default') expect(canonical.has(key), `orphan color key ${key}`).toBe(true)
    }
  })

  it('normalizes rarity labels before selecting their color', () => {
    expect(getRarityColor('rare')).toBe('var(--color-rarity-rare)')
    expect(getRarityColor(' LEGENDARY ')).toBe('var(--color-rarity-legendary)')
    expect(getRarityColor('unknown')).toBe('var(--color-rarity-common)')
  })
})
