import { describe, expect, it } from 'vitest'
import { isFrontierTile, scoutBand, scoutProbeTarget } from '@/core/views/map-prototype/scout'

const WIDTH = 5
const HEIGHT = 5

function grid(unexplored: Array<[number, number]>): Uint8Array {
  const mask = new Uint8Array(WIDTH * HEIGHT).fill(1)
  for (const [x, y] of unexplored) mask[y * WIDTH + x] = 0
  return mask
}

describe('scout', () => {
  describe('isFrontierTile', () => {
    const mask = grid([[2, 2]])

    it('accepts a revealed tile that touches unknown territory', () => {
      expect(isFrontierTile(mask, WIDTH, HEIGHT, 1, 2)).toBe(true)
      expect(isFrontierTile(mask, WIDTH, HEIGHT, 2, 1)).toBe(true)
    })

    it('rejects a revealed interior tile with no unknown neighbours', () => {
      expect(isFrontierTile(mask, WIDTH, HEIGHT, 0, 0)).toBe(false)
    })

    it('rejects an unrevealed tile', () => {
      expect(isFrontierTile(mask, WIDTH, HEIGHT, 2, 2)).toBe(false)
    })

    it('treats a fully revealed map as having no frontier', () => {
      expect(isFrontierTile(grid([]), WIDTH, HEIGHT, 0, 0)).toBe(false)
    })

    it('detects a frontier at the map edge', () => {
      expect(isFrontierTile(grid([[1, 0]]), WIDTH, HEIGHT, 0, 0)).toBe(true)
    })
  })

  describe('scoutProbeTarget', () => {
    it('steps past the frontier along the origin bearing', () => {
      expect(scoutProbeTarget({ x: 10, y: 10 }, { x: 0, y: 10 }, 5, 80, 80)).toEqual({ x: 15, y: 10 })
    })

    it('clamps the probe to the map bounds', () => {
      expect(scoutProbeTarget({ x: 78, y: 10 }, { x: 0, y: 10 }, 10, 80, 80)).toEqual({ x: 79, y: 10 })
      expect(scoutProbeTarget({ x: 1, y: 1 }, { x: 10, y: 10 }, 10, 80, 80)).toEqual({ x: 0, y: 0 })
    })

    it('returns the frontier when origin equals the frontier', () => {
      expect(scoutProbeTarget({ x: 4, y: 4 }, { x: 4, y: 4 }, 8, 80, 80)).toEqual({ x: 4, y: 4 })
    })
  })

  describe('scoutBand', () => {
    it('returns a coarse range, not a precise number', () => {
      expect(scoutBand(1)).toEqual({ low: 1, high: 3 })
      expect(scoutBand(3)).toEqual({ low: 2, high: 6 })
      expect(scoutBand(5)).toEqual({ low: 4, high: 8 })
      expect(scoutBand(10)).toEqual({ low: 8, high: 16 })
      expect(scoutBand(30)).toEqual({ low: 24, high: 40 })
    })
  })
})
