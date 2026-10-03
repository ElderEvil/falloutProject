/**
 * Deterministic overworld generator — shared atlas geography.
 *
 * Pure, framework-free TypeScript. No Math.random(), no Date.now(), no crypto,
 * no network, no storage. Every random decision is derived from a stable hash
 * of `"${version}:${seed}:${namespace}"` fed into a mulberry32 PRNG, so the
 * same seed + config always produces a byte-identical GeneratedWorld.
 *
 * Shared by the DEV prototype and the production map: the geography is seeded
 * from a fixed world seed and anchored to the shared public anchors (seeded
 * vault signals), so every vault sees the same biomes, rivers, and roads.
 *
 * Pipeline:
 *   1. three normalized fbm fields → 5 terrain classes (wasteland / ruins /
 *      hills / forest / water); a low-frequency base field gives broad
 *      land/water and coherent hill peaks, a separate field gives coherent
 *      ruined fields, a third low-frequency field gives a few forest groves
 *   2. seeded random-walk rivers carve water
 *   3. one vault slot per sector (snapped off water, spacing-nudged)
 *   4. settlement clusters (biased toward ruined fields) + archetype-placed
 *      locations
 *   5. Prim MST + loop edges, A*-routed into roads through seeded curved
 *      waypoints (water crossings become bridge tiles)
 *   6. red_rocket at road junctions, raider camps away from roads
 *   7. vault access paths to the road network
 *   8. reachability repair — every vault is guaranteed reachable from origin
 *   9. scavenge guarantee — every vault gets a routed supply cache within
 *      VAULT_SCAVENGE_BUDGET (caches are an overlay, not part of locationCount)
 *  10. validation report
 */

// ── Tunable constants ──────────────────────────────────────────────────
// Grouped here so a human can visually tune the generator.

export const HOURS_PER_COST = 0.5 // hours = round(cost * HOURS_PER_COST)

// Noise / terrain
// Two independent fbm fields, each min/max-normalized per map so the terrain
// composition is stable across seeds. Thresholds are quantiles of the map's
// own range: the fields are low-frequency (smooth), so the selected cores read
// as a few coherent regions rather than per-tile speckle.
const NOISE_OCTAVES = 4
const NOISE_FREQUENCY = 0.03 // base field — broad hill cores
const NOISE_LACUNARITY = 2.0
const NOISE_GAIN = 0.5
const WATER_QUANTILE = 0.02 // bottom 2% of base field → a couple of small lakes
const HILLS_QUANTILE = 0.17 // top 17% of base field → hill cores
const RUINS_FREQUENCY = 0.022 // separate field — ruins form coherent fields
const RUINS_QUANTILE = 0.17 // top 17% of ruins field → ruin cores
const FOREST_FREQUENCY = 0.02 // separate field — forest forms a few broad groves
const FOREST_QUANTILE = 0.14 // top 14% of forest field (over wasteland) → groves
const MIN_REGION_COMPONENT = 40 // hills/ruins components below this are speckle → wasteland
const FOREST_MIN_COMPONENT = 40 // forest components below this are speckle → wasteland
const WATER_MIN_COMPONENT = 20 // water components below this are speckle → wasteland

// Rivers
const RIVER_COUNT = 1 // a single meandering river reads as one waterway
const RIVER_WIDTH = 3 // narrow 3-tile channel — shared 5x5 bridge plugs provably span it
const RIVER_MAX_STEPS = 160 // jittered-walk cap; a straight finish guarantees the target edge
const RIVER_JITTER = 0.6 // ±0.3 rad ≈ ±17° — gentle meander that stays on course

// Vault slots
const SECTOR_OFFSET_MAX = 2 // max seeded offset from sector center (tiles)
const VAULT_SNAP_RADIUS = 4 // search radius to snap off water
const DRY_PATCH_RADIUS = 1 // deterministic dry patch around a water vault
const VAULT_MIN_SPACING = 4 // min distance between vault slots (tiles)
const VAULT_SPACING_ATTEMPTS = 8
const VAULT_SPACING_NUDGE = 4

// Locations
const CLUSTER_MIN_DIST = 14 // max min distance between settlement clusters (scaled down for dense maps)
const CLUSTER_MIN_DIST_FLOOR = 6 // floor for dense maps
const CLUSTER_ATTEMPTS = 40
const LOCATION_MIN_SPACING = 3 // min distance between non-settlement locations (tiles)
const LOCATION_PLACEMENT_ATTEMPTS = 64 // bounded rejection-sampling attempts per location
const MART_CLUSTER_RADIUS = 9 // super_duper_mart scatter around a cluster
const FACTORY_EDGE_MIN = 3 // abandoned_factory ring offset from a settlement cluster
const FACTORY_EDGE_MAX = 7
const SETTLEMENT_RUINS_RADIUS = 10 // settlements prefer wasteland near ruined fields
const LOCATION_SNAP_RADIUS = 4

// Roads
const ROAD_EXTRA_EDGE_RATIO = 0.14 // extra MST edges to create loops (curved edges cover more ground)
const ROAD_CURVE_OFFSET = 0.18 // max perpendicular waypoint offset as a fraction of edge length
const ROAD_CURVE_LONG_EDGE = 10 // edges at/above this chord length get 2 waypoints, shorter get 1
const ROAD_CURVE_SNAP_RADIUS = 6 // waypoint snap search radius (Chebyshev rings)
const JUNCTION_RADIUS = 3 // red_rocket pool: road tiles near degree-≥3 junctions
const WATER_CROSSING_COST = 250 // water crossings are costly — roads reuse existing bridges
const LINE_SAMPLE_STEP = 4 // tiles between samples for MST edge weights
const WATER_SAMPLE_COST = 250 // spanning water is costly — the MST crosses minimally

// Raider camps
const RAIDER_ROAD_DISTANCE = 8 // min distance from any road tile

// Scavenge guarantee
const VAULT_SCAVENGE_BUDGET = 6 // routed travel-cost budget ≈ 3h at HOURS_PER_COST
const VAULT_CACHE_RADIUS = 3 // cache placed within this many BFS hops of its vault
const VAULT_CACHE_FALLBACK_RADIUS = 8 // spacing relaxed beyond this if needed
const SUPPLY_CACHE_NAMES = ['Supply Cache', 'Abandoned House', 'Wrecked Caravan', 'Scavenger Den', 'Ranger Post'] as const

// Validation
const MIN_REGION_SIZE = 20 // passable regions above this size count as isolated
const REGION_BUCKETS = 4 // 4x4 buckets for valuable-site distribution

// ── Public types & constants ───────────────────────────────────────────

export type TerrainType = 'wasteland' | 'forest' | 'ruins' | 'hills' | 'water'

export const TRAVEL_COST: Record<TerrainType, number> = {
  wasteland: 1.0,
  forest: 1.15,
  ruins: 1.3,
  hills: 1.5,
  water: Infinity,
}

/** Internal cost table used when routing roads (water passable at a price). */
export const ROAD_COST: Record<TerrainType, number> = {
  wasteland: 0.7,
  forest: 0.8,
  ruins: 0.9,
  hills: 1.1,
  water: WATER_CROSSING_COST,
}

export interface WorldGenConfig {
  seed: string
  width: number
  height: number
  sectorCols: number
  sectorRows: number
  locationCount: number
  version: number
}

export const DEFAULT_WORLD_CONFIG: WorldGenConfig = {
  seed: 'vault-111',
  width: 80,
  height: 80,
  sectorCols: 10,
  sectorRows: 10,
  locationCount: 100,
  version: 1,
}

export interface VaultSlot {
  id: number
  x: number
  y: number
  sectorCol: number
  sectorRow: number
  claimed: boolean
}

export type LocationKind =
  | 'red_rocket'
  | 'super_duper_mart'
  | 'abandoned_factory'
  | 'radio_tower'
  | 'water_treatment'
  | 'raider_camp'
  | 'settlement'
  | 'supply_cache'

export interface MapLocation {
  id: number
  name: string
  kind: LocationKind
  x: number
  y: number
}

export interface RoadEdge {
  from: number
  to: number
  path: Array<{ x: number; y: number }>
  length: number
  /** Seeded interior waypoints the path was routed through (the curvature). */
  waypoints: Array<{ x: number; y: number }>
}

export interface ValidationReport {
  totalVaults: number
  reachableVaults: number
  unreachableVaultIds: number[]
  vaultsWithNearbyScavenge: number
  isolatedRegions: number
  valuableByRegion: Record<string, number>
}

export const ANCHOR_CONSTRAINT_VERSION = 1
export const SHARED_FIXTURE_VERSION = 'synthetic-public-v1'

export interface TerrainAnchor {
  id: string
  name: string
  coord_x: number
  coord_y: number
  terrain: Exclude<TerrainType, 'water'>
}

/** Deliberately synthetic shared geography; never sourced from vault discovery. */
export const SHARED_ANCHOR_FIXTURES: readonly TerrainAnchor[] = [
  { id: 'fixture-town', name: 'Synthetic settlement', coord_x: 22.375, coord_y: 31.125, terrain: 'ruins' },
  { id: 'fixture-tower', name: 'Synthetic hill tower', coord_x: 64.625, coord_y: 18.875, terrain: 'hills' },
  { id: 'fixture-vault', name: 'Synthetic vault signal', coord_x: 47.25, coord_y: 73.125, terrain: 'wasteland' },
  { id: 'fixture-conflict', name: 'Synthetic co-cell conflict', coord_x: 22.4, coord_y: 31.2, terrain: 'hills' },
]

export interface AnchorDiagnostic {
  anchor: TerrainAnchor
  x: number
  y: number
  before: TerrainType | null
  after: TerrainType | null
  conflict: string | null
  reachable: boolean
}

export interface GeneratedWorld {
  config: WorldGenConfig
  terrain: TerrainType[]
  travelCost: number[]
  vaultSlots: VaultSlot[]
  locations: MapLocation[]
  roads: RoadEdge[]
  roadMask: Uint8Array
  origin: { x: number; y: number }
  validation: ValidationReport
  anchorDiagnostics: AnchorDiagnostic[]
}

// ── Seeded RNG ─────────────────────────────────────────────────────────

/** FNV-1a 32-bit string hash — stable across platforms. */
function hashString(str: string): number {
  let h = 0x811c9dc5
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i)
    h = Math.imul(h, 0x01000193)
  }
  return h >>> 0
}

