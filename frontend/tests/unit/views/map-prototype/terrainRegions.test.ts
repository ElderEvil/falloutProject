import { describe, expect, it } from 'vitest'
import { extractTerrainRegions } from '@/core/views/map-prototype/terrainRegions'
import type { RegionPoint, TerrainRegion } from '@/core/views/map-prototype/terrainRegions'
import { generateWorld } from '@/modules/map/utils/atlasWorldgen'
import type { TerrainType } from '@/modules/map/utils/atlasWorldgen'

const makeGrid = (width: number, height: number, fill: TerrainType): TerrainType[] =>
  new Array<TerrainType>(width * height).fill(fill)

const setTile = (terrain: TerrainType[], width: number, x: number, y: number, kind: TerrainType): void => {
  terrain[y * width + x] = kind
}

/** Shoelace area of a closed ring; the sign encodes the winding direction. */
const signedArea = (ring: RegionPoint[]): number => {
  let area = 0
  for (let i = 0; i < ring.length - 1; i++) {
    const a = ring[i]
    const b = ring[i + 1]
    if (a === undefined || b === undefined) continue
    area += a.x * b.y - b.x * a.y
  }
  return area / 2
}

/** Rings are explicitly closed: the last point repeats the first. */
const isClosed = (ring: RegionPoint[]): boolean => {
  const first = ring[0]
  const last = ring[ring.length - 1]
  return first !== undefined && last !== undefined && first.x === last.x && first.y === last.y
}

/** Non-zero winding point-in-polygon over all rings of one region. */
const insideRings = (rings: RegionPoint[][], px: number, py: number): boolean => {
  let winding = 0
  for (const ring of rings) {
    for (let i = 0; i < ring.length - 1; i++) {
      const a = ring[i]
      const b = ring[i + 1]
      if (a === undefined || b === undefined) continue
      const cross = (b.x - a.x) * (py - a.y) - (px - a.x) * (b.y - a.y)
      if (a.y <= py) {
        if (b.y > py && cross > 0) winding++
      } else if (b.y <= py && cross < 0) {
        winding--
      }
    }
  }
  return winding !== 0
}

/** A cell whose full (2r+1)² neighborhood shares its terrain sits ≥ r tiles from any boundary. */
const isInterior = (
  terrain: TerrainType[],
  width: number,
  x: number,
  y: number,
  kind: TerrainType,
  radius: number,
): boolean => {
  for (let dy = -radius; dy <= radius; dy++) {
    for (let dx = -radius; dx <= radius; dx++) {
      if (terrain[(y + dy) * width + x + dx] !== kind) return false
    }
  }
  return true
}

