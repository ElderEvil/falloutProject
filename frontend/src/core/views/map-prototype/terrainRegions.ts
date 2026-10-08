/**
 * terrainRegions.ts — pure terrain-mask → smoothed region polygons.
 *
 * The tile grid stays the source of truth for logic (slots, roads, rivers,
 * reachability); this module only derives the *rendering* geometry. For each
 * terrain kind it finds the 4-connected components, traces every component
 * boundary as closed rings (directed cell-edge following with the component on
 * the left), simplifies the tile staircase with Douglas–Peucker and rounds it
 * with Chaikin corner cutting, so biomes render as large organic regions
 * instead of per-tile colour fills.
 *
 * Coordinates are in tile/wire units on the cell-edge lattice: tile `(x, y)`
 * spans `[x, x+1] × [y, y+1]`, so the canvas position is `point * TILE`.
 * Rings are explicitly closed — the last point repeats the first — and holes
 * wind opposite to their outer ring, so one non-zero fill punches holes.
 *
 * Deterministic: no randomness, no DOM, no framework imports (the only import
 * is the shared `TerrainType` union).
 */
import type { TerrainType } from '@/modules/map/utils/atlasWorldgen'

export interface RegionPoint {
  x: number
  y: number
}

export interface TerrainRegion {
  terrain: TerrainType
  rings: RegionPoint[][]
}

/**
 * Extraction/draw order: wasteland first (drawn as the map base), water last so
 * rivers and lakes sit on top of the land they cut through.
 */
const REGION_ORDER: readonly TerrainType[] = ['wasteland', 'forest', 'ruins', 'hills', 'water']

// Douglas–Peucker tolerance (tiles) and Chaikin passes that turn the traced
// tile staircase into organic curves without dissolving real coastline.
const SIMPLIFY_TOLERANCE = 1
const SMOOTHING_PASSES = 2
// Cap simplified edge length before Chaikin, otherwise a corner between two long
// straight edges is rounded by a quarter of their length instead of a half tile.
const MAX_EDGE_LENGTH = 2

// Screen-space directions (y grows downward), clockwise: east, south, west, north.
const DIR_EAST = 0
const DIR_SOUTH = 1
const DIR_WEST = 2
const DIR_NORTH = 3

interface BoundaryEdge {
  from: number
  to: number
  dir: number
  visited: boolean
}

export function extractTerrainRegions(
  terrain: readonly TerrainType[],
  width: number,
  height: number,
): TerrainRegion[] {
  if (terrain.length !== width * height) {
    throw new Error(`extractTerrainRegions: terrain length ${terrain.length} does not match ${width}×${height}`)
  }
  const regions: TerrainRegion[] = []
  const visited = new Uint8Array(terrain.length)
  for (const kind of REGION_ORDER) {
    for (let index = 0; index < terrain.length; index++) {
      if (terrain[index] !== kind || visited[index] === 1) continue
      const cells = collectComponent(terrain, width, height, index, kind, visited)
      const rings = traceRings(cells, terrain, width, height, kind)
        .map(ring => smoothRing(ring))
        .filter(ring => ring.length >= 3)
      if (rings.length > 0) regions.push({ terrain: kind, rings })
    }
  }
  return regions
}

/** 4-connected flood fill over the same-terrain mask, in deterministic scan order. */
function collectComponent(
  terrain: readonly TerrainType[],
  width: number,
  height: number,
  start: number,
  kind: TerrainType,
  visited: Uint8Array,
): number[] {
  const stack: number[] = [start]
  visited[start] = 1
  const cells: number[] = []
  while (stack.length > 0) {
    const index = stack.pop()
    if (index === undefined) break
    cells.push(index)
    const x = index % width
    const y = (index - x) / width
    if (y > 0) pushNeighbor(terrain, visited, stack, index - width, kind)
    if (y < height - 1) pushNeighbor(terrain, visited, stack, index + width, kind)
    if (x > 0) pushNeighbor(terrain, visited, stack, index - 1, kind)
    if (x < width - 1) pushNeighbor(terrain, visited, stack, index + 1, kind)
  }
  return cells
}