/** mulberry32 PRNG (same approach as modules/map/utils/wastelandTerrain.ts). */
function mulberry32(seed: number): () => number {
  let s = seed | 0
  return () => {
    s = (s + 0x6d2b79f5) | 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/**
 * Independent RNG stream for a namespace. Separate streams mean adding a
 * location type never shifts vault positions, etc.
 */
function seededRng(seed: string, version: number, namespace: string): () => number {
  return mulberry32(hashString(`${version}:${seed}:${namespace}`))
}

// ── Value noise + fbm ──────────────────────────────────────────────────

/** Deterministic hash of an integer lattice point into [0, 1). */
function latticeHash(ix: number, iy: number, seed: number): number {
  let h = (seed ^ Math.imul(ix | 0, 0x27d4eb2d) ^ Math.imul(iy | 0, 0x165667b1)) >>> 0
  h = Math.imul(h ^ (h >>> 15), 0x85ebca6b)
  h = Math.imul(h ^ (h >>> 13), 0xc2b2ae35)
  return ((h ^ (h >>> 16)) >>> 0) / 4294967296
}

function smoothstep(t: number): number {
  return t * t * (3 - 2 * t)
}

function valueNoise(x: number, y: number, seed: number): number {
  const ix = Math.floor(x)
  const iy = Math.floor(y)
  const fx = x - ix
  const fy = y - iy
  const sx = smoothstep(fx)
  const sy = smoothstep(fy)
  const a = latticeHash(ix, iy, seed)
  const b = latticeHash(ix + 1, iy, seed)
  const c = latticeHash(ix, iy + 1, seed)
  const d = latticeHash(ix + 1, iy + 1, seed)
  return a + (b - a) * sx + (c - a) * sy + (a - b - c + d) * sx * sy
}

/** Fractal Brownian motion over value noise — broad coherent patches. */
function fbm(x: number, y: number, seed: number, frequency = NOISE_FREQUENCY): number {
  let value = 0
  let amp = 1
  let freq = frequency
  let norm = 0
  for (let o = 0; o < NOISE_OCTAVES; o++) {
    value += amp * valueNoise(x * freq, y * freq, seed + o * 1013)
    norm += amp
    amp *= NOISE_GAIN
    freq *= NOISE_LACUNARITY
  }
  return value / norm
}

/** Min/max-normalize a field to [0, 1] in place (stable thresholds per map). */
function normalizeInPlace(field: Float64Array): void {
  let lo = Infinity
  let hi = -Infinity
  for (let i = 0; i < field.length; i++) {
    if (field[i] < lo) lo = field[i]
    if (field[i] > hi) hi = field[i]
  }
  const span = hi - lo || 1
  for (let i = 0; i < field.length; i++) field[i] = (field[i] - lo) / span
}

/** Ascending-quantile value of a field — the cut that leaves ~q of tiles below it. */
function quantileValue(field: Float64Array, q: number): number {
  const sorted = Array.from(field).sort((a, b) => a - b)
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.floor(q * sorted.length)))
  return sorted[idx]
}

/** Convert 4-connected components of `kind` smaller than minSize to `replacement`. */
function filterSmallComponents(
  terrain: TerrainType[],
  width: number,
  height: number,
  kind: TerrainType,
  replacement: TerrainType,
  minSize: number,
): void {
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
      for (const [dx, dy] of ORTHO) {
        const nx = cx + dx
        const ny = cy + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const nIdx = ny * width + nx
        if (seen[nIdx] === 1 || terrain[nIdx] !== kind) continue
        seen[nIdx] = 1
        queue.push(nIdx)
      }
    }
    if (cells.length < minSize) {
      for (const c of cells) terrain[c] = replacement
    }
  }
}

// ── Small helpers ──────────────────────────────────────────────────────

const TERRAIN_KINDS: readonly TerrainType[] = ['wasteland', 'forest', 'ruins', 'hills', 'water']

/**
 * Experiment (contract DD3): road tiles cost less so the network is a real
 * travel benefit. Applied only when a caller opts in via `findPath` options.
 */
export const ROAD_TRAVEL_DISCOUNT = 0.7

/** Admissible A* heuristic floors (minimum effective per-tile cost). */
const TRAVEL_MIN_COST = Math.min(...TERRAIN_KINDS.map(kind => TRAVEL_COST[kind]))
const ROAD_MIN_COST = Math.min(...TERRAIN_KINDS.map(kind => ROAD_COST[kind]))

const ORTHO: ReadonlyArray<readonly [number, number]> = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
]

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

const ORTHO_NEIGHBORS: ReadonlyArray<readonly [number, number, boolean]> = [
  [1, 0, false],
  [-1, 0, false],
  [0, 1, false],
  [0, -1, false],
]

const SQRT2 = Math.SQRT2

function clamp(v: number, lo: number, hi: number): number {
  if (v < lo) return lo
  if (v > hi) return hi
  return v
}

function pad(n: number): string {
  return n < 10 ? `0${n}` : String(n)
}

function minDistTo(p: { x: number; y: number }, points: Array<{ x: number; y: number }>): number {
  let best = Infinity
  for (const q of points) {
    const d = Math.hypot(p.x - q.x, p.y - q.y)
    if (d < best) best = d
  }
  return best
}

// ── Terrain ────────────────────────────────────────────────────────────

function generateTerrain(width: number, height: number, seed: string, version: number): TerrainType[] {
  const noiseSeed = hashString(`${version}:${seed}:terrain`)
  const baseField = new Float64Array(width * height)
  const ruinsField = new Float64Array(width * height)
  const forestField = new Float64Array(width * height)
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      baseField[y * width + x] = fbm(x, y, noiseSeed)
      ruinsField[y * width + x] = fbm(x, y, noiseSeed + 777, RUINS_FREQUENCY)
      forestField[y * width + x] = fbm(x, y, noiseSeed + 1337, FOREST_FREQUENCY)
    }
  }
  normalizeInPlace(baseField)
  normalizeInPlace(ruinsField)
  normalizeInPlace(forestField)
  const waterCut = quantileValue(baseField, WATER_QUANTILE)
  const hillsCut = quantileValue(baseField, 1 - HILLS_QUANTILE)
  const ruinsCut = quantileValue(ruinsField, 1 - RUINS_QUANTILE)
  const terrain = Array.from({ length: width * height }, () => 'wasteland' as TerrainType)
  for (let i = 0; i < width * height; i++) {
    const b = baseField[i]
    const r = ruinsField[i]
    let t: TerrainType
    if (b < waterCut) t = 'water'
    else if (b > hillsCut) t = 'hills'
    else if (r > ruinsCut) t = 'ruins'
    else t = 'wasteland'
    terrain[i] = t
  }
  // Forest groves are carved from wasteland only. The cut is a quantile of the
  // forest field over wasteland tiles, so the grove share stays stable across
  // seeds instead of drifting with where the smooth patches happen to land.
  const forestValues = new Float64Array(width * height)
  let forestCount = 0
  for (let i = 0; i < width * height; i++) {
    if (terrain[i] === 'wasteland') forestValues[forestCount++] = forestField[i]
  }
  const forestCut = quantileValue(forestValues.subarray(0, forestCount), 1 - FOREST_QUANTILE)
  for (let i = 0; i < width * height; i++) {
    if (terrain[i] === 'wasteland' && forestField[i] > forestCut) terrain[i] = 'forest'
  }
  filterSmallComponents(terrain, width, height, 'hills', 'wasteland', MIN_REGION_COMPONENT)
  filterSmallComponents(terrain, width, height, 'ruins', 'wasteland', MIN_REGION_COMPONENT)
  filterSmallComponents(terrain, width, height, 'forest', 'wasteland', FOREST_MIN_COMPONENT)
  return terrain
}

// ── Rivers ─────────────────────────────────────────────────────────────

const EDGES = ['top', 'bottom', 'left', 'right'] as const
type Edge = (typeof EDGES)[number]

const ADJACENT_EDGES: Record<Edge, [Edge, Edge]> = {
  top: ['left', 'right'],
  bottom: ['left', 'right'],
  left: ['top', 'bottom'],
  right: ['top', 'bottom'],
}

function traceRivers(terrain: TerrainType[], width: number, height: number, seed: string, version: number): void {
  const rng = seededRng(seed, version, 'rivers')
  for (let r = 0; r < RIVER_COUNT; r++) {
    traceRiver(terrain, width, height, rng)
  }
}

