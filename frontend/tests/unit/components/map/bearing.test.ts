import { describe, it, expect } from 'vitest'
import {
  bearingDegrees,
  compassLabel,
  formatHeading,
  COMPASS_LABELS,
} from '@/modules/map/utils/bearing'

describe('bearingDegrees', () => {
  it('maps the SVG axis convention to compass degrees (x east, y south)', () => {
    const origin = { x: 80, y: 80 }
    // y decreases = north
    expect(bearingDegrees(origin, { x: 80, y: 70 })).toBe(0)
    // x increases = east
    expect(bearingDegrees(origin, { x: 90, y: 80 })).toBe(90)
    // y increases = south
    expect(bearingDegrees(origin, { x: 80, y: 90 })).toBe(180)
    // x decreases = west
    expect(bearingDegrees(origin, { x: 70, y: 80 })).toBe(270)
  })

  it('computes the intercardinal diagonals', () => {
    const origin = { x: 0, y: 0 }
    expect(bearingDegrees(origin, { x: 1, y: -1 })).toBe(45) // NE
    expect(bearingDegrees(origin, { x: 1, y: 1 })).toBe(135) // SE
    expect(bearingDegrees(origin, { x: -1, y: 1 })).toBe(225) // SW
    expect(bearingDegrees(origin, { x: -1, y: -1 })).toBe(315) // NW
  })

  it('normalizes results into [0, 360)', () => {
    const origin = { x: 0, y: 0 }
    // Just west of north: dx=-0.01, dy=-1 → slightly less than 360
    const westOfNorth = bearingDegrees(origin, { x: -0.01, y: -1 })
    expect(westOfNorth).toBeGreaterThan(350)
    expect(westOfNorth).toBeLessThan(360)
    // Just north of west: dx=-1, dy=-0.01 → slightly more than 270
    const northOfWest = bearingDegrees(origin, { x: -1, y: -0.01 })
    expect(northOfWest).toBeGreaterThan(270)
    expect(northOfWest).toBeLessThan(271)
  })

  it('returns 0 for a click exactly on the origin', () => {
    expect(bearingDegrees({ x: 40, y: 40 }, { x: 40, y: 40 })).toBe(0)
  })

  it('rounds float noise to 2 decimals', () => {
    const heading = bearingDegrees({ x: 0, y: 0 }, { x: 3, y: 1 })
    expect(Number.isInteger(heading * 100)).toBe(true)
  })
})

describe('compassLabel', () => {
  it('labels the 8 compass points', () => {
    expect(compassLabel(0)).toBe('N')
    expect(compassLabel(45)).toBe('NE')
    expect(compassLabel(90)).toBe('E')
    expect(compassLabel(135)).toBe('SE')
    expect(compassLabel(180)).toBe('S')
    expect(compassLabel(225)).toBe('SW')
    expect(compassLabel(270)).toBe('W')
    expect(compassLabel(315)).toBe('NW')
  })

  it('wraps around 360 and negative inputs', () => {
    expect(compassLabel(360)).toBe('N')
    expect(compassLabel(-90)).toBe('W')
  })

  it('snaps near-boundary headings to the nearest point', () => {
    expect(compassLabel(22)).toBe('N')
    expect(compassLabel(23)).toBe('NE')
  })

  it('only ever returns a known label', () => {
    for (let degrees = 0; degrees < 360; degrees += 7) {
      expect(COMPASS_LABELS).toContain(compassLabel(degrees))
    }
  })
})

describe('formatHeading', () => {
  it('renders the compass label and rounded degrees', () => {
    expect(formatHeading(90)).toBe('E / 90°')
    expect(formatHeading(90.4)).toBe('E / 90°')
    expect(formatHeading(315)).toBe('NW / 315°')
  })
})