function pushNeighbor(
  terrain: readonly TerrainType[],
  visited: Uint8Array,
  stack: number[],
  index: number,
  kind: TerrainType,
): void {
  if (visited[index] === 1 || terrain[index] !== kind) return
  visited[index] = 1
  stack.push(index)
}

/**
 * Trace every boundary ring of one component. Each cell edge facing a
 * non-component tile becomes a directed edge with the component on its left;
 * outer rings and holes therefore wind in opposite directions, and a single
 * non-zero fill punches holes correctly.
 */
function traceRings(
  cells: readonly number[],
  terrain: readonly TerrainType[],
  width: number,
  height: number,
  kind: TerrainType,
): RegionPoint[][] {
  const stride = width + 1
  const outgoing: BoundaryEdge[][] = Array.from({ length: stride * (height + 1) }, () => [])
  const edges: BoundaryEdge[] = []
  const register = (from: number, to: number, dir: number): void => {
    const edge: BoundaryEdge = { from, to, dir, visited: false }
    edges.push(edge)
    outgoing[from]?.push(edge)
  }
  for (const index of cells) {
    const x = index % width
    const y = (index - x) / width
    if (y === 0 || terrain[index - width] !== kind) {
      register(y * stride + x, y * stride + x + 1, DIR_EAST)
    }
    if (x === width - 1 || terrain[index + 1] !== kind) {
      register(y * stride + x + 1, (y + 1) * stride + x + 1, DIR_SOUTH)
    }
    if (y === height - 1 || terrain[index + width] !== kind) {
      register((y + 1) * stride + x + 1, (y + 1) * stride + x, DIR_WEST)
    }
    if (x === 0 || terrain[index - 1] !== kind) {
      register((y + 1) * stride + x, y * stride + x, DIR_NORTH)
    }
  }

  const rings: RegionPoint[][] = []
  const pointAt = (vertex: number): RegionPoint => {
    const x = vertex % stride
    return { x, y: (vertex - x) / stride }
  }
  for (const first of edges) {
    if (first.visited) continue
    first.visited = true
    const ring: number[] = [first.from]
    let edge = first
    let closed = false
    for (;;) {
      if (edge.to === first.from) {
        closed = true
        break
      }
      ring.push(edge.to)
      const next = pickNextEdge(outgoing[edge.to], edge.dir)
      if (next === null) break
      next.visited = true
      edge = next
    }
    if (!closed || ring.length < 3) continue
    rings.push(ring.map(pointAt))
  }
  return rings
}

/**
 * Rightmost-turn pairing at a vertex: among the unvisited outgoing edges,
 * take the one that turns most clockwise from the incoming direction. This is
 * the 4-connectivity convention, so diagonally touching cells never merge.
 */
function pickNextEdge(candidates: readonly BoundaryEdge[], incoming: number): BoundaryEdge | null {
  let best: BoundaryEdge | null = null
  let bestTurn = 5
  for (const candidate of candidates) {
    if (candidate.visited) continue
    const turn = (candidate.dir - incoming + 4) % 4
    if (turn < bestTurn) {
      bestTurn = turn
      best = candidate
    }
  }
  return best
}

/** Simplify the traced staircase, bound the edge lengths, then round the corners. */
function smoothRing(ring: readonly RegionPoint[]): RegionPoint[] {
  const simplified = simplifyRing(ring, SIMPLIFY_TOLERANCE)
  const subdivided = subdivideRing(simplified, MAX_EDGE_LENGTH)
  const smoothed = smoothCorners(subdivided, SMOOTHING_PASSES)
  const first = smoothed[0]
  if (first === undefined) return []
  return [...smoothed, { x: first.x, y: first.y }]
}