function traceRiver(terrain: TerrainType[], width: number, height: number, rng: () => number): void {
  // Adjacent edges: the river bends across a corner instead of bisecting the
  // map, so land stays connected around its ends and roads detour around it
  // rather than bridging everywhere. Crossings that remain are short and rare.
  const startEdge = EDGES[Math.floor(rng() * EDGES.length)]
  const endEdge = ADJACENT_EDGES[startEdge][Math.floor(rng() * 2)]

  // Bias endpoints toward the middle of each edge so the river crosses the map
  // interior instead of hugging a corner.
  const edgePoint = (edge: Edge): number => {
    const span = edge === 'top' || edge === 'bottom' ? width : height
    return Math.floor(span * 0.2 + rng() * span * 0.6)
  }

  let x = 0
  let y = 0
  switch (startEdge) {
    case 'top':
      x = edgePoint(startEdge)
      y = 0
      break
    case 'bottom':
      x = edgePoint(startEdge)
      y = height - 1
      break
    case 'left':
      x = 0
      y = edgePoint(startEdge)
      break
    case 'right':
      x = width - 1
      y = edgePoint(startEdge)
      break
  }

  let tx = 0
  let ty = 0
  switch (endEdge) {
    case 'top':
      tx = edgePoint(endEdge)
      ty = 0
      break
    case 'bottom':
      tx = edgePoint(endEdge)
      ty = height - 1
      break
    case 'left':
      tx = 0
      ty = edgePoint(endEdge)
      break
    case 'right':
      tx = width - 1
      ty = edgePoint(endEdge)
      break
  }

  // Wander prologue: meander toward the interior first so the river is long and
  // winding even when the endpoints are close. Same stream, fully deterministic.
  const wanderSteps = 60
  const wanderCx = width / 2 + (rng() - 0.5) * width * 0.3
  const wanderCy = height / 2 + (rng() - 0.5) * height * 0.3
  for (let s = 0; s < wanderSteps; s++) {
    carve(terrain, width, height, x, y)
    const wdx = wanderCx - x
    const wdy = wanderCy - y
    const wlen = Math.hypot(wdx, wdy)
    if (wlen < 1) break
    const wnx = wdx / wlen
    const wny = wdy / wlen
    const wjit = (rng() - 0.5) * RIVER_JITTER * 2
    const wsx = wnx - wny * wjit
    const wsy = wny + wnx * wjit
    const wsl = Math.hypot(wsx, wsy)
    x = clamp(Math.round(x + (wsl > 0 ? wsx / wsl : 0)), 0, width - 1)
    y = clamp(Math.round(y + (wsl > 0 ? wsy / wsl : 0)), 0, height - 1)
  }

  if (Math.abs(x - tx) + Math.abs(y - ty) < 70) {
    if (endEdge === 'top' || endEdge === 'bottom') tx = width - 1 - tx
    else ty = height - 1 - ty
  }
  const maxSteps = Math.max(RIVER_MAX_STEPS, Math.ceil(Math.hypot(width, height) * 1.6))
  let steps = 0
  while (steps < maxSteps) {
    carve(terrain, width, height, x, y)
    if (onEdge(x, y, width, height, endEdge)) break
    const dx = tx - x
    const dy = ty - y
    const len = Math.hypot(dx, dy)
    const nx = len > 0 ? dx / len : 0
    const ny = len > 0 ? dy / len : 0
    const jitter = (rng() - 0.5) * RIVER_JITTER
    const sx = nx - ny * jitter
    const sy = ny + nx * jitter
    const sl = Math.hypot(sx, sy)
    x = clamp(Math.round(x + (sl > 0 ? sx / sl : 0)), 0, width - 1)
    y = clamp(Math.round(y + (sl > 0 ? sy / sl : 0)), 0, height - 1)
    steps++
  }
  // Guarantee the river terminates on the target edge: if the jittered walk ran
  // out of steps, finish with a straight march toward the end point.
  while (!onEdge(x, y, width, height, endEdge)) {
    carve(terrain, width, height, x, y)
    const dx = tx - x
    const dy = ty - y
    const len = Math.hypot(dx, dy)
    if (len === 0) break
    x = clamp(Math.round(x + dx / len), 0, width - 1)
    y = clamp(Math.round(y + dy / len), 0, height - 1)
  }
}

function carve(terrain: TerrainType[], width: number, height: number, x: number, y: number): void {
  const half = Math.floor(RIVER_WIDTH / 2)
  for (let dy = -half; dy <= half; dy++) {
    for (let dx = -half; dx <= half; dx++) {
      const nx = x + dx
      const ny = y + dy
      if (nx >= 0 && nx < width && ny >= 0 && ny < height) terrain[ny * width + nx] = 'water'
    }
  }
}

function onEdge(x: number, y: number, width: number, height: number, edge: Edge): boolean {
  switch (edge) {
    case 'top':
      return y === 0
    case 'bottom':
      return y === height - 1
    case 'left':
      return x === 0
    case 'right':
      return x === width - 1
  }
}

// ── Tile helpers ───────────────────────────────────────────────────────

function buildTileLists(
  terrain: TerrainType[],
  width: number,
  height: number,
): { lists: Record<TerrainType, Array<{ x: number; y: number }>>; nonWater: Array<{ x: number; y: number }> } {
  const lists: Record<TerrainType, Array<{ x: number; y: number }>> = {
    wasteland: [],
    forest: [],
    ruins: [],
    hills: [],
    water: [],
  }
  const nonWater: Array<{ x: number; y: number }> = []
  for (let y = 0; y < height; y++) {
    for (let x = 0; x < width; x++) {
      const t = terrain[y * width + x]
      lists[t].push({ x, y })
      if (t !== 'water') nonWater.push({ x, y })
    }
  }
  return { lists, nonWater }
}

/** Nearest non-water tile within maxRadius (Chebyshev rings), else the input. */
function nearestNonWater(
  terrain: TerrainType[],
  width: number,
  height: number,
  x: number,
  y: number,
  x0: number,
  x1: number,
  y0: number,
  y1: number,
  maxRadius: number,
): { x: number; y: number } {
  if (terrain[y * width + x] !== 'water') return { x, y }
  for (let r = 1; r <= maxRadius; r++) {
    for (let dy = -r; dy <= r; dy++) {
      for (let dx = -r; dx <= r; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue
        const nx = x + dx
        const ny = y + dy
        if (nx < x0 || nx >= x1 || ny < y0 || ny >= y1) continue
        if (terrain[ny * width + nx] !== 'water') return { x: nx, y: ny }
      }
    }
  }
  return { x, y }
}

function dryPatch(terrain: TerrainType[], width: number, height: number, x: number, y: number, radius: number): void {
  for (let dy = -radius; dy <= radius; dy++) {
    for (let dx = -radius; dx <= radius; dx++) {
      const nx = x + dx
      const ny = y + dy
      if (nx >= 0 && nx < width && ny >= 0 && ny < height) {
        terrain[ny * width + nx] = 'wasteland'
      }
    }
  }
}

function adjacentNonWater(
  terrain: TerrainType[],
  width: number,
  height: number,
  x: number,
  y: number,
): { x: number; y: number } | null {
  for (const [dx, dy] of ORTHO) {
    const nx = x + dx
    const ny = y + dy
    if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
    if (terrain[ny * width + nx] !== 'water') return { x: nx, y: ny }
  }
  return null
}

// ── Vault slots ────────────────────────────────────────────────────────

function placeVaults(
  terrain: TerrainType[],
  width: number,
  height: number,
  sectorCols: number,
  sectorRows: number,
  seed: string,
  version: number,
): VaultSlot[] {
  const slots: VaultSlot[] = []
  let id = 0
  for (let row = 0; row < sectorRows; row++) {
    for (let col = 0; col < sectorCols; col++) {
      const rng = seededRng(seed, version, `vault:${row}:${col}`)
      const x0 = Math.floor((col * width) / sectorCols)
      const x1 = Math.floor(((col + 1) * width) / sectorCols)
      const y0 = Math.floor((row * height) / sectorRows)
      const y1 = Math.floor(((row + 1) * height) / sectorRows)
      const cx = (x0 + x1) / 2
      const cy = (y0 + y1) / 2
      let x = clamp(Math.round(cx + (rng() - 0.5) * 2 * SECTOR_OFFSET_MAX), x0, x1 - 1)
      let y = clamp(Math.round(cy + (rng() - 0.5) * 2 * SECTOR_OFFSET_MAX), y0, y1 - 1)
      const snapped = nearestNonWater(terrain, width, height, x, y, x0, x1, y0, y1, VAULT_SNAP_RADIUS)
      x = snapped.x
      y = snapped.y
      if (terrain[y * width + x] === 'water') {
        dryPatch(terrain, width, height, x, y, DRY_PATCH_RADIUS)
      }
      const placed = slots.map(s => ({ x: s.x, y: s.y }))
      if (minDistTo({ x, y }, placed) < VAULT_MIN_SPACING) {
        for (let attempt = 0; attempt < VAULT_SPACING_ATTEMPTS; attempt++) {
          const nx = clamp(x + Math.round((rng() - 0.5) * VAULT_SPACING_NUDGE), x0, x1 - 1)
          const ny = clamp(y + Math.round((rng() - 0.5) * VAULT_SPACING_NUDGE), y0, y1 - 1)
          const candidate = nearestNonWater(terrain, width, height, nx, ny, x0, x1, y0, y1, VAULT_SNAP_RADIUS)
          if (minDistTo(candidate, placed) >= VAULT_MIN_SPACING) {
            x = candidate.x
            y = candidate.y
            break
          }
        }
        // Fallback: keep the current position even if spacing is unmet — the
        // sector is too small to satisfy VAULT_MIN_SPACING.
      }
      slots.push({ id, x, y, sectorCol: col, sectorRow: row, claimed: false })
      id++
    }
  }
  return slots
}

// ── Locations ──────────────────────────────────────────────────────────

const LOCATION_KINDS: readonly LocationKind[] = [
  'settlement',
  'red_rocket',
  'super_duper_mart',
  'abandoned_factory',
  'radio_tower',
  'water_treatment',
  'raider_camp',
]

const LOCATION_WEIGHTS: Record<LocationKind, number> = {
  settlement: 6,
  red_rocket: 8,
  super_duper_mart: 7,
  abandoned_factory: 8,
  radio_tower: 7,
  water_treatment: 6,
  raider_camp: 8,
  supply_cache: 0, // guarantee overlay — never assigned by the density count
}

/** Kinds that participate in the road graph (raider camps stay off-road). */
const ROAD_GRAPH_KINDS: readonly LocationKind[] = [
  'settlement',
  'super_duper_mart',
  'abandoned_factory',
  'radio_tower',
  'water_treatment',
]

function computeLocationCounts(locationCount: number): Record<LocationKind, number> {
  const totalWeight = LOCATION_KINDS.reduce((sum, kind) => sum + LOCATION_WEIGHTS[kind], 0)
  const counts: Record<LocationKind, number> = {
    settlement: 0,
    red_rocket: 0,
    super_duper_mart: 0,
    abandoned_factory: 0,
    radio_tower: 0,
    water_treatment: 0,
    raider_camp: 0,
    supply_cache: 0,
  }
  let assigned = 0
  for (const kind of LOCATION_KINDS) {
    counts[kind] = Math.floor((locationCount * LOCATION_WEIGHTS[kind]) / totalWeight)
    assigned += counts[kind]
  }
  let i = 0
  while (assigned < locationCount) {
    const kind = LOCATION_KINDS[i % LOCATION_KINDS.length]
    counts[kind]++
    assigned++
    i++
  }
  return counts
}

// ── Location placement helpers ─────────────────────────────────────────

interface PlacementState {
  terrain: TerrainType[]
  width: number
  height: number
  occupied: Set<number>
  nonSettlement: Array<{ x: number; y: number }>
}

/** True when a tile is dry, not a vault slot, and (optionally) spaced from non-settlement locations. */
function isTileFree(state: PlacementState, p: { x: number; y: number }, minSpacing: number): boolean {
  const idx = p.y * state.width + p.x
  if (state.occupied.has(idx)) return false
  if (state.terrain[idx] === 'water') return false
  if (minSpacing > 0) {
    const minSq = minSpacing * minSpacing
    for (const q of state.nonSettlement) {
      const dx = p.x - q.x
      const dy = p.y - q.y
      if (dx * dx + dy * dy < minSq) return false
    }
  }
  return true
}

