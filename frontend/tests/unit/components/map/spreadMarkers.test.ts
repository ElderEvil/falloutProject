import { describe, it, expect } from 'vitest'
import { spreadMarkers } from '@/modules/map/utils/spreadMarkers'

describe('spreadMarkers', () => {
  it('should return an empty map for empty input', () => {
    const result = spreadMarkers([])
    expect(result.size).toBe(0)
  })

  it('should return original position for a single marker', () => {
    const result = spreadMarkers([{ id: 'a', x: 50, y: 50 }])
    expect(result.get('a')).toEqual({ renderX: 50, renderY: 50 })
  })

  it('should not move markers that are far apart', () => {
    const markers = [
      { id: 'a', x: 10, y: 10 },
      { id: 'b', x: 90, y: 90 },
    ]
    const result = spreadMarkers(markers, { collisionRadius: 4.5 })

    expect(result.get('a')!.renderX).toBeCloseTo(10, 0)
    expect(result.get('a')!.renderY).toBeCloseTo(10, 0)
    expect(result.get('b')!.renderX).toBeCloseTo(90, 0)
    expect(result.get('b')!.renderY).toBeCloseTo(90, 0)
  })

  it('should spread overlapping markers apart', () => {
    const markers = [
      { id: 'a', x: 50, y: 50 },
      { id: 'b', x: 50, y: 50 },
    ]
    const result = spreadMarkers(markers, { collisionRadius: 4.5, maxDisplace: 2.5, iterations: 5 })

    const a = result.get('a')!
    const b = result.get('b')!

    // They should be separated (not at the same position)
    const dx = b.renderX - a.renderX
    const dy = b.renderY - a.renderY
    const dist = Math.sqrt(dx * dx + dy * dy)
    expect(dist).toBeGreaterThan(0)
  })

  it('should be deterministic — same input produces same output', () => {
    const markers = [
      { id: 'alpha', x: 30, y: 40 },
      { id: 'beta', x: 31, y: 41 },
      { id: 'gamma', x: 32, y: 40 },
    ]

    const result1 = spreadMarkers(markers)
    const result2 = spreadMarkers(markers)
    const result3 = spreadMarkers(markers)

    for (const id of ['alpha', 'beta', 'gamma']) {
      expect(result1.get(id)).toEqual(result2.get(id))
      expect(result2.get(id)).toEqual(result3.get(id))
    }
  })

  it('should clamp positions to [0, 160]', () => {
    const markers = [
      { id: 'a', x: 0, y: 0 },
      { id: 'b', x: 1, y: 1 },
      { id: 'c', x: 0.5, y: 0.5 },
    ]
    const result = spreadMarkers(markers, { collisionRadius: 4.5, maxDisplace: 3 })

    for (const [, pos] of result) {
      expect(pos.renderX).toBeGreaterThanOrEqual(0)
      expect(pos.renderX).toBeLessThanOrEqual(160)
      expect(pos.renderY).toBeGreaterThanOrEqual(0)
      expect(pos.renderY).toBeLessThanOrEqual(160)
    }
  })

  it('should limit displacement to maxDisplace from original position', () => {
    const markers = [
      { id: 'a', x: 50, y: 50 },
      { id: 'b', x: 51, y: 51 },
    ]
    const maxDisplace = 2.5
    const result = spreadMarkers(markers, { maxDisplace })

    for (const m of markers) {
      const pos = result.get(m.id)!
      const dx = pos.renderX - m.x
      const dy = pos.renderY - m.y
      const dist = Math.sqrt(dx * dx + dy * dy)
      expect(dist).toBeLessThanOrEqual(maxDisplace + 0.01)
    }
  })

  it('should handle coincident markers (exact same position) without NaN', () => {
    const markers = [
      { id: 'a', x: 50, y: 50 },
      { id: 'b', x: 50, y: 50 },
    ]
    const result = spreadMarkers(markers)

    for (const [, pos] of result) {
      expect(Number.isNaN(pos.renderX)).toBe(false)
      expect(Number.isNaN(pos.renderY)).toBe(false)
    }
  })

  it('should preserve geographic layout with many markers', () => {
    // Generate 20 markers in a line — spread should keep them roughly in order
    const markers = Array.from({ length: 20 }, (_, i) => ({
      id: `m-${i}`,
      x: 10 + i * 4,
      y: 50,
    }))

    const result = spreadMarkers(markers, { collisionRadius: 4.5, maxDisplace: 2.5 })

    // Check that the x-ordering is preserved (markers should not cross over each other)
    for (let i = 1; i < markers.length; i++) {
      const prev = result.get(markers[i - 1].id)!
      const curr = result.get(markers[i].id)!
      expect(curr.renderX).toBeGreaterThanOrEqual(prev.renderX - 0.1)
    }
  })
})