/** Insert points so no edge exceeds `maxLength`, keeping Chaikin local. */
function subdivideRing(ring: readonly RegionPoint[], maxLength: number): RegionPoint[] {
  const out: RegionPoint[] = []
  for (let i = 0; i < ring.length; i++) {
    const from = ring[i]
    const to = ring[(i + 1) % ring.length]
    if (from === undefined || to === undefined) continue
    out.push(from)
    const steps = Math.max(1, Math.ceil(Math.hypot(to.x - from.x, to.y - from.y) / maxLength))
    for (let step = 1; step < steps; step++) {
      const t = step / steps
      out.push({ x: from.x + (to.x - from.x) * t, y: from.y + (to.y - from.y) * t })
    }
  }
  return out
}

/**
 * Cyclic Douglas–Peucker: anchor the ring on its first point and the point
 * farthest from it, simplify both halves, and stitch them back together.
 */
function simplifyRing(ring: readonly RegionPoint[], tolerance: number): RegionPoint[] {
  if (ring.length <= 4) return [...ring]
  const first = ring[0]
  if (first === undefined) return []
  let farIndex = 0
  let farDistance = -1
  for (let i = 1; i < ring.length; i++) {
    const point = ring[i]
    if (point === undefined) continue
    const distance = (point.x - first.x) ** 2 + (point.y - first.y) ** 2
    if (distance > farDistance) {
      farDistance = distance
      farIndex = i
    }
  }
  if (farIndex === 0) return [...ring]
  const head = simplifyPolyline(ring.slice(0, farIndex + 1), tolerance)
  const tail = simplifyPolyline([...ring.slice(farIndex), first], tolerance)
  return [...head.slice(0, -1), ...tail.slice(0, -1)]
}

function simplifyPolyline(points: readonly RegionPoint[], tolerance: number): RegionPoint[] {
  if (points.length <= 2) return [...points]
  const keep = new Uint8Array(points.length)
  keep[0] = 1
  keep[points.length - 1] = 1
  const stack: Array<[number, number]> = [[0, points.length - 1]]
  while (stack.length > 0) {
    const range = stack.pop()
    if (range === undefined) break
    const [start, end] = range
    const from = points[start]
    const to = points[end]
    if (from === undefined || to === undefined) continue
    let maxDistance = -1
    let maxIndex = -1
    for (let i = start + 1; i < end; i++) {
      const point = points[i]
      if (point === undefined) continue
      const distance = perpendicularDistance(point, from, to)
      if (distance > maxDistance) {
        maxDistance = distance
        maxIndex = i
      }
    }
    if (maxIndex !== -1 && maxDistance > tolerance) {
      keep[maxIndex] = 1
      stack.push([start, maxIndex], [maxIndex, end])
    }
  }
  const simplified: RegionPoint[] = []
  for (let i = 0; i < points.length; i++) {
    const point = points[i]
    if (keep[i] === 1 && point !== undefined) simplified.push(point)
  }
  return simplified
}

function perpendicularDistance(point: RegionPoint, start: RegionPoint, end: RegionPoint): number {
  const dx = end.x - start.x
  const dy = end.y - start.y
  const length = Math.hypot(dx, dy)
  if (length === 0) return Math.hypot(point.x - start.x, point.y - start.y)
  return Math.abs(dy * (point.x - start.x) - dx * (point.y - start.y)) / length
}

/** One Chaikin corner-cutting pass replaces each edge with the two points at 1/4 and 3/4. */
function smoothCorners(ring: readonly RegionPoint[], passes: number): RegionPoint[] {
  let current: RegionPoint[] = [...ring]
  for (let pass = 0; pass < passes; pass++) {
    if (current.length < 3) return current
    const next: RegionPoint[] = []
    for (let i = 0; i < current.length; i++) {
      const from = current[i]
      const to = current[(i + 1) % current.length]
      if (from === undefined || to === undefined) continue
      next.push({ x: from.x * 0.75 + to.x * 0.25, y: from.y * 0.75 + to.y * 0.25 })
      next.push({ x: from.x * 0.25 + to.x * 0.75, y: from.y * 0.25 + to.y * 0.75 })
    }
    current = next
  }
  return current
}