/** Deterministic Chebyshev-ring search for the nearest dry, unoccupied tile. */
function nearestFreeTile(
  state: PlacementState,
  x: number,
  y: number,
  maxRadius: number,
): { x: number; y: number } {
  const { terrain, width, height, occupied } = state
  if (isTileFree(state, { x, y }, 0)) return { x, y }
  for (let r = 1; r <= maxRadius; r++) {
    for (let dy = -r; dy <= r; dy++) {
      for (let dx = -r; dx <= r; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue
        const nx = x + dx
        const ny = y + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const idx = ny * width + nx
        if (terrain[idx] === 'water') continue
        if (occupied.has(idx)) continue
        return { x: nx, y: ny }
      }
    }
  }
  return { x, y }
}

/**
 * Bounded deterministic rejection sampling: draw candidates from the per-kind
 * RNG until one is dry, unoccupied and spaced, then snap it off water. On
 * exhaustion, fall back to the nearest free tile so the count is never dropped.
 */
function placeWithRejection(
  state: PlacementState,
  rng: () => number,
  generate: () => { x: number; y: number },
  minSpacing: number,
  maxAttempts: number,
): { x: number; y: number } {
  let last: { x: number; y: number } | null = null
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const raw = generate()
    const p = nearestNonWater(
      state.terrain,
      state.width,
      state.height,
      raw.x,
      raw.y,
      0,
      state.width,
      0,
      state.height,
      LOCATION_SNAP_RADIUS,
    )
    last = p
    if (isTileFree(state, p, minSpacing)) return p
  }
  return nearestFreeTile(state, last?.x ?? 0, last?.y ?? 0, Math.max(state.width, state.height))
}

/**
 * Scale settlement-cluster min distance with the requested count so dense maps
 * still fit: disk-packing estimate of the spacing a count of clusters needs on
 * the map, clamped to [CLUSTER_MIN_DIST_FLOOR, CLUSTER_MIN_DIST].
 */
function clusterMinDist(count: number, width: number, height: number): number {
  const area = width * height
  const d = Math.sqrt((area * 4) / (Math.max(1, count) * Math.PI))
  return clamp(Math.round(d * 0.8), CLUSTER_MIN_DIST_FLOOR, CLUSTER_MIN_DIST)
}

/** Multi-source BFS from ruins tiles over non-water tiles (distance per tile). */
function ruinsDistanceField(terrain: TerrainType[], width: number, height: number): Int32Array {
  const dist = new Int32Array(width * height).fill(-1)
  const queue: number[] = []
  for (let i = 0; i < terrain.length; i++) {
    if (terrain[i] === 'ruins') {
      dist[i] = 0
      queue.push(i)
    }
  }
  let head = 0
  while (head < queue.length) {
    const cur = queue[head]
    head++
    const cx = cur % width
    const cy = Math.floor(cur / width)
    for (const [dx, dy] of ORTHO) {
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
      const nIdx = ny * width + nx
      if (dist[nIdx] !== -1) continue
      if (terrain[nIdx] === 'water') continue
      dist[nIdx] = dist[cur] + 1
      queue.push(nIdx)
    }
  }
  return dist
}

function placeSettlements(
  terrain: TerrainType[],
  width: number,
  height: number,
  count: number,
  seed: string,
  version: number,
  occupied: Set<number>,
): Array<{ x: number; y: number }> {
  const rng = seededRng(seed, version, 'settlements')
  const clusters: Array<{ x: number; y: number }> = []
  const { lists, nonWater } = buildTileLists(terrain, width, height)
  const wastelandPool = lists.wasteland.filter(t => !occupied.has(t.y * width + t.x))
  const nonWaterPool = nonWater.filter(t => !occupied.has(t.y * width + t.x))
  const minDist = clusterMinDist(count, width, height)
  // Prefer wasteland near ruined fields so settlements cluster around the
  // recognizable ruined regions; fall back to all wasteland, then all
  // non-water, when the ruins-near pool cannot spread the clusters.
  const spreadArea = count * Math.PI * (minDist / 2) ** 2
  const ruinsDist = ruinsDistanceField(terrain, width, height)
  const ruinsNearPool = wastelandPool.filter(t => ruinsDist[t.y * width + t.x] <= SETTLEMENT_RUINS_RADIUS)
  const pool =
    ruinsNearPool.length >= spreadArea * 0.6
      ? ruinsNearPool
      : wastelandPool.length >= spreadArea * 0.6
        ? wastelandPool
        : nonWaterPool
  if (pool.length === 0) return clusters
  const attempts = Math.max(CLUSTER_ATTEMPTS, count * 2)
  for (let i = 0; i < count; i++) {
    let best = pool[Math.floor(rng() * pool.length)]
    let bestDist = minDistTo(best, clusters)
    for (let attempt = 0; attempt < attempts; attempt++) {
      const candidate = pool[Math.floor(rng() * pool.length)]
      const d = minDistTo(candidate, clusters)
      if (d >= minDist) {
        best = candidate
        bestDist = d
        break
      }
      if (d > bestDist) {
        bestDist = d
        best = candidate
      }
    }
    clusters.push(best)
  }
  return clusters
}

function placeLocations(
  terrain: TerrainType[],
  width: number,
  height: number,
  counts: Record<LocationKind, number>,
  clusters: Array<{ x: number; y: number }>,
  seed: string,
  version: number,
  occupied: Set<number>,
): MapLocation[] {
  const locations: MapLocation[] = []
  let id = 0
  const { lists, nonWater } = buildTileLists(terrain, width, height)
  const state: PlacementState = { terrain, width, height, occupied, nonSettlement: [] }

  // Settlements — cluster centers.
  for (let i = 0; i < counts.settlement; i++) {
    const c = clusters[i]
    if (c === undefined) continue
    locations.push({ id: id++, name: `Settlement ${pad(i + 1)}`, kind: 'settlement', x: c.x, y: c.y })
    occupied.add(c.y * width + c.x)
  }

  // Super Duper Mart — near settlement clusters.
  const martRng = seededRng(seed, version, 'loc:super_duper_mart')
  for (let i = 0; i < counts.super_duper_mart; i++) {
    const p = placeWithRejection(
      state,
      martRng,
      () => {
        const anchor =
          clusters.length > 0
            ? clusters[Math.floor(martRng() * clusters.length)]
            : nonWater[Math.floor(martRng() * nonWater.length)]
        return {
          x: clamp(anchor.x + Math.round((martRng() - 0.5) * 2 * MART_CLUSTER_RADIUS), 0, width - 1),
          y: clamp(anchor.y + Math.round((martRng() - 0.5) * 2 * MART_CLUSTER_RADIUS), 0, height - 1),
        }
      },
      LOCATION_MIN_SPACING,
      LOCATION_PLACEMENT_ATTEMPTS,
    )
    locations.push({ id: id++, name: `Super Duper Mart ${pad(i + 1)}`, kind: 'super_duper_mart', x: p.x, y: p.y })
    occupied.add(p.y * width + p.x)
    state.nonSettlement.push(p)
  }

  // Abandoned Factory — on the edges of settlement clusters.
  const factoryRng = seededRng(seed, version, 'loc:abandoned_factory')
  for (let i = 0; i < counts.abandoned_factory; i++) {
    const p = placeWithRejection(
      state,
      factoryRng,
      () => {
        const anchor =
          clusters.length > 0
            ? clusters[Math.floor(factoryRng() * clusters.length)]
            : nonWater[Math.floor(factoryRng() * nonWater.length)]
        const angle = factoryRng() * Math.PI * 2
        const dist = FACTORY_EDGE_MIN + factoryRng() * (FACTORY_EDGE_MAX - FACTORY_EDGE_MIN)
        return {
          x: clamp(Math.round(anchor.x + Math.cos(angle) * dist), 0, width - 1),
          y: clamp(Math.round(anchor.y + Math.sin(angle) * dist), 0, height - 1),
        }
      },
      LOCATION_MIN_SPACING,
      LOCATION_PLACEMENT_ATTEMPTS,
    )
    locations.push({ id: id++, name: `Abandoned Factory ${pad(i + 1)}`, kind: 'abandoned_factory', x: p.x, y: p.y })
    occupied.add(p.y * width + p.x)
    state.nonSettlement.push(p)
  }

  // Radio Tower — on hills.
  const towerRng = seededRng(seed, version, 'loc:radio_tower')
  for (let i = 0; i < counts.radio_tower; i++) {
    const p = placeWithRejection(
      state,
      towerRng,
      () => {
        return lists.hills.length > 0
          ? lists.hills[Math.floor(towerRng() * lists.hills.length)]
          : nonWater[Math.floor(towerRng() * nonWater.length)]
      },
      LOCATION_MIN_SPACING,
      LOCATION_PLACEMENT_ATTEMPTS,
    )
    locations.push({ id: id++, name: `Radio Tower ${pad(i + 1)}`, kind: 'radio_tower', x: p.x, y: p.y })
    occupied.add(p.y * width + p.x)
    state.nonSettlement.push(p)
  }

  // Water Treatment — adjacent to rivers.
  const treatmentRng = seededRng(seed, version, 'loc:water_treatment')
  for (let i = 0; i < counts.water_treatment; i++) {
    const p = placeWithRejection(
      state,
      treatmentRng,
      () => {
        if (lists.water.length > 0) {
          const w = lists.water[Math.floor(treatmentRng() * lists.water.length)]
          return (
            adjacentNonWater(terrain, width, height, w.x, w.y) ??
            nonWater[Math.floor(treatmentRng() * nonWater.length)]
          )
        }
        return nonWater[Math.floor(treatmentRng() * nonWater.length)]
      },
      LOCATION_MIN_SPACING,
      LOCATION_PLACEMENT_ATTEMPTS,
    )
    locations.push({ id: id++, name: `Water Treatment ${pad(i + 1)}`, kind: 'water_treatment', x: p.x, y: p.y })
    occupied.add(p.y * width + p.x)
    state.nonSettlement.push(p)
  }

  return locations
}

