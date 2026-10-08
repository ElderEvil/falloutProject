import { describe, expect, it } from 'vitest'
import {
  ANCHOR_CONSTRAINT_VERSION,
  DEFAULT_WORLD_CONFIG,
  HOURS_PER_COST,
  ROAD_COST,
  ROAD_TRAVEL_DISCOUNT,
  SHARED_ANCHOR_FIXTURES,
  TRAVEL_COST,
  constrainTerrainToAnchors,
  findPath,
  generateWorld,
} from '@/modules/map/utils/atlasWorldgen'
import type { GeneratedWorld, TerrainAnchor, TerrainType } from '@/modules/map/utils/atlasWorldgen'

const WIDTH = 80
const HEIGHT = 80

// Mirrors VAULT_SCAVENGE_BUDGET / VAULT_CACHE_RADIUS in worldgen.ts.
const SCAVENGE_BUDGET = 6
const CACHE_RADIUS = 3

/**
 * Test-local multi-source Dijkstra over TRAVEL_COST — the same routed-cost
 * field the generator uses for the scavenge guarantee, so the test can verify
 * caches are only placed for vaults that actually need one.
 */
function scavengeCost(
  terrain: TerrainType[],
  width: number,
  height: number,
  sources: Array<{ x: number; y: number }>,
): Float64Array {
  const cost = new Float64Array(width * height).fill(Infinity)
  const closed = new Uint8Array(width * height)
  const heap: Array<{ idx: number; f: number }> = []
  const push = (idx: number, f: number): void => {
    heap.push({ idx, f })
    let i = heap.length - 1
    while (i > 0) {
      const p = (i - 1) >> 1
      if (heap[p].f <= heap[i].f) break
      const tmp = heap[p]
      heap[p] = heap[i]
      heap[i] = tmp
      i = p
    }
  }
  const pop = (): number | null => {
    if (heap.length === 0) return null
    const top = heap[0]
    const last = heap.pop()
    if (heap.length > 0 && last !== undefined) {
      heap[0] = last
      let i = 0
      for (;;) {
        const l = i * 2 + 1
        const r = l + 1
        let smallest = i
        if (l < heap.length && heap[l].f < heap[smallest].f) smallest = l
        if (r < heap.length && heap[r].f < heap[smallest].f) smallest = r
        if (smallest === i) break
        const tmp = heap[i]
        heap[i] = heap[smallest]
        heap[smallest] = tmp
        i = smallest
      }
    }
    return top.idx
  }
  for (const s of sources) {
    const idx = s.y * width + s.x
    if (cost[idx] === 0) continue
    cost[idx] = 0
    push(idx, 0)
  }
  const NEIGHBORS: ReadonlyArray<readonly [number, number, boolean]> = [
    [1, 0, false],
    [-1, 0, false],
    [0, 1, false],
    [0, -1, false],
    [1, 1, true],
    [1, -1, true],
    [-1, 1, true],
    [-1, -1, true],
  ]
  while (heap.length > 0) {
    const cur = pop()
    if (cur === null) break
    if (closed[cur] === 1) continue
    closed[cur] = 1
    const cx = cur % width
    const cy = Math.floor(cur / width)
    for (const [dx, dy, diag] of NEIGHBORS) {
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
      const nIdx = ny * width + nx
      const tileCost = TRAVEL_COST[terrain[nIdx]]
      if (tileCost === Infinity) continue
      if (diag) {
        if (TRAVEL_COST[terrain[cy * width + cx + dx]] === Infinity) continue
        if (TRAVEL_COST[terrain[(cy + dy) * width + cx]] === Infinity) continue
      }
      const moveCost = tileCost * (diag ? Math.SQRT2 : 1)
      const tentative = cost[cur] + moveCost
      if (tentative < cost[nIdx]) {
        cost[nIdx] = tentative
        push(nIdx, tentative)
      }
    }
  }
  return cost
}

/** Size of the passable region containing the origin (4-connectivity). */
function originRegionSize(world: ReturnType<typeof generateWorld>): number {
  const { terrain, config, origin } = world
  const width = config.width
  const height = config.height
  const seen = new Uint8Array(width * height)
  const startIdx = origin.y * width + origin.x
  const queue: number[] = [startIdx]
  seen[startIdx] = 1
  let count = 0
  while (queue.length > 0) {
    const cur = queue.pop() as number
    count++
    const cx = cur % width
    const cy = Math.floor(cur / width)
    for (const [dx, dy] of [
      [1, 0],
      [-1, 0],
      [0, 1],
      [0, -1],
    ]) {
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
      const nIdx = ny * width + nx
      if (seen[nIdx] === 1) continue
      if (terrain[nIdx] === 'water') continue
      seen[nIdx] = 1
      queue.push(nIdx)
    }
  }
  return count
}

