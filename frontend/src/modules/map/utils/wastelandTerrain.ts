/**
 * Deterministic wasteland terrain generation for the SVG world map.
 *
 * All randomness is derived from a seeded PRNG (mulberry32) so terrain
 * features are stable across re-renders and testable. No Math.random().
 *
 * Generates three feature types:
 *   1. Terrain patches  — irregular ellipses (scorched ground, dust bowls)
 *   2. Contour lines    — subtle elevation/wind paths
 *   3. Road segments    — dashed paths connecting marker cluster anchors
 */

// ── Seeded PRNG (mulberry32) ──────────────────────────────────────────

function mulberry32(seed: number): () => number {
  let s = seed | 0
  return () => {
    s = (s + 0x6d2b79f5) | 0
    let t = Math.imul(s ^ (s >>> 15), 1 | s)
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

// ── Types ─────────────────────────────────────────────────────────────

export interface TerrainPatch {
  cx: number
  cy: number
  rx: number
  ry: number
  rotation: number
  opacity: number
  kind: 'scorched' | 'dust' | 'crater'
}

export interface ContourLine {
  /** SVG path d attribute */
  d: string
  opacity: number
}

export interface RoadSegment {
  /** SVG path d attribute */
  d: string
  opacity: number
  dashArray: string
}

export interface WastelandTerrain {
  patches: TerrainPatch[]
  contours: ContourLine[]
  roads: RoadSegment[]
}

// ── Terrain generation ────────────────────────────────────────────────

const SEED = 0xf04_111 // fixed seed — "FO4 111" (Fallout 4 Vault 111)

/**
 * Generate all deterministic terrain features for the map.
 * Call once — the result is pure and stable.
 */
export function generateTerrain(): WastelandTerrain {
  const rand = mulberry32(SEED)

  return {
    patches: generatePatches(rand),
    contours: generateContours(rand),
    roads: generateRoads(rand),
  }
}

/** Generate wasteland terrain patches (scorched, dust, craters). */
function generatePatches(rand: () => number): TerrainPatch[] {
  const patches: TerrainPatch[] = []

  // Scorched ground — large dark ellipses, very subtle
  for (let i = 0; i < 8; i++) {
    patches.push({
      cx: 8 + rand() * 144,
      cy: 8 + rand() * 144,
      rx: 9.6 + rand() * 19.2,
      ry: 6.4 + rand() * 16,
      rotation: rand() * 360,
      opacity: 0.04 + rand() * 0.04, // 0.04–0.08
      kind: 'scorched',
    })
  }

  // Dust bowls — medium ellipses, slightly lighter
  for (let i = 0; i < 6; i++) {
    patches.push({
      cx: 16 + rand() * 128,
      cy: 16 + rand() * 128,
      rx: 6.4 + rand() * 12.8,
      ry: 4.8 + rand() * 9.6,
      rotation: rand() * 360,
      opacity: 0.03 + rand() * 0.03, // 0.03–0.06
      kind: 'dust',
    })
  }

  // Craters — small circles, slightly more visible
  for (let i = 0; i < 5; i++) {
    const radius = 2.4 + rand() * 4.8
    patches.push({
      cx: 16 + rand() * 128,
      cy: 16 + rand() * 128,
      rx: radius,
      ry: radius,
      rotation: 0,
      opacity: 0.06 + rand() * 0.06, // 0.06–0.12
      kind: 'crater',
    })
  }

  return patches
}

/** Generate subtle contour/elevation lines as smooth curves. */
function generateContours(rand: () => number): ContourLine[] {
  const contours: ContourLine[] = []

  for (let i = 0; i < 6; i++) {
    const startX = rand() * 48
    const startY = 16 + rand() * 128
    const cp1X = 32 + rand() * 48
    const cp1Y = startY + (rand() - 0.5) * 48
    const cp2X = 80 + rand() * 48
    const cp2Y = startY + (rand() - 0.5) * 48
    const endX = 112 + rand() * 48
    const endY = startY + (rand() - 0.5) * 32

    contours.push({
      d: `M ${startX.toFixed(1)} ${startY.toFixed(1)} C ${cp1X.toFixed(1)} ${cp1Y.toFixed(1)}, ${cp2X.toFixed(1)} ${cp2Y.toFixed(1)}, ${endX.toFixed(1)} ${endY.toFixed(1)}`,
      opacity: 0.04 + rand() * 0.04, // 0.04–0.08
    })
  }

  return contours
}

/** Generate road segments connecting loose anchor points. */
function generateRoads(rand: () => number): RoadSegment[] {
  const roads: RoadSegment[] = []

  // 4 fixed anchor "hubs" derived from the seed — roughly in quadrants
  const hubs = [
    { x: 24 + rand() * 32, y: 24 + rand() * 32 },
    { x: 96 + rand() * 40, y: 16 + rand() * 40 },
    { x: 16 + rand() * 40, y: 96 + rand() * 40 },
    { x: 88 + rand() * 48, y: 88 + rand() * 48 },
  ]

  // Connect hub 0→1, 0→2, 1→3, 2→3 (spanning the map)
  const connections = [
    [0, 1],
    [0, 2],
    [1, 3],
    [2, 3],
  ]

  for (const [a, b] of connections) {
    const from = hubs[a]
    const to = hubs[b]
    const midX = (from.x + to.x) / 2 + (rand() - 0.5) * 24
    const midY = (from.y + to.y) / 2 + (rand() - 0.5) * 24

    roads.push({
      d: `M ${from.x.toFixed(1)} ${from.y.toFixed(1)} Q ${midX.toFixed(1)} ${midY.toFixed(1)}, ${to.x.toFixed(1)} ${to.y.toFixed(1)}`,
      opacity: 0.06 + rand() * 0.04, // 0.06–0.10
      dashArray: '2.4 1.6',
    })
  }

  return roads
}