/** Red Rockets hug road junctions; Raider Camps stay away from roads. Placed post-roads. */
function placeRoadsideLocations(
  terrain: TerrainType[],
  width: number,
  height: number,
  counts: Record<LocationKind, number>,
  rocketPool: Array<{ x: number; y: number }>,
  distanceToRoad: Int32Array,
  seed: string,
  version: number,
  startId: number,
  occupied: Set<number>,
  placed: MapLocation[],
): MapLocation[] {
  const locations: MapLocation[] = []
  let id = startId
  const { nonWater } = buildTileLists(terrain, width, height)
  const state: PlacementState = {
    terrain,
    width,
    height,
    occupied,
    nonSettlement: placed.filter(l => l.kind !== 'settlement').map(l => ({ x: l.x, y: l.y })),
  }

  const rocketRng = seededRng(seed, version, 'loc:red_rocket')
  const pool = rocketPool.length > 0 ? rocketPool : nonWater
  for (let i = 0; i < counts.red_rocket; i++) {
    const p = placeWithRejection(
      state,
      rocketRng,
      () => pool[Math.floor(rocketRng() * pool.length)],
      LOCATION_MIN_SPACING,
      LOCATION_PLACEMENT_ATTEMPTS,
    )
    locations.push({ id: id++, name: `Red Rocket ${pad(i + 1)}`, kind: 'red_rocket', x: p.x, y: p.y })
    occupied.add(p.y * width + p.x)
    state.nonSettlement.push(p)
  }

  const raiderRng = seededRng(seed, version, 'loc:raider_camp')
  const far: Array<{ x: number; y: number }> = []
  for (const t of nonWater) {
    if (distanceToRoad[t.y * width + t.x] >= RAIDER_ROAD_DISTANCE) far.push(t)
  }
  // Dense road networks can leave almost no tiles far from roads; only use the
  // far pool when it can hold the camps, otherwise spread them across the map.
  const raiderPool = far.length >= counts.raider_camp ? far : nonWater
  for (let i = 0; i < counts.raider_camp; i++) {
    const p = placeWithRejection(
      state,
      raiderRng,
      () => raiderPool[Math.floor(raiderRng() * raiderPool.length)],
      LOCATION_MIN_SPACING,
      LOCATION_PLACEMENT_ATTEMPTS,
    )
    locations.push({ id: id++, name: `Raider Camp ${pad(i + 1)}`, kind: 'raider_camp', x: p.x, y: p.y })
    occupied.add(p.y * width + p.x)
    state.nonSettlement.push(p)
  }

  return locations
}

// ── Roads ──────────────────────────────────────────────────────────────

function sampleLineCost(
  terrain: TerrainType[],
  width: number,
  height: number,
  a: { x: number; y: number },
  b: { x: number; y: number },
): number {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const dist = Math.hypot(dx, dy)
  const steps = Math.max(1, Math.ceil(dist / LINE_SAMPLE_STEP))
  let cost = 0
  for (let s = 0; s <= steps; s++) {
    const t = s / steps
    const x = clamp(Math.round(a.x + dx * t), 0, width - 1)
    const y = clamp(Math.round(a.y + dy * t), 0, height - 1)
    const terr = terrain[y * width + x]
    cost += terr === 'water' ? WATER_SAMPLE_COST : TRAVEL_COST[terr]
  }
  return cost
}

function primMST(n: number, weights: number[][]): Array<{ a: number; b: number }> {
  const inTree = Array.from({ length: n }, () => false)
  const key = Array.from({ length: n }, () => Infinity)
  const parent = Array.from({ length: n }, () => -1)
  key[0] = 0
  const edges: Array<{ a: number; b: number }> = []
  for (let iter = 0; iter < n; iter++) {
    let u = -1
    let best = Infinity
    for (let i = 0; i < n; i++) {
      if (!inTree[i] && key[i] < best) {
        best = key[i]
        u = i
      }
    }
    if (u === -1) break
    inTree[u] = true
    if (parent[u] !== -1) edges.push({ a: parent[u], b: u })
    for (let v = 0; v < n; v++) {
      if (!inTree[v] && weights[u][v] < key[v]) {
        key[v] = weights[u][v]
        parent[v] = u
      }
    }
  }
  return edges
}

function mstHas(mst: Array<{ a: number; b: number }>, i: number, j: number): boolean {
  return mst.some(e => (e.a === i && e.b === j) || (e.a === j && e.b === i))
}

/**
 * Snap a waypoint to a land tile: prefer a non-water tile that is not a vault
 * slot or location; fall back to any non-water tile within the search radius,
 * then the clamped input. Roads are downstream of placement, so this never
 * moves any vault or location — it only picks where the road bends.
 */
function snapWaypoint(
  terrain: TerrainType[],
  width: number,
  height: number,
  x: number,
  y: number,
  occupied: Set<number>,
): { x: number; y: number } {
  const idx = y * width + x
  if (terrain[idx] !== 'water' && !occupied.has(idx)) return { x, y }
  let fallback: { x: number; y: number } | null = null
  for (let r = 1; r <= ROAD_CURVE_SNAP_RADIUS; r++) {
    for (let dy = -r; dy <= r; dy++) {
      for (let dx = -r; dx <= r; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue
        const nx = x + dx
        const ny = y + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const nIdx = ny * width + nx
        if (terrain[nIdx] === 'water') continue
        if (!occupied.has(nIdx)) return { x: nx, y: ny }
        if (fallback === null) fallback = { x: nx, y: ny }
      }
    }
  }
  return fallback ?? { x, y }
}

/**
 * Seeded interior waypoints for a road edge A→B: 1 on short edges, 2 on long
 * edges. Each waypoint sits on the straight chord, offset perpendicular by a
 * per-edge seeded random amount scaled to the edge length, then snapped to a
 * land tile. Routing A* through the chain bends the road instead of drawing a
 * laser-straight diagonal.
 */
function roadWaypoints(
  terrain: TerrainType[],
  width: number,
  height: number,
  a: { x: number; y: number },
  b: { x: number; y: number },
  rng: () => number,
  occupied: Set<number>,
): Array<{ x: number; y: number }> {
  const dx = b.x - a.x
  const dy = b.y - a.y
  const d = Math.hypot(dx, dy)
  if (d < 1) return []
  const count = d >= ROAD_CURVE_LONG_EDGE ? 2 : 1
  const waypoints: Array<{ x: number; y: number }> = []
  for (let i = 0; i < count; i++) {
    const t = (i + 1) / (count + 1) // 1/2 for one waypoint; 1/3, 2/3 for two
    const ux = dx / d
    const uy = dy / d
    const offset = (rng() - 0.5) * 2 * ROAD_CURVE_OFFSET * d
    // Perpendicular of (ux, uy) is (-uy, ux); the random sign bends either way.
    const px = clamp(Math.round(a.x + ux * (t * d) - uy * offset), 0, width - 1)
    const py = clamp(Math.round(a.y + uy * (t * d) + ux * offset), 0, height - 1)
    waypoints.push(snapWaypoint(terrain, width, height, px, py, occupied))
  }
  return waypoints
}

/**
 * Route A* through a chain of waypoints (A→mid→…→B), concatenating the
 * segments. Each segment uses ROAD_COST, so water crossings still become
 * bridges. Returns null when any segment is unroutable.
 */
function routeEdge(
  terrain: TerrainType[],
  width: number,
  height: number,
  from: { x: number; y: number },
  to: { x: number; y: number },
  waypoints: Array<{ x: number; y: number }>,
): Array<{ x: number; y: number }> | null {
  const chain = [from, ...waypoints, to]
  const path: Array<{ x: number; y: number }> = []
  for (let i = 0; i < chain.length - 1; i++) {
    const seg = astar(
      width,
      height,
      chain[i],
      chain[i + 1],
      idx => ROAD_COST[terrain[idx]],
      ROAD_MIN_COST,
    )
    if (seg === null) return null
    const start = path.length > 0 ? 1 : 0 // skip the tile shared with the previous segment
    for (let k = start; k < seg.path.length; k++) path.push(seg.path[k])
  }
  return path
}

function placeRiverBridges(
  terrain: TerrainType[],
  width: number,
  height: number,
  seed: string,
  version: number,
  occupied: Set<number>,
): Array<{ x: number; y: number }> {
  const waterComp = new Int32Array(width * height).fill(-1)
  let best: number[] = []
  let compId = 0
  for (let i = 0; i < width * height; i++) {
    if (terrain[i] !== 'water' || waterComp[i] !== -1) continue
    const tiles: number[] = [i]
    waterComp[i] = compId
    let head = 0
    while (head < tiles.length) {
      const cur = tiles[head++]
      const cx = cur % width
      const cy = Math.floor(cur / width)
      for (const [dx, dy] of ORTHO) {
        const nx = cx + dx
        const ny = cy + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const nIdx = ny * width + nx
        if (terrain[nIdx] !== 'water' || waterComp[nIdx] !== -1) continue
        waterComp[nIdx] = compId
        tiles.push(nIdx)
      }
    }
    if (tiles.length > best.length) best = tiles
    compId++
  }
  if (best.length < 60) return []
  const rng = seededRng(seed, version, 'bridges')
  const deep = (idx: number): number => {
    let c = 0
    const bx = idx % width
    const by = Math.floor(idx / width)
    for (let dy = -2; dy <= 2; dy++) {
      for (let dx = -2; dx <= 2; dx++) {
        const nx = bx + dx
        const ny = by + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        if (terrain[ny * width + nx] === 'water') c++
      }
    }
    return c
  }
  let a = best[0]
  let aScore = -1
  for (let t = 0; t < 24; t++) {
    const c = best[Math.floor(rng() * best.length)]
    const s = deep(c)
    if (s > aScore) {
      aScore = s
      a = c
    }
  }
  let b = a
  let bScore = -1
  for (let t = 0; t < 24; t++) {
    const c = best[Math.floor(rng() * best.length)]
    const d = Math.abs((a % width) - (c % width)) + Math.abs(Math.floor(a / width) - Math.floor(c / width))
    if (d < 20) continue
    const s = deep(c)
    if (s > bScore) {
      bScore = s
      b = c
    }
  }
  for (const idx of [a, b]) {
    const bx = idx % width
    const by = Math.floor(idx / width)
    for (let dy = -2; dy <= 2; dy++) {
      for (let dx = -2; dx <= 2; dx++) {
        const nx = bx + dx
        const ny = by + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const nIdx = ny * width + nx
        if (occupied.has(nIdx)) continue
        terrain[nIdx] = 'wasteland'
      }
    }
  }
  if (a === b) return [{ x: a % width, y: Math.floor(a / width) }]
  return [
    { x: a % width, y: Math.floor(a / width) },
    { x: b % width, y: Math.floor(b / width) },
  ]
}

