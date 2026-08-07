import { describe, it, expect } from 'vitest'
import { generateTerrain } from '@/modules/map/utils/wastelandTerrain'

describe('generateTerrain', () => {
  it('should be deterministic — same output on every call', () => {
    const a = generateTerrain()
    const b = generateTerrain()
    const c = generateTerrain()

    expect(a).toEqual(b)
    expect(b).toEqual(c)
  })

  it('should generate 19 terrain patches (8 scorched + 6 dust + 5 craters)', () => {
    const terrain = generateTerrain()

    expect(terrain.patches).toHaveLength(19)
    expect(terrain.patches.filter((p) => p.kind === 'scorched')).toHaveLength(8)
    expect(terrain.patches.filter((p) => p.kind === 'dust')).toHaveLength(6)
    expect(terrain.patches.filter((p) => p.kind === 'crater')).toHaveLength(5)
  })

  it('should keep all patch opacities in the subtle 0.03–0.12 range', () => {
    const terrain = generateTerrain()

    for (const patch of terrain.patches) {
      expect(patch.opacity).toBeGreaterThanOrEqual(0.03)
      expect(patch.opacity).toBeLessThanOrEqual(0.12)
    }
  })

  it('should keep all patch centers within map bounds [0, 160]', () => {
    const terrain = generateTerrain()

    for (const patch of terrain.patches) {
      expect(patch.cx).toBeGreaterThanOrEqual(0)
      expect(patch.cx).toBeLessThanOrEqual(160)
      expect(patch.cy).toBeGreaterThanOrEqual(0)
      expect(patch.cy).toBeLessThanOrEqual(160)
    }
  })

  it('should generate 6 contour lines and 4 road segments', () => {
    const terrain = generateTerrain()

    expect(terrain.contours).toHaveLength(6)
    expect(terrain.roads).toHaveLength(4)
  })

  it('should have valid SVG path data for contours and roads', () => {
    const terrain = generateTerrain()

    for (const contour of terrain.contours) {
      expect(contour.d).toMatch(/^M [\d.]+ [\d.]+ C [\d.]+/)
      expect(contour.opacity).toBeGreaterThan(0)
    }

    for (const road of terrain.roads) {
      expect(road.d).toMatch(/^M [\d.]+ [\d.]+ Q [\d.]+/)
      expect(road.opacity).toBeGreaterThan(0)
      expect(road.dashArray).toBeTruthy()
    }
  })
})