/** 4-connected component sizes of a terrain kind, largest first. */
function componentSizes(terrain: TerrainType[], width: number, height: number, kind: TerrainType): number[] {
  const seen = new Uint8Array(width * height)
  const sizes: number[] = []
  for (let i = 0; i < terrain.length; i++) {
    if (terrain[i] !== kind || seen[i] === 1) continue
    const queue: number[] = [i]
    seen[i] = 1
    let size = 0
    let head = 0
    while (head < queue.length) {
      const cur = queue[head]
      head++
      size++
      const cx = cur % width
      const cy = Math.floor(cur / width)
      for (const [dx, dy] of [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
      ]) {
        const nx = cx + dx
        const ny = cy + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const nIdx = ny * width + nx
        if (seen[nIdx] === 1 || terrain[nIdx] !== kind) continue
        seen[nIdx] = 1
        queue.push(nIdx)
      }
    }
    sizes.push(size)
  }
  return sizes.sort((a, b) => b - a)
}

/** Bounding box of the largest 4-connected component of a terrain kind. */
function largestComponentBBox(
  terrain: TerrainType[],
  width: number,
  height: number,
  kind: TerrainType,
): { minX: number; maxX: number; minY: number; maxY: number } | null {
  const sizes = componentSizes(terrain, width, height, kind)
  const target = sizes[0]
  if (target === undefined) return null
  const seen = new Uint8Array(width * height)
  for (let i = 0; i < terrain.length; i++) {
    if (terrain[i] !== kind || seen[i] === 1) continue
    const queue: number[] = [i]
    seen[i] = 1
    const cells: number[] = []
    let head = 0
    while (head < queue.length) {
      const cur = queue[head]
      head++
      cells.push(cur)
      const cx = cur % width
      const cy = Math.floor(cur / width)
      for (const [dx, dy] of [
        [1, 0],
        [-1, 0],
        [0, 1],
        [0, -1],
      ]) {
        const nx = cx + dx
        const ny = cy + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const nIdx = ny * width + nx
        if (seen[nIdx] === 1 || terrain[nIdx] !== kind) continue
        seen[nIdx] = 1
        queue.push(nIdx)
      }
    }
    if (cells.length === target) {
      let minX = width
      let maxX = -1
      let minY = height
      let maxY = -1
      for (const c of cells) {
        const x = c % width
        const y = Math.floor(c / width)
        if (x < minX) minX = x
        if (x > maxX) maxX = x
        if (y < minY) minY = y
        if (y > maxY) maxY = y
      }
      return { minX, maxX, minY, maxY }
    }
  }
  return null
}

/** Perpendicular distance of a point from the chord A→B (tiles). */
function perpendicularDeviation(
  p: { x: number; y: number },
  a: { x: number; y: number },
  b: { x: number; y: number },
): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const d = Math.hypot(dx, dy)
  if (d === 0) return 0
  return Math.abs(dx * (p.y - a.y) - dy * (p.x - a.x)) / d
}