function buildRoads(
  terrain: TerrainType[],
  width: number,
  height: number,
  nodes: MapLocation[],
  vaults: VaultSlot[],
  seed: string,
  version: number,
): { roads: RoadEdge[]; roadTileList: Array<{ x: number; y: number }> } {
  const roads: RoadEdge[] = []
  const roadTileSet = new Set<number>()
  if (nodes.length < 2) return { roads, roadTileList: [] }

  const n = nodes.length
  const weights: number[][] = []
  for (let i = 0; i < n; i++) {
    weights.push(Array.from({ length: n }, () => 0))
    for (let j = 0; j < n; j++) {
      if (i !== j) weights[i][j] = sampleLineCost(terrain, width, height, nodes[i], nodes[j])
    }
  }

  const mst = primMST(n, weights)
  const extraCount = Math.max(1, Math.round(mst.length * ROAD_EXTRA_EDGE_RATIO))
  // Label non-water components on pre-road terrain so loop edges never open a
  // new river crossing. MST spans (necessary for connectivity) keep their
  // bridges; extra loops stay inside one landmass and cannot sever the river.
  const comp = labelComponents(terrain, width, height)
  const nodeComp = nodes.map(l => comp[l.y * width + l.x])
  const nonMst: Array<{ a: number; b: number; w: number }> = []
  for (let i = 0; i < n; i++) {
    for (let j = i + 1; j < n; j++) {
      if (mstHas(mst, i, j)) continue
      if (nodeComp[i] !== -1 && nodeComp[j] !== -1 && nodeComp[i] !== nodeComp[j]) continue
      nonMst.push({ a: i, b: j, w: weights[i][j] })
    }
  }
  // Loops: the cheapest non-MST edges. No forced longest-edge trunks — long
  // routes still exist through the spanning network, but nothing forces a
  // straight cross-map chord.
  nonMst.sort((p, q) => p.w - q.w || p.a - q.a || p.b - q.b)
  const extra = nonMst.slice(0, extraCount)

  const edges = mst.concat(extra)
  const occupied = new Set<number>()
  for (const v of vaults) occupied.add(v.y * width + v.x)
  for (const l of nodes) occupied.add(l.y * width + l.x)
  const bridges = placeRiverBridges(terrain, width, height, seed, version, occupied)
  for (const e of edges) {
    const from = nodes[e.a]
    const to = nodes[e.b]
    // Per-edge stream keyed by stable endpoint ids: curvature is independent
    // of every other stream and of the order edges are routed.
    const rng = seededRng(seed, version, `road-curve:${Math.min(from.id, to.id)}:${Math.max(from.id, to.id)}`)
    const crossRiver = nodeComp[e.a] !== -1 && nodeComp[e.b] !== -1 && nodeComp[e.a] !== nodeComp[e.b]
    let waypoints: Array<{ x: number; y: number }>
    if (crossRiver && bridges.length > 0) {
      let bestBridge = bridges[0]
      let bestD = Infinity
      for (const br of bridges) {
        const d = (from.x - br.x) * (from.x - br.x) + (from.y - br.y) * (from.y - br.y)
        if (d < bestD) {
          bestD = d
          bestBridge = br
        }
      }
      waypoints = [bestBridge]
    } else {
      waypoints = roadWaypoints(terrain, width, height, from, to, rng, occupied)
    }
    const path = routeEdge(terrain, width, height, from, to, waypoints)
    if (path === null) continue
    for (const t of path) {
      const idx = t.y * width + t.x
      if (terrain[idx] === 'water') terrain[idx] = 'wasteland' // bridge tile
      roadTileSet.add(idx)
    }
    roads.push({ from: from.id, to: to.id, path, length: path.length, waypoints })
  }

  const roadTileList: Array<{ x: number; y: number }> = []
  for (const idx of roadTileSet) {
    roadTileList.push({ x: idx % width, y: Math.floor(idx / width) })
  }
  return { roads, roadTileList }
}

/**
 * Road tiles within JUNCTION_RADIUS of a graph node where ≥3 routed road edges
 * meet — the red_rocket placement pool. Falls back to all road tiles when no
 * junction exists.
 */
function computeJunctionTiles(
  roads: RoadEdge[],
  nodes: MapLocation[],
  roadTileList: Array<{ x: number; y: number }>,
  width: number,
  height: number,
): Array<{ x: number; y: number }> {
  const degree = new Map<number, number>()
  for (const road of roads) {
    degree.set(road.from, (degree.get(road.from) ?? 0) + 1)
    degree.set(road.to, (degree.get(road.to) ?? 0) + 1)
  }
  const junctions = nodes.filter(n => (degree.get(n.id) ?? 0) >= 3)
  if (junctions.length === 0) return roadTileList
  const roadSet = new Set(roadTileList.map(t => t.y * width + t.x))
  const tileSet = new Set<number>()
  for (const node of junctions) {
    for (let dy = -JUNCTION_RADIUS; dy <= JUNCTION_RADIUS; dy++) {
      for (let dx = -JUNCTION_RADIUS; dx <= JUNCTION_RADIUS; dx++) {
        const nx = node.x + dx
        const ny = node.y + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const idx = ny * width + nx
        if (roadSet.has(idx)) tileSet.add(idx)
      }
    }
  }
  const list: Array<{ x: number; y: number }> = []
  for (const idx of tileSet) list.push({ x: idx % width, y: Math.floor(idx / width) })
  return list.length > 0 ? list : roadTileList
}

/** Multi-source BFS from road tiles: distance + nearest road tile per tile. */
function roadDistanceField(
  width: number,
  height: number,
  roadTileList: Array<{ x: number; y: number }>,
): { dist: Int32Array; nearest: Int32Array } {
  const dist = new Int32Array(width * height).fill(-1)
  const nearest = new Int32Array(width * height).fill(-1)
  const queue: number[] = []
  for (const t of roadTileList) {
    const idx = t.y * width + t.x
    if (dist[idx] !== -1) continue
    dist[idx] = 0
    nearest[idx] = idx
    queue.push(idx)
  }
  let head = 0
  while (head < queue.length) {
    const cur = queue[head]
    head++
    const cx = cur % width
    const cy = Math.floor(cur / width)
    for (const [dx, dy] of ORTHO) {
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
      const nIdx = ny * width + nx
      if (dist[nIdx] !== -1) continue
      dist[nIdx] = dist[cur] + 1
      nearest[nIdx] = nearest[cur]
      queue.push(nIdx)
    }
  }
  return { dist, nearest }
}

// ── Origin & reachability repair ───────────────────────────────────────

function pickOrigin(terrain: TerrainType[], width: number, height: number): { x: number; y: number } {
  const cx = Math.floor(width / 2)
  const cy = Math.floor(height / 2)
  const maxR = Math.max(width, height)
  for (let r = 0; r <= maxR; r++) {
    for (let dy = -r; dy <= r; dy++) {
      for (let dx = -r; dx <= r; dx++) {
        if (Math.max(Math.abs(dx), Math.abs(dy)) !== r) continue
        const x = cx + dx
        const y = cy + dy
        if (x < 0 || x >= width || y < 0 || y >= height) continue
        if (terrain[y * width + x] === 'wasteland') return { x, y }
      }
    }
  }
  for (let i = 0; i < width * height; i++) {
    if (terrain[i] !== 'water') return { x: i % width, y: Math.floor(i / width) }
  }
  return { x: cx, y: cy }
}

function labelComponents(terrain: TerrainType[], width: number, height: number): Int32Array {
  const comp = new Int32Array(width * height).fill(-1)
  let compCount = 0
  for (let i = 0; i < width * height; i++) {
    if (terrain[i] === 'water' || comp[i] !== -1) continue
    comp[i] = compCount
    const queue: number[] = [i]
    let head = 0
    while (head < queue.length) {
      const cur = queue[head++]
      const cx = cur % width
      const cy = Math.floor(cur / width)
      for (const [dx, dy] of ORTHO) {
        const nx = cx + dx
        const ny = cy + dy
        if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
        const nIdx = ny * width + nx
        if (terrain[nIdx] === 'water' || comp[nIdx] !== -1) continue
        comp[nIdx] = compCount
        queue.push(nIdx)
      }
    }
    compCount++
  }
  return comp
}

function computeReachable(
  terrain: TerrainType[],
  width: number,
  height: number,
  origin: { x: number; y: number },
): Uint8Array {
  const reachable = new Uint8Array(width * height)
  const startIdx = origin.y * width + origin.x
  if (terrain[startIdx] === 'water') return reachable
  const comp = labelComponents(terrain, width, height)
  const home = comp[startIdx]
  for (let i = 0; i < width * height; i++) {
    if (comp[i] === home) reachable[i] = 1
  }
  return reachable
}

/** BFS over all tiles (water passable) from a vault to the nearest reachable tile. */
function pathToReachable(
  terrain: TerrainType[],
  width: number,
  height: number,
  vault: VaultSlot,
  reachable: Uint8Array,
): Array<{ x: number; y: number }> | null {
  const startIdx = vault.y * width + vault.x
  if (reachable[startIdx] === 1) return []
  const cameFrom = new Int32Array(width * height).fill(-1)
  const queue: number[] = [startIdx]
  cameFrom[startIdx] = startIdx
  let head = 0
  while (head < queue.length) {
    const cur = queue[head]
    head++
    const cx = cur % width
    const cy = Math.floor(cur / width)
    for (const [dx, dy] of ORTHO) {
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
      const nIdx = ny * width + nx
      if (cameFrom[nIdx] !== -1) continue
      cameFrom[nIdx] = cur
      if (reachable[nIdx] === 1) {
        const path: Array<{ x: number; y: number }> = []
        let c = nIdx
        while (c !== startIdx) {
          path.push({ x: c % width, y: Math.floor(c / width) })
          c = cameFrom[c]
        }
        path.push({ x: vault.x, y: vault.y })
        path.reverse()
        return path
      }
      queue.push(nIdx)
    }
  }
  return null
}