describe('terrainRegions', () => {
  describe('extractTerrainRegions', () => {
    it('returns one closed ring for a single full-grid region', () => {
      const terrain = makeGrid(5, 4, 'hills')
      const regions = extractTerrainRegions(terrain, 5, 4)
      expect(regions).toHaveLength(1)
      expect(regions[0]?.terrain).toBe('hills')
      const rings = regions[0]?.rings ?? []
      expect(rings).toHaveLength(1)
      const ring = rings[0] ?? []
      expect(isClosed(ring)).toBe(true)
      expect(ring.length).toBeGreaterThan(4)
      for (const point of ring) {
        expect(point.x).toBeGreaterThanOrEqual(0)
        expect(point.x).toBeLessThanOrEqual(5)
        expect(point.y).toBeGreaterThanOrEqual(0)
        expect(point.y).toBeLessThanOrEqual(4)
      }
    })

    it('traces a closed ring around a small island', () => {
      const terrain = makeGrid(6, 6, 'wasteland')
      setTile(terrain, 6, 2, 2, 'forest')
      setTile(terrain, 6, 3, 2, 'forest')
      setTile(terrain, 6, 2, 3, 'forest')
      setTile(terrain, 6, 3, 3, 'forest')
      const regions = extractTerrainRegions(terrain, 6, 6)
      const forest = regions.find(region => region.terrain === 'forest')
      expect(forest).toBeDefined()
      const rings = forest?.rings ?? []
      expect(rings).toHaveLength(1)
      const ring = rings[0] ?? []
      expect(isClosed(ring)).toBe(true)
      for (const point of ring) {
        expect(point.x).toBeGreaterThanOrEqual(2)
        expect(point.x).toBeLessThanOrEqual(4)
        expect(point.y).toBeGreaterThanOrEqual(2)
        expect(point.y).toBeLessThanOrEqual(4)
      }
    })

    it('keeps adjacent different biomes as separate regions', () => {
      const terrain = makeGrid(4, 2, 'wasteland')
      for (let y = 0; y < 2; y++) {
        setTile(terrain, 4, 0, y, 'forest')
        setTile(terrain, 4, 1, y, 'forest')
        setTile(terrain, 4, 2, y, 'hills')
        setTile(terrain, 4, 3, y, 'hills')
      }
      const regions = extractTerrainRegions(terrain, 4, 2)
      expect(regions.map(region => region.terrain)).toEqual(['forest', 'hills'])
      for (const region of regions) {
        expect(region.rings).toHaveLength(1)
        expect(isClosed(region.rings[0] ?? [])).toBe(true)
      }
      const forestRing = regions[0]?.rings[0] ?? []
      const hillsRing = regions[1]?.rings[0] ?? []
      expect(Math.max(...forestRing.map(point => point.x))).toBeLessThanOrEqual(2)
      expect(Math.min(...hillsRing.map(point => point.x))).toBeGreaterThanOrEqual(2)
    })

    it('keeps smoothed points within the component bounds', () => {
      const terrain = makeGrid(5, 5, 'wasteland')
      setTile(terrain, 5, 2, 1, 'ruins')
      setTile(terrain, 5, 1, 2, 'ruins')
      setTile(terrain, 5, 2, 2, 'ruins')
      setTile(terrain, 5, 3, 2, 'ruins')
      setTile(terrain, 5, 2, 3, 'ruins')
      const regions = extractTerrainRegions(terrain, 5, 5)
      const ruins = regions.find(region => region.terrain === 'ruins')
      expect(ruins).toBeDefined()
      for (const ring of ruins?.rings ?? []) {
        for (const point of ring) {
          expect(point.x).toBeGreaterThanOrEqual(1)
          expect(point.x).toBeLessThanOrEqual(4)
          expect(point.y).toBeGreaterThanOrEqual(1)
          expect(point.y).toBeLessThanOrEqual(4)
        }
      }
    })

    it('punches holes with an opposite-wound inner ring', () => {
      const terrain = makeGrid(5, 5, 'forest')
      setTile(terrain, 5, 2, 2, 'wasteland')
      const regions = extractTerrainRegions(terrain, 5, 5)
      const forest = regions.find(region => region.terrain === 'forest')
      expect(forest?.rings).toHaveLength(2)
      const outer = forest?.rings.find(ring => signedArea(ring) > 0)
      const hole = forest?.rings.find(ring => signedArea(ring) < 0)
      expect(outer).toBeDefined()
      expect(hole).toBeDefined()
      if (outer !== undefined && hole !== undefined) {
        expect(Math.abs(signedArea(outer))).toBeGreaterThan(Math.abs(signedArea(hole)))
      }
    })

    it('keeps generated-world interior cell centers inside their terrain regions', () => {
      const world = generateWorld({ seed: 'region-probe', locationCount: 100 })
      const { width, height } = world.config
      const regions = extractTerrainRegions(world.terrain, width, height)
      const byTerrain = new Map<TerrainType, TerrainRegion[]>()
      for (const region of regions) {
        const list = byTerrain.get(region.terrain) ?? []
        list.push(region)
        byTerrain.set(region.terrain, list)
      }
      let checked = 0
      for (let y = 2; y < height - 2; y++) {
        for (let x = 2; x < width - 2; x++) {
          const kind = world.terrain[y * width + x]
          if (kind === undefined || !isInterior(world.terrain, width, x, y, kind, 2)) continue
          checked++
          const inside = (byTerrain.get(kind) ?? []).some(region =>
            insideRings(region.rings, x + 0.5, y + 0.5),
          )
          expect(inside).toBe(true)
        }
      }
      expect(checked).toBeGreaterThan(0)
    })

    it('is deterministic for the same input', () => {
      const terrain = makeGrid(9, 7, 'wasteland')
      setTile(terrain, 9, 1, 1, 'forest')
      setTile(terrain, 9, 2, 1, 'forest')
      setTile(terrain, 9, 2, 2, 'forest')
      setTile(terrain, 9, 6, 5, 'water')
      setTile(terrain, 9, 7, 5, 'water')
      setTile(terrain, 9, 6, 4, 'hills')
      const first = extractTerrainRegions(terrain, 9, 7)
      const second = extractTerrainRegions(terrain, 9, 7)
      expect(first.length).toBeGreaterThan(0)
      expect(first).toEqual(second)
    })
  })
})