describe('worldgen', () => {
  it('generates a byte-identical world for the same seed', () => {
    const a = generateWorld({ seed: 'test-seed' })
    const b = generateWorld({ seed: 'test-seed' })
    expect(JSON.stringify(a)).toBe(JSON.stringify(b))
  })

  it('generates different terrain for different seeds', () => {
    const a = generateWorld({ seed: 'seed-a' })
    const b = generateWorld({ seed: 'seed-b' })
    expect(a.terrain).not.toEqual(b.terrain)
  })

  it('uses defaults when no config is given', () => {
    const world = generateWorld()
    expect(world.config).toEqual(DEFAULT_WORLD_CONFIG)
    expect(world.terrain).toHaveLength(WIDTH * HEIGHT)
  })

  it('produces an 80x80 map with all five terrain types and a small water fraction', () => {
    const world = generateWorld()
    expect(world.terrain).toHaveLength(WIDTH * HEIGHT)
    const counts: Record<TerrainType, number> = { wasteland: 0, forest: 0, ruins: 0, hills: 0, water: 0 }
    for (const t of world.terrain) counts[t]++
    for (const t of ['wasteland', 'forest', 'ruins', 'hills', 'water'] as const) {
      expect(counts[t]).toBeGreaterThan(0)
    }
    expect(counts.water / world.terrain.length).toBeLessThan(0.15)
  })

  it('keeps travelCost parallel to terrain', () => {
    const world = generateWorld()
    expect(world.travelCost).toHaveLength(world.terrain.length)
    for (let i = 0; i < world.terrain.length; i++) {
      expect(world.travelCost[i]).toBe(TRAVEL_COST[world.terrain[i]])
    }
  })

  it('places one vault per sector with sequential ids, claimed=false, never on water', () => {
    const world = generateWorld()
    expect(world.vaultSlots).toHaveLength(100)
    world.vaultSlots.forEach((v, i) => {
      expect(v.id).toBe(i)
      expect(v.claimed).toBe(false)
      expect(world.terrain[v.y * WIDTH + v.x]).not.toBe('water')
    })
  })

  it('places vaults inside their own sector bounds', () => {
    const world = generateWorld()
    for (const v of world.vaultSlots) {
      const x0 = Math.floor((v.sectorCol * WIDTH) / 10)
      const x1 = Math.floor(((v.sectorCol + 1) * WIDTH) / 10)
      const y0 = Math.floor((v.sectorRow * HEIGHT) / 10)
      const y1 = Math.floor(((v.sectorRow + 1) * HEIGHT) / 10)
      expect(v.x).toBeGreaterThanOrEqual(x0)
      expect(v.x).toBeLessThan(x1)
      expect(v.y).toBeGreaterThanOrEqual(y0)
      expect(v.y).toBeLessThan(y1)
    }
  })

  it('places exactly locationCount main locations plus supply caches, with unique names, none on water', () => {
    const world = generateWorld()
    const main = world.locations.filter(l => l.kind !== 'supply_cache')
    // supply_cache is a guarantee overlay, not part of the locationCount
    // distribution, so locations.length may exceed locationCount by caches.
    expect(main).toHaveLength(DEFAULT_WORLD_CONFIG.locationCount)
    const names = new Set(world.locations.map(l => l.name))
    expect(names.size).toBe(world.locations.length)
    for (const l of world.locations) {
      expect(world.terrain[l.y * WIDTH + l.x]).not.toBe('water')
    }
  })

  it('places exactly the requested locationCount of main kinds across a sane range', () => {
    for (const count of [10, 50, 200, 300, 600]) {
      const world = generateWorld({ seed: 'density', locationCount: count })
      const main = world.locations.filter(l => l.kind !== 'supply_cache')
      expect(main, `count ${count}`).toHaveLength(count)
      expect(world.locations.length, `count ${count}`).toBeGreaterThanOrEqual(count)
    }
  })

  it('keeps locations off water, off vault slots and off each other at 50 and 300', () => {
    for (const count of [50, 300]) {
      const world = generateWorld({ seed: 'density', locationCount: count })
      const vaultTiles = new Set(world.vaultSlots.map(v => v.y * WIDTH + v.x))
      const tiles = new Set<number>()
      for (const l of world.locations) {
        const idx = l.y * WIDTH + l.x
        expect(world.terrain[idx], `water at ${l.name}`).not.toBe('water')
        expect(vaultTiles.has(idx), `vault slot at ${l.name}`).toBe(false)
        expect(tiles.has(idx), `duplicate tile at ${l.name}`).toBe(false)
        tiles.add(idx)
      }
    }
  })

  it('keeps location names unique at 300', () => {
    const world = generateWorld({ seed: 'density', locationCount: 300 })
    const names = new Set(world.locations.map(l => l.name))
    expect(names.size).toBe(world.locations.length)
  })

  it('keeps vault positions stable when locationCount changes', () => {
    const a = generateWorld({ seed: 'stable', locationCount: 50 })
    const b = generateWorld({ seed: 'stable', locationCount: 60 })
    expect(a.vaultSlots).toEqual(b.vaultSlots)
  })

  it('builds a road network with valid edges and non-water paths', () => {
    const world = generateWorld()
    expect(world.roads.length).toBeGreaterThan(0)
    const ids = new Set(world.locations.map(l => l.id))
    for (const road of world.roads) {
      expect(ids.has(road.from)).toBe(true)
      expect(ids.has(road.to)).toBe(true)
      expect(road.path.length).toBe(road.length)
      expect(road.path.length).toBeGreaterThan(0)
      for (const t of road.path) {
        expect(world.terrain[t.y * WIDTH + t.x]).not.toBe('water')
      }
    }
  })

  it('bends long routed road edges through seeded off-chord waypoints', () => {
    for (const seed of ['vault-111', 'alpha', 'beta']) {
      const world = generateWorld({ seed })
      const again = generateWorld({ seed })
      const byId = new Map(world.locations.map(l => [l.id, l]))
      let maxPathDeviation = 0
      let maxWaypointDeviation = 0
      let longEdges = 0
      for (const road of world.roads) {
        const a = byId.get(road.from)
        const b = byId.get(road.to)
        if (a === undefined || b === undefined) continue
        const chord = Math.hypot(a.x - b.x, a.y - b.y)
        if (chord < 10) continue
        longEdges++
        for (const t of road.path) {
          maxPathDeviation = Math.max(maxPathDeviation, perpendicularDeviation(t, a, b))
        }
        // The bend must come from routed waypoints: each waypoint is a tile on
        // the actual road path, pushed off the chord by the seeded offset.
        expect(road.waypoints.length, `seed ${seed} edge ${road.from}-${road.to}`).toBeGreaterThan(0)
        for (const w of road.waypoints) {
          expect(
            road.path.some(t => t.x === w.x && t.y === w.y),
            `seed ${seed} waypoint ${w.x},${w.y} not on path`,
          ).toBe(true)
          maxWaypointDeviation = Math.max(maxWaypointDeviation, perpendicularDeviation(w, a, b))
        }
      }
      expect(longEdges, `seed ${seed}`).toBeGreaterThan(0)
      // A straight A* diagonal would hug its chord within a tile everywhere;
      // seeded waypoints must push the path visibly off it.
      expect(maxPathDeviation, `seed ${seed}`).toBeGreaterThan(1.5)
      expect(maxWaypointDeviation, `seed ${seed}`).toBeGreaterThan(1)
      // Deterministic: the same seed reproduces the same curvature.
      expect(again.roads.map(r => r.waypoints)).toEqual(world.roads.map(r => r.waypoints))
    }
  })

  it('places the origin on wasteland near the map center', () => {
    const world = generateWorld()
    expect(world.terrain[world.origin.y * WIDTH + world.origin.x]).toBe('wasteland')
    expect(Math.abs(world.origin.x - 40)).toBeLessThanOrEqual(20)
    expect(Math.abs(world.origin.y - 40)).toBeLessThanOrEqual(20)
  })

  it('guarantees every vault is reachable from the origin', () => {
    const world = generateWorld()
    expect(world.validation.totalVaults).toBe(100)
    expect(world.validation.reachableVaults).toBe(100)
    expect(world.validation.unreachableVaultIds).toEqual([])
  })

  it('reports scavenge, isolated regions and valuable distribution', () => {
    const world = generateWorld()
    expect(world.validation.vaultsWithNearbyScavenge).toBe(world.validation.totalVaults)
    expect(world.validation.isolatedRegions).toBeGreaterThanOrEqual(0)
    const buckets = Object.keys(world.validation.valuableByRegion)
    expect(buckets).toHaveLength(16)
    const total = Object.values(world.validation.valuableByRegion).reduce((a, b) => a + b, 0)
    expect(total).toBe(world.locations.length + world.vaultSlots.length)
  })

  it('guarantees every vault a scavenge site within the routed budget across seeds', () => {
    for (const seed of ['alpha', 'beta', 'gamma', 'delta', 'epsilon']) {
      const world = generateWorld({ seed })
      expect(world.validation.vaultsWithNearbyScavenge, `seed ${seed}`).toBe(world.validation.totalVaults)
    }
  })

  it('produces dominant wasteland, low water, all five types and a large passable region', () => {
    for (const seed of ['vault-111', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']) {
      const world = generateWorld({ seed })
      const counts: Record<TerrainType, number> = { wasteland: 0, forest: 0, ruins: 0, hills: 0, water: 0 }
      for (const t of world.terrain) counts[t]++
      const total = world.terrain.length
      expect(counts.wasteland, `seed ${seed}`).toBeGreaterThan(counts.ruins)
      expect(counts.wasteland, `seed ${seed}`).toBeGreaterThan(counts.hills)
      expect(counts.wasteland, `seed ${seed}`).toBeGreaterThan(counts.water)
      expect(counts.water / total, `seed ${seed}`).toBeLessThan(0.15)
      for (const t of ['wasteland', 'forest', 'ruins', 'hills', 'water'] as const) {
        expect(counts[t], `seed ${seed}`).toBeGreaterThan(0)
      }
      expect(originRegionSize(world), `seed ${seed}`).toBeGreaterThan(total * 0.5)
    }
  })

  it('places supply caches only for underserved vaults, deterministically', () => {
    for (const seed of ['vault-111', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']) {
      const world = generateWorld({ seed })
      const caches = world.locations.filter(l => l.kind === 'supply_cache')
      // Deterministic count for the same seed.
      const again = generateWorld({ seed })
      expect(again.locations.filter(l => l.kind === 'supply_cache')).toHaveLength(caches.length)
      // Every cache sits next to a vault (within VAULT_CACHE_RADIUS).
      for (const c of caches) {
        const nearest = Math.min(...world.vaultSlots.map(v => Math.hypot(v.x - c.x, v.y - c.y)))
        expect(nearest, `${c.name}`).toBeLessThanOrEqual(CACHE_RADIUS)
      }
      // The number of caches equals the number of vaults underserved when only
      // non-cache locations count (routed cost > VAULT_SCAVENGE_BUDGET).
      const nonCache = world.locations.filter(l => l.kind !== 'supply_cache')
      const cost = scavengeCost(world.terrain, WIDTH, HEIGHT, nonCache)
      const underserved = world.vaultSlots.filter(v => cost[v.y * WIDTH + v.x] > SCAVENGE_BUDGET).length
      expect(underserved, `seed ${seed}`).toBe(caches.length)
    }
  })

  it('findPath returns a valid path between origin and a vault', () => {
    const world = generateWorld()
    const vault = world.vaultSlots[0]
    const result = findPath(world, world.origin, { x: vault.x, y: vault.y })
    expect(result).not.toBeNull()
    if (result !== null) {
      expect(result.path.length).toBeGreaterThan(0)
      expect(result.path[0]).toEqual(world.origin)
      expect(result.path[result.path.length - 1]).toEqual({ x: vault.x, y: vault.y })
      expect(result.cost).toBeGreaterThan(0)
      expect(result.hours).toBe(Math.round(result.cost * HOURS_PER_COST))
      for (const t of result.path) {
        expect(world.terrain[t.y * WIDTH + t.x]).not.toBe('water')
      }
    }
  })

  it('findPath returns null for an unreachable water tile', () => {
    const world = generateWorld()
    const waterIdx = world.terrain.indexOf('water')
    expect(waterIdx).toBeGreaterThanOrEqual(0)
    const water = { x: waterIdx % WIDTH, y: Math.floor(waterIdx / WIDTH) }
    expect(findPath(world, world.origin, water)).toBeNull()
  })

  it('findPath from a tile to itself returns a zero-cost single-tile path', () => {
    const world = generateWorld()
    expect(findPath(world, world.origin, world.origin)).toEqual({
      path: [world.origin],
      cost: 0,
      hours: 0,
    })
  })

  describe('findPath visibility mask', () => {
    function line(): GeneratedWorld {
      const width = 5
      return {
        config: { ...DEFAULT_WORLD_CONFIG, width, height: 1, sectorCols: 1, sectorRows: 1, locationCount: 0 },
        terrain: Array<TerrainType>(width).fill('wasteland'),
        travelCost: Array<number>(width).fill(TRAVEL_COST.wasteland),
        vaultSlots: [],
        locations: [],
        roads: [],
        roadMask: new Uint8Array(width),
        origin: { x: 0, y: 0 },
        anchorDiagnostics: [],
        validation: {
          totalVaults: 0,
          reachableVaults: 0,
          unreachableVaultIds: [],
          vaultsWithNearbyScavenge: 0,
          isolatedRegions: 0,
          valuableByRegion: {},
        },
      }
    }

    it('routes only through explored cells', () => {
      const world = line()
      const explored = new Uint8Array(5)
      explored[0] = 1
      explored[1] = 1
      explored[4] = 1
      expect(findPath(world, { x: 0, y: 0 }, { x: 4, y: 0 }, { explored })).toBeNull()

      explored[2] = 1
      explored[3] = 1
      const result = findPath(world, { x: 0, y: 0 }, { x: 4, y: 0 }, { explored })
      expect(result).not.toBeNull()
      expect(result!.path.map(p => p.x)).toEqual([0, 1, 2, 3, 4])
    })

    it('returns null when an endpoint is outside the mask', () => {
      const world = line()
      const explored = new Uint8Array(5).fill(1)
      explored[4] = 0
      expect(findPath(world, { x: 0, y: 0 }, { x: 4, y: 0 }, { explored })).toBeNull()
    })

    it('searches the full grid when no mask is provided', () => {
      const world = line()
      expect(findPath(world, { x: 0, y: 0 }, { x: 4, y: 0 })).not.toBeNull()
    })
  })

  describe('road travel discount', () => {
    function twoRow(withRoad: boolean): GeneratedWorld {
      const width = 6
      const height = 2
      const terrain: TerrainType[] = [
        ...Array<TerrainType>(width).fill('ruins'),
        ...Array<TerrainType>(width).fill('wasteland'),
      ]
      const roadMask = new Uint8Array(width * height)
      if (withRoad) for (let x = 0; x < width; x++) roadMask[width + x] = 1
      return {
        config: { ...DEFAULT_WORLD_CONFIG, width, height, sectorCols: 1, sectorRows: 1, locationCount: 0 },
        terrain,
        travelCost: terrain.map(t => TRAVEL_COST[t]),
        vaultSlots: [],
        locations: [],
        roads: [],
        roadMask,
        origin: { x: 0, y: 0 },
        anchorDiagnostics: [],
        validation: {
          totalVaults: 0,
          reachableVaults: 0,
          unreachableVaultIds: [],
          vaultsWithNearbyScavenge: 0,
          isolatedRegions: 0,
          valuableByRegion: {},
        },
      }
    }

    it('lowers the cost and pulls the route onto the road when enabled', () => {
      const world = twoRow(true)
      const plain = findPath(world, { x: 0, y: 0 }, { x: 5, y: 0 })
      const discounted = findPath(world, { x: 0, y: 0 }, { x: 5, y: 0 }, { roadDiscount: ROAD_TRAVEL_DISCOUNT })
      expect(plain).not.toBeNull()
      expect(discounted).not.toBeNull()
      expect(discounted!.cost).toBeLessThan(plain!.cost)
      expect(discounted!.path.some(p => p.y === 1)).toBe(true)
    })

    it('leaves the cost unchanged when no road tile is on the route', () => {
      const world = twoRow(false)
      const plain = findPath(world, { x: 0, y: 0 }, { x: 5, y: 0 })
      const discounted = findPath(world, { x: 0, y: 0 }, { x: 5, y: 0 }, { roadDiscount: ROAD_TRAVEL_DISCOUNT })
      expect(discounted!.cost).toBeCloseTo(plain!.cost)
    })
  })

  describe('anchored geography (Option A)', () => {
    function wet(): TerrainType[] {
      return ['water', 'water', 'wasteland', 'water', 'water']
    }

    it('moves an anchor onto passable ground and reports the count', () => {
      const terrain = wet()
      const adjusted = constrainTerrainToAnchors(terrain, 5, 1, [
        { x: 0, y: 0 },
        { x: 2, y: 0 },
      ])
      expect(adjusted).toBe(1)
      expect(terrain[0]).not.toBe('water')
      expect(terrain[2]).toBe('wasteland')
    })

    it('is deterministic for the same input', () => {
      const a = wet()
      const b = wet()
      constrainTerrainToAnchors(a, 5, 1, [{ x: 0, y: 0 }])
      constrainTerrainToAnchors(b, 5, 1, [{ x: 0, y: 0 }])
      expect(a).toEqual(b)
    })

    it('leaves every generated location and vault on passable terrain', () => {
      for (const seed of ['vault-111', 'alpha', 'beta']) {
        const world = generateWorld({ seed })
        const anchors = [...world.locations, ...world.vaultSlots.map(v => ({ x: v.x, y: v.y }))]
        for (const anchor of anchors) {
          expect(
            world.terrain[anchor.y * world.config.width + anchor.x],
            `${seed} @ ${anchor.x},${anchor.y}`,
          ).not.toBe('water')
        }
      }
    })

    it('constrains terrain for the synthetic shared fixtures', () => {
      const world = generateWorld(undefined, SHARED_ANCHOR_FIXTURES)
      expect(world.anchorDiagnostics).toHaveLength(SHARED_ANCHOR_FIXTURES.length)
      expect(world.anchorDiagnostics.filter(d => d.conflict !== null)).toHaveLength(1)
      for (const d of world.anchorDiagnostics) {
        expect(d.before).not.toBeNull()
        expect(d.reachable, d.anchor.id).toBe(true)
        if (d.conflict === null) expect(d.after).toBe(d.anchor.terrain)
      }
    })

    it('merges real public anchors through the same constraint pass', () => {
      const real: TerrainAnchor[] = [
        { id: 'seed-0', name: 'Seeded signal', coord_x: 50, coord_y: 50, terrain: 'wasteland' },
      ]
      const world = generateWorld(undefined, [...SHARED_ANCHOR_FIXTURES, ...real])
      expect(world.anchorDiagnostics).toHaveLength(SHARED_ANCHOR_FIXTURES.length + 1)
      expect(world.anchorDiagnostics.map(d => d.anchor.id)).toContain('seed-0')
    })

    it('is deterministic for the same seed and fixtures', () => {
      const a = generateWorld({ seed: 'alpha' }, SHARED_ANCHOR_FIXTURES)
      const b = generateWorld({ seed: 'alpha' }, SHARED_ANCHOR_FIXTURES)
      expect(a.terrain).toEqual(b.terrain)
      expect(a.anchorDiagnostics).toEqual(b.anchorDiagnostics)
    })

    it('exposes the constraint version', () => {
      expect(ANCHOR_CONSTRAINT_VERSION).toBe(1)
    })
  })

  it('keeps every vault reachable across many seeds', () => {
    for (const seed of ['alpha', 'beta', 'gamma', 'delta', 'epsilon']) {
      const world = generateWorld({ seed })
      expect(world.validation.reachableVaults, `seed ${seed}`).toBe(world.validation.totalVaults)
      expect(world.validation.unreachableVaultIds, `seed ${seed}`).toEqual([])
    }
  })

  it('keeps water as a few large bodies spanning the map, not shattered speckle', () => {
    for (const seed of ['vault-111', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']) {
      const world = generateWorld({ seed })
      const water = componentSizes(world.terrain, WIDTH, HEIGHT, 'water')
      const largest = water[0] ?? 0
      // Shared bridges segment the river into a few large bodies, never confetti.
      expect(water.length, `seed ${seed}`).toBeLessThanOrEqual(8)
      expect(largest, `seed ${seed}`).toBeGreaterThanOrEqual(80)
      const bbox = largestComponentBBox(world.terrain, WIDTH, HEIGHT, 'water')
      expect(bbox, `seed ${seed}`).not.toBeNull()
      if (bbox !== null) {
        const spanX = bbox.maxX - bbox.minX + 1
        const spanY = bbox.maxY - bbox.minY + 1
        // Regional terrain gives a smaller lake, so the largest body is often a
        // long river segment split off by a road bridge; it still spans a good
        // fraction of the map in one dimension.
        expect(Math.max(spanX / WIDTH, spanY / HEIGHT), `seed ${seed}`).toBeGreaterThanOrEqual(0.15)
      }
    }
  })

  it('keeps hills and ruins as a few large regions, not per-tile speckle', () => {
    for (const seed of ['vault-111', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']) {
      const world = generateWorld({ seed })
      const counts: Record<TerrainType, number> = { wasteland: 0, forest: 0, ruins: 0, hills: 0, water: 0 }
      for (const t of world.terrain) counts[t]++
      for (const kind of ['hills', 'ruins'] as const) {
        const comps = componentSizes(world.terrain, WIDTH, HEIGHT, kind)
        // A bounded small number of regions — the consolidated plan plus river
        // splits (which can add a couple of components)... never a scatter.
        expect(comps.length, `seed ${seed} ${kind}`).toBeLessThanOrEqual(8)
        // ...with a largest region that is both a real mass and a meaningful
        // share of the biome's own tiles (not scattered single tiles).
        expect(comps[0] ?? 0, `seed ${seed} ${kind}`).toBeGreaterThanOrEqual(120)
        expect(comps[0] ?? 0, `seed ${seed} ${kind}`).toBeGreaterThanOrEqual(counts[kind] * 0.05)
      }
    }
  })

  it('gives forest a travel cost of 1.15 and a road cost between wasteland and ruins', () => {
    expect(TRAVEL_COST.forest).toBe(1.15)
    expect(TRAVEL_COST.forest).toBeGreaterThan(TRAVEL_COST.wasteland)
    expect(TRAVEL_COST.forest).toBeLessThan(TRAVEL_COST.ruins)
    expect(ROAD_COST.forest).toBeGreaterThan(ROAD_COST.wasteland)
    expect(ROAD_COST.forest).toBeLessThan(ROAD_COST.ruins)
  })

  it('keeps forest as a few large groves, not per-tile speckle', () => {
    for (const seed of ['vault-111', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']) {
      const world = generateWorld({ seed })
      const counts: Record<TerrainType, number> = { wasteland: 0, forest: 0, ruins: 0, hills: 0, water: 0 }
      for (const t of world.terrain) counts[t]++
      const comps = componentSizes(world.terrain, WIDTH, HEIGHT, 'forest')
      // A bounded small number of groves (region plan + river splits)...
      expect(comps.length, `seed ${seed}`).toBeLessThanOrEqual(8)
      // ...with a largest grove that is a real mass and a meaningful share of
      // the forest's own tiles (not scattered single tiles).
      expect(comps[0] ?? 0, `seed ${seed}`).toBeGreaterThanOrEqual(120)
      expect(comps[0] ?? 0, `seed ${seed}`).toBeGreaterThanOrEqual(counts.forest * 0.05)
    }
  })

  it('forms large contiguous biome regions over large wasteland voids, deterministically', () => {
    const assertRegionGoal = (world: ReturnType<typeof generateWorld>): void => {
      const counts: Record<TerrainType, number> = { wasteland: 0, forest: 0, ruins: 0, hills: 0, water: 0 }
      for (const t of world.terrain) counts[t]++
      // Region goal: every non-wasteland biome is a handful of large contiguous
      // masses — at most ~8 components, with the largest a substantial share of
      // that biome's own tiles. This is the direct component-size statement of
      // the region-first generator.
      for (const kind of ['forest', 'hills', 'ruins', 'water'] as const) {
        const comps = componentSizes(world.terrain, world.config.width, world.config.height, kind)
        expect(comps.length, `${kind}`).toBeLessThanOrEqual(8)
        expect(comps[0] ?? 0, `${kind}`).toBeGreaterThanOrEqual(counts[kind] * 0.05)
      }
      // Wasteland forms the largest contiguous mass: bigger than every other
      // biome's largest region, and a large share of the wasteland itself.
      const wastelandComps = componentSizes(world.terrain, world.config.width, world.config.height, 'wasteland')
      const wastelandLargest = wastelandComps[0] ?? 0
      expect(wastelandLargest).toBeGreaterThanOrEqual(counts.wasteland * 0.25)
      for (const kind of ['forest', 'hills', 'ruins', 'water'] as const) {
        const otherLargest = componentSizes(world.terrain, world.config.width, world.config.height, kind)[0] ?? 0
        expect(wastelandLargest, `wasteland > ${kind}`).toBeGreaterThan(otherLargest)
      }
    }
    for (const seed of ['vault-111', 'alpha', 'beta', 'gamma', 'delta', 'epsilon']) {
      assertRegionGoal(generateWorld({ seed }))
      // Stable across locationCount: downstream routing re-carves a few bridge
      // tiles, so terrain is not byte-identical, but the region structure must
      // hold at a different count too.
      assertRegionGoal(generateWorld({ seed, locationCount: 60 }))
    }
    // Determinism is part of the region contract: the same seed + config is
    // byte-identical, terrain included.
    const stable = generateWorld()
    expect(generateWorld().terrain).toEqual(stable.terrain)
  })

  it('keeps forest a modest share with wasteland dominant and water low', () => {
    for (const seed of ['vault-111', 'alpha']) {
      const world = generateWorld({ seed })
      const counts: Record<TerrainType, number> = { wasteland: 0, forest: 0, ruins: 0, hills: 0, water: 0 }
      for (const t of world.terrain) counts[t]++
      const total = world.terrain.length
      const forestShare = counts.forest / total
      expect(forestShare, `seed ${seed}`).toBeGreaterThanOrEqual(0.05)
      // Regional forest is a few large masses, so the share runs higher than the
      // old scattered groves; wasteland still dominates by a wide margin.
      expect(forestShare, `seed ${seed}`).toBeLessThanOrEqual(0.16)
      expect(counts.wasteland, `seed ${seed}`).toBeGreaterThan(counts.forest)
      expect(counts.water / total, `seed ${seed}`).toBeLessThan(0.15)
    }
  })
})