/** Deterministically carve dry paths until every vault is reachable from origin. */
/**
 * Anchored-geography constraint pass (Option A). Terrain must accommodate the
 * shared anchor set, so every anchor ends on passable ground. Deterministic and
 * cheap (a no-op once placement already avoids water); it runs on the shared
 * location set only — never a per-vault unlocked subset — so geography stays
 * common and cannot reveal private locations. Returns the number of anchors moved
 * onto land.
 *
 * Per-kind shaping (settlements vs water-adjacent kinds) is a later refinement;
 * the guarantee here is only "passable".
 */
export function constrainTerrainToAnchors(
  terrain: TerrainType[],
  width: number,
  height: number,
  anchors: ReadonlyArray<{ x: number; y: number }>,
): number {
  let adjusted = 0
  for (const anchor of anchors) {
    if (terrain[anchor.y * width + anchor.x] !== 'water') continue
    dryPatch(terrain, width, height, anchor.x, anchor.y, DRY_PATCH_RADIUS)
    adjusted++
  }
  return adjusted
}

function repairReachability(
  terrain: TerrainType[],
  width: number,
  height: number,
  vaults: VaultSlot[],
  origin: { x: number; y: number },
): void {
  for (let iter = 0; iter < 4; iter++) {
    const reachable = computeReachable(terrain, width, height, origin)
    let anyUnreachable = false
    for (const vault of vaults) {
      if (reachable[vault.y * width + vault.x] === 1) continue
      anyUnreachable = true
      const path = pathToReachable(terrain, width, height, vault, reachable)
      if (path === null) continue
      for (const t of path) {
        const idx = t.y * width + t.x
        if (terrain[idx] === 'water') terrain[idx] = 'wasteland'
      }
    }
    if (!anyUnreachable) return
  }
}

// ── Scavenge guarantee ─────────────────────────────────────────────────

/**
 * Multi-source Dijkstra over the tile grid from every location, using the
 * same TRAVEL_COST table and MinHeap as A* — the weighted analogue of the
 * road distance field. Gives each tile the routed travel cost to the nearest
 * location (water impassable), so vault coverage is a hard routed guarantee.
 */
function scavengeCostField(
  terrain: TerrainType[],
  width: number,
  height: number,
  locations: MapLocation[],
): Float64Array {
  const cost = new Float64Array(width * height).fill(Infinity)
  const closed = new Uint8Array(width * height)
  const heap = new MinHeap()
  for (const l of locations) {
    const idx = l.y * width + l.x
    if (cost[idx] === 0) continue
    cost[idx] = 0
    heap.push(idx, 0)
  }
  while (heap.size > 0) {
    const cur = heap.pop()
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
        const ax = cx + dx
        const ay = cy
        const bx = cx
        const by = cy + dy
        if (TRAVEL_COST[terrain[ay * width + ax]] === Infinity) continue
        if (TRAVEL_COST[terrain[by * width + bx]] === Infinity) continue
      }
      const moveCost = tileCost * (diag ? SQRT2 : 1)
      const tentative = cost[cur] + moveCost
      if (tentative < cost[nIdx]) {
        cost[nIdx] = tentative
        heap.push(nIdx, tentative)
      }
    }
  }
  return cost
}

/**
 * Deterministic BFS from a vault over non-water tiles; place the cache on the
 * first free, spaced tile within VAULT_CACHE_RADIUS, relaxing spacing up to
 * VAULT_CACHE_FALLBACK_RADIUS, then the nearest free tile as a last resort.
 * The cache is always reachable from its vault (BFS-connected, non-water).
 */
function placeCacheNearVault(state: PlacementState, vault: VaultSlot): { x: number; y: number } {
  const { terrain, width, height } = state
  const startIdx = vault.y * width + vault.x
  const dist = new Int32Array(width * height).fill(-1)
  const queue: number[] = [startIdx]
  dist[startIdx] = 0
  const order: number[] = []
  let head = 0
  while (head < queue.length) {
    const cur = queue[head]
    head++
    const d = dist[cur]
    if (d >= VAULT_CACHE_FALLBACK_RADIUS) continue
    const cx = cur % width
    const cy = Math.floor(cur / width)
    for (const [dx, dy] of ORTHO) {
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
      const nIdx = ny * width + nx
      if (dist[nIdx] !== -1) continue
      if (terrain[nIdx] === 'water') continue
      dist[nIdx] = d + 1
      queue.push(nIdx)
      order.push(nIdx)
    }
  }
  for (const idx of order) {
    if (dist[idx] > VAULT_CACHE_RADIUS) break
    const p = { x: idx % width, y: Math.floor(idx / width) }
    if (isTileFree(state, p, LOCATION_MIN_SPACING)) return p
  }
  for (const idx of order) {
    const p = { x: idx % width, y: Math.floor(idx / width) }
    if (isTileFree(state, p, 0)) return p
  }
  return nearestFreeTile(state, vault.x, vault.y, Math.max(width, height))
}

/**
 * Guarantee overlay: every vault whose nearest location exceeds
 * VAULT_SCAVENGE_BUDGET gets a supply cache placed next to it. Iterates vaults
 * in id order; caches are NOT part of the locationCount distribution, so
 * locations.length may exceed locationCount by the number of caches.
 */
function placeSupplyCaches(
  terrain: TerrainType[],
  width: number,
  height: number,
  vaults: VaultSlot[],
  locations: MapLocation[],
  seed: string,
  version: number,
  occupied: Set<number>,
): MapLocation[] {
  const costField = scavengeCostField(terrain, width, height, locations)
  const rng = seededRng(seed, version, 'loc:supply_cache')
  const state: PlacementState = {
    terrain,
    width,
    height,
    occupied,
    nonSettlement: locations.filter(l => l.kind !== 'settlement').map(l => ({ x: l.x, y: l.y })),
  }
  const caches: MapLocation[] = []
  let id = locations.length
  let cacheIndex = 0
  for (const vault of vaults) {
    if (costField[vault.y * width + vault.x] <= VAULT_SCAVENGE_BUDGET) continue
    const p = placeCacheNearVault(state, vault)
    const template = SUPPLY_CACHE_NAMES[Math.floor(rng() * SUPPLY_CACHE_NAMES.length)]
    caches.push({ id: id++, name: `${template} ${pad(cacheIndex + 1)}`, kind: 'supply_cache', x: p.x, y: p.y })
    occupied.add(p.y * width + p.x)
    state.nonSettlement.push(p)
    cacheIndex++
  }
  return caches
}

// ── Validation ─────────────────────────────────────────────────────────

function computeRegions(
  terrain: TerrainType[],
  width: number,
  height: number,
  originIdx: number,
): Array<{ size: number; containsOrigin: boolean }> {
  const comp = labelComponents(terrain, width, height)
  let maxId = -1
  for (let i = 0; i < width * height; i++) if (comp[i] > maxId) maxId = comp[i]
  const regions: Array<{ size: number; containsOrigin: boolean }> = []
  for (let r = 0; r <= maxId; r++) regions.push({ size: 0, containsOrigin: false })
  for (let i = 0; i < width * height; i++) {
    const rid = comp[i]
    if (rid === -1) continue
    regions[rid].size++
    if (i === originIdx) regions[rid].containsOrigin = true
  }
  return regions
}

function buildValidation(
  terrain: TerrainType[],
  width: number,
  height: number,
  vaults: VaultSlot[],
  locations: MapLocation[],
  origin: { x: number; y: number },
): ValidationReport {
  const totalVaults = vaults.length
  const reachable = computeReachable(terrain, width, height, origin)
  let reachableVaults = 0
  const unreachableVaultIds: number[] = []
  for (const v of vaults) {
    if (reachable[v.y * width + v.x] === 1) reachableVaults++
    else unreachableVaultIds.push(v.id)
  }

  const scavengeCost = scavengeCostField(terrain, width, height, locations)
  let vaultsWithNearbyScavenge = 0
  for (const v of vaults) {
    if (scavengeCost[v.y * width + v.x] <= VAULT_SCAVENGE_BUDGET) vaultsWithNearbyScavenge++
  }

  const originIdx = origin.y * width + origin.x
  const regions = computeRegions(terrain, width, height, originIdx)
  let isolatedRegions = 0
  for (const region of regions) {
    if (region.size >= MIN_REGION_SIZE && !region.containsOrigin) isolatedRegions++
  }

  const bucketW = Math.ceil(width / REGION_BUCKETS)
  const bucketH = Math.ceil(height / REGION_BUCKETS)
  const valuableByRegion: Record<string, number> = {}
  for (let r = 0; r < REGION_BUCKETS; r++) {
    for (let c = 0; c < REGION_BUCKETS; c++) {
      valuableByRegion[`r${r}c${c}`] = 0
    }
  }
  const countValuable = (p: { x: number; y: number }): void => {
    const c = Math.min(REGION_BUCKETS - 1, Math.floor(p.x / bucketW))
    const r = Math.min(REGION_BUCKETS - 1, Math.floor(p.y / bucketH))
    valuableByRegion[`r${r}c${c}`]++
  }
  for (const l of locations) countValuable(l)
  for (const v of vaults) countValuable(v)

  return {
    totalVaults,
    reachableVaults,
    unreachableVaultIds,
    vaultsWithNearbyScavenge,
    isolatedRegions,
    valuableByRegion,
  }
}

// ── A* pathfinding ─────────────────────────────────────────────────────

class MinHeap {
  private items: Array<{ idx: number; f: number }> = []

  get size(): number {
    return this.items.length
  }

  push(idx: number, f: number): void {
    this.items.push({ idx, f })
    let i = this.items.length - 1
    while (i > 0) {
      const p = (i - 1) >> 1
      if (this.items[p].f <= this.items[i].f) break
      const tmp = this.items[p]
      this.items[p] = this.items[i]
      this.items[i] = tmp
      i = p
    }
  }

  pop(): number | null {
    if (this.items.length === 0) return null
    const top = this.items[0]
    const last = this.items.pop()
    if (this.items.length > 0 && last !== undefined) {
      this.items[0] = last
      let i = 0
      for (;;) {
        const l = i * 2 + 1
        const r = l + 1
        let smallest = i
        if (l < this.items.length && this.items[l].f < this.items[smallest].f) smallest = l
        if (r < this.items.length && this.items[r].f < this.items[smallest].f) smallest = r
        if (smallest === i) break
        const tmp = this.items[i]
        this.items[i] = this.items[smallest]
        this.items[smallest] = tmp
        i = smallest
      }
    }
    return top.idx
  }
}

function heuristic(idx: number, goalIdx: number, width: number, height: number, minCost: number): number {
  const x = idx % width
  const y = Math.floor(idx / width)
  const gx = goalIdx % width
  const gy = Math.floor(goalIdx / width)
  const dx = Math.abs(x - gx)
  const dy = Math.abs(y - gy)
  return (Math.max(dx, dy) + (SQRT2 - 1) * Math.min(dx, dy)) * minCost
}

function reconstructPath(
  cameFrom: Int32Array,
  goalIdx: number,
  width: number,
  height: number,
  gScore: Float64Array,
): { path: Array<{ x: number; y: number }>; cost: number } {
  const path: Array<{ x: number; y: number }> = []
  let cur = goalIdx
  while (cur !== -1) {
    path.push({ x: cur % width, y: Math.floor(cur / width) })
    cur = cameFrom[cur]
  }
  path.reverse()
  return { path, cost: gScore[goalIdx] }
}

/**
 * A* over the tile grid. 8-neighbour with diagonal corner-cutting prevented
 * through impassable tiles. Cost is supplied by `costAt` (Infinity = impassable)
 * and `minCost` must be an admissible lower bound on any tile's cost.
 * `allowDiagonal=false` restricts movement to 4-neighbours — used for road
 * routing so the road network stays 4-connected (reachability is 4-connected).
 * `passable` optionally masks walkable tiles (used to keep known-only routing
 * from crossing unexplored cells); unmasked callers keep full-world behavior.
 */
function astar(
  width: number,
  height: number,
  from: { x: number; y: number },
  to: { x: number; y: number },
  costAt: (idx: number) => number,
  minCost: number,
  allowDiagonal = true,
  passable?: (idx: number) => boolean,
): { path: Array<{ x: number; y: number }>; cost: number } | null {
  const startIdx = from.y * width + from.x
  const goalIdx = to.y * width + to.x
  if (startIdx === goalIdx) return { path: [{ x: from.x, y: from.y }], cost: 0 }
  if (passable !== undefined && (!passable(startIdx) || !passable(goalIdx))) return null

  const gScore = new Float64Array(width * height).fill(Infinity)
  const cameFrom = new Int32Array(width * height).fill(-1)
  const closed = new Uint8Array(width * height)
  const heap = new MinHeap()
  gScore[startIdx] = 0
  heap.push(startIdx, heuristic(startIdx, goalIdx, width, height, minCost))

  const neighbors = allowDiagonal ? NEIGHBORS : ORTHO_NEIGHBORS
  while (heap.size > 0) {
    const current = heap.pop()
    if (current === null) break
    if (current === goalIdx) return reconstructPath(cameFrom, current, width, height, gScore)
    if (closed[current] === 1) continue
    closed[current] = 1
    const cx = current % width
    const cy = Math.floor(current / width)
    for (const [dx, dy, diag] of neighbors) {
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
      const nIdx = ny * width + nx
      const tileCost = costAt(nIdx)
      if (tileCost === Infinity) continue
      if (passable !== undefined && !passable(nIdx)) continue
      if (diag) {
        const ax = cx + dx
        const ay = cy
        const bx = cx
        const by = cy + dy
        const aIdx = ay * width + ax
        const bIdx = by * width + bx
        if (costAt(aIdx) === Infinity) continue
        if (passable !== undefined && !passable(aIdx)) continue
        if (costAt(bIdx) === Infinity) continue
        if (passable !== undefined && !passable(bIdx)) continue
      }
      const moveCost = tileCost * (diag ? SQRT2 : 1)
      const tentative = gScore[current] + moveCost
      if (tentative < gScore[nIdx]) {
        gScore[nIdx] = tentative
        cameFrom[nIdx] = current
        heap.push(nIdx, tentative + heuristic(nIdx, goalIdx, width, height, minCost))
      }
    }
  }
  return null
}

// ── Public API ─────────────────────────────────────────────────────────

export function generateWorld(
  config?: Partial<WorldGenConfig>,
  sharedAnchors: readonly TerrainAnchor[] = [],
): GeneratedWorld {
  const cfg: WorldGenConfig = { ...DEFAULT_WORLD_CONFIG, ...config }
  const { seed, width, height, sectorCols, sectorRows, locationCount, version } = cfg

  const terrain = generateTerrain(width, height, seed, version)
  traceRivers(terrain, width, height, seed, version)
  filterSmallComponents(terrain, width, height, 'water', 'wasteland', WATER_MIN_COMPONENT)

  // Version 1: lexical ID precedence for co-cell conflicts; exact coordinates stay
  // untouched. Reject invalid coordinates rather than silently clamping anchors.
  const anchorDiagnostics: AnchorDiagnostic[] = []
  const reserved = new Map<number, TerrainAnchor>()
  for (const anchor of [...sharedAnchors].sort((a, b) => a.id < b.id ? -1 : a.id > b.id ? 1 : 0)) {
    const valid = [anchor.coord_x, anchor.coord_y].every(c => Number.isFinite(c) && c >= 0 && c <= 100)
    const x = Math.min(width - 1, Math.floor(anchor.coord_x * width / 100))
    const y = Math.min(height - 1, Math.floor(anchor.coord_y * height / 100))
    const idx = y * width + x
    const previous = reserved.get(idx)
    const conflict = !valid ? 'Invalid registry coordinates' : previous && previous.terrain !== anchor.terrain
      ? `Co-cell terrain conflict: ${previous.id} wins` : null
    anchorDiagnostics.push({ anchor, x, y, before: valid ? terrain[idx] : null, after: null, conflict, reachable: false })
    if (!valid || previous) continue
    reserved.set(idx, anchor)
    terrain[idx] = anchor.terrain
  }

  const vaultSlots = placeVaults(terrain, width, height, sectorCols, sectorRows, seed, version)

  const counts = computeLocationCounts(locationCount)
  const occupied = new Set<number>()
  for (const v of vaultSlots) occupied.add(v.y * width + v.x)
  for (const idx of reserved.keys()) occupied.add(idx)
  const clusters = placeSettlements(terrain, width, height, counts.settlement, seed, version, occupied)
  const locations = placeLocations(terrain, width, height, counts, clusters, seed, version, occupied)

  const anchorNodes: MapLocation[] = anchorDiagnostics
    .filter(d => d.before !== null && reserved.get(d.y * width + d.x)?.id === d.anchor.id)
    .map((d, i) => ({ id: -i - 1, name: d.anchor.name, kind: 'settlement', x: d.x, y: d.y }))
  const graphNodes = [...locations.filter(l => ROAD_GRAPH_KINDS.includes(l.kind)), ...anchorNodes]
  const { roads, roadTileList } = buildRoads(terrain, width, height, graphNodes, vaultSlots, seed, version)

  const { dist } = roadDistanceField(width, height, roadTileList)
  const junctionTiles = computeJunctionTiles(roads, graphNodes, roadTileList, width, height)
  const rocketPool = junctionTiles.length > 0 ? junctionTiles : roadTileList
  const roadside = placeRoadsideLocations(
    terrain,
    width,
    height,
    counts,
    rocketPool,
    dist,
    seed,
    version,
    locations.length,
    occupied,
    locations,
  )
  locations.push(...roadside)

  // Option A: anchors own the world, so terrain accommodates them before
  // reachability is repaired.
  constrainTerrainToAnchors(terrain, width, height, locations)

  const origin = pickOrigin(terrain, width, height)
  repairReachability(terrain, width, height, [...vaultSlots, ...anchorNodes.map(n => ({
    ...n, sectorCol: -1, sectorRow: -1, claimed: false,
  }))], origin)
  filterSmallComponents(terrain, width, height, 'water', 'wasteland', WATER_MIN_COMPONENT)

  // Scavenge guarantee overlay: caches are NOT part of the locationCount
  // distribution, so locations.length may exceed locationCount by their count.
  const caches = placeSupplyCaches(terrain, width, height, vaultSlots, locations, seed, version, occupied)
  locations.push(...caches)

  const travelCost = Array.from({ length: width * height }, () => 0)
  for (let i = 0; i < terrain.length; i++) travelCost[i] = TRAVEL_COST[terrain[i]]

  const roadMask = new Uint8Array(width * height)
  for (const edge of roads) {
    for (const p of edge.path) roadMask[p.y * width + p.x] = 1
  }

  const validation = buildValidation(terrain, width, height, vaultSlots, locations, origin)
  const reachable = computeReachable(terrain, width, height, origin)
  for (const diagnostic of anchorDiagnostics) {
    if (diagnostic.before === null) continue
    const idx = diagnostic.y * width + diagnostic.x
    diagnostic.after = terrain[idx]
    diagnostic.reachable = reachable[idx] === 1
    if (!diagnostic.conflict && diagnostic.after !== diagnostic.anchor.terrain) {
      diagnostic.conflict = 'Terrain changed by downstream generation'
    }
  }

  return { config: cfg, terrain, travelCost, vaultSlots, locations, roads, roadMask, origin, validation, anchorDiagnostics }
}

export interface PathOptions {
  explored?: Uint8Array
  roadDiscount?: number
}

export function findPath(
  world: GeneratedWorld,
  from: { x: number; y: number },
  to: { x: number; y: number },
  options: PathOptions = {},
): { path: Array<{ x: number; y: number }>; cost: number; hours: number } | null {
  const { explored, roadDiscount = 1 } = options
  const { width, height } = world.config
  const discounted = roadDiscount < 1
  const costAt = (idx: number): number => {
    const base = TRAVEL_COST[world.terrain[idx]]
    return discounted && world.roadMask[idx] === 1 ? base * roadDiscount : base
  }
  const minCost = discounted ? TRAVEL_MIN_COST * roadDiscount : TRAVEL_MIN_COST
  const passable =
    explored === undefined ? undefined : (idx: number): boolean => explored[idx] === 1
  const result = astar(width, height, from, to, costAt, minCost, true, passable)
  if (result === null) return null
  return { path: result.path, cost: result.cost, hours: Math.round(result.cost * HOURS_PER_COST) }
}
