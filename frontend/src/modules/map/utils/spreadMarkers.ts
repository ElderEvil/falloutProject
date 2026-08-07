/**
 * Deterministic anti-overlap spread for map markers.
 *
 * When markers land within a collision radius of each other, push them apart
 * gently so the dense clusters become readable. The output is stable across
 * re-renders/polls because the algorithm is fully deterministic — no Math.random().
 *
 * Original coordinates are preserved for click/data; only renderX/renderY shift.
 */

export interface SpreadInput {
  id: string
  x: number
  y: number
}

export interface SpreadResult {
  renderX: number
  renderY: number
}

export interface SpreadOptions {
  /** Minimum center-to-center distance before markers overlap. Default 7.2 */
  collisionRadius?: number
  /** Max displacement from original position. Default 4.0 */
  maxDisplace?: number
  /** Number of relaxation iterations. Default 5 */
  iterations?: number
}

const DEFAULT_OPTIONS: Required<SpreadOptions> = {
  collisionRadius: 7.2,
  maxDisplace: 4.0,
  iterations: 5,
}

/**
 * Deterministic hash of a string → 32-bit int.
 * Used to derive a stable push angle when two markers share the same position.
 */
function hashStr(s: string): number {
  let h = 0
  for (let i = 0; i < s.length; i++) {
    h = ((h << 5) - h + s.charCodeAt(i)) | 0
  }
  return h
}

/**
 * Derive a deterministic angle (radians) for a pair of markers.
 * Order-independent: hash(a+b) == hash(b+a) is NOT guaranteed, so we sort
 * the ids first to make it symmetric.
 */
function pairAngle(idA: string, idB: string): number {
  const [a, b] = idA < idB ? [idA, idB] : [idB, idA]
  const h = hashStr(`${a}:${b}`)
  // Map int → [0, 2π)
  return ((h & 0x7fffffff) / 0x7fffffff) * Math.PI * 2
}

/**
 * Spread markers apart so no two are closer than `collisionRadius`.
 *
 * Returns a Map keyed by marker id → { renderX, renderY }.
 * Markers that don't collide keep their original position.
 */
export function spreadMarkers(
  markers: SpreadInput[],
  options?: SpreadOptions
): Map<string, SpreadResult> {
  const { collisionRadius, maxDisplace, iterations } = { ...DEFAULT_OPTIONS, ...options }

  if (markers.length === 0) return new Map()

  // Working copies
  interface WorkItem {
    id: string
    ox: number
    oy: number
    x: number
    y: number
  }

  const items: WorkItem[] = markers.map((m) => ({
    id: m.id,
    ox: m.x,
    oy: m.y,
    x: m.x,
    y: m.y,
  }))

  const n = items.length
  const radiusSq = collisionRadius * collisionRadius

  for (let iter = 0; iter < iterations; iter++) {
    // Damping decreases each iteration so convergence is smooth
    const damping = 1 - iter / (iterations + 1)

    for (let i = 0; i < n; i++) {
      for (let j = i + 1; j < n; j++) {
        const a = items[i]
        const b = items[j]
        const dx = b.x - a.x
        const dy = b.y - a.y
        const distSq = dx * dx + dy * dy

        if (distSq >= radiusSq) continue

        const dist = Math.sqrt(distSq)

        if (dist > 0.001) {
          // Normal push along the connecting line
          const overlap = (collisionRadius - dist) / 2
          const pushX = (dx / dist) * overlap * damping
          const pushY = (dy / dist) * overlap * damping
          a.x -= pushX
          a.y -= pushY
          b.x += pushX
          b.y += pushY
        } else {
          // Coincident markers — use deterministic angle
          const angle = pairAngle(a.id, b.id)
          const push = (collisionRadius / 2) * damping
          a.x -= Math.cos(angle) * push
          a.y -= Math.sin(angle) * push
          b.x += Math.cos(angle) * push
          b.y += Math.sin(angle) * push
        }
      }
    }

    // Clamp positions to [0, 160] and limit displacement
    for (const item of items) {
      item.x = Math.max(0, Math.min(160, item.x))
      item.y = Math.max(0, Math.min(160, item.y))

      const ddx = item.x - item.ox
      const ddy = item.y - item.oy
      const dDist = Math.sqrt(ddx * ddx + ddy * ddy)
      if (dDist > maxDisplace) {
        item.x = item.ox + (ddx / dDist) * maxDisplace
        item.y = item.oy + (ddy / dDist) * maxDisplace
      }
    }
  }

  const result = new Map<string, SpreadResult>()
  for (const item of items) {
    result.set(item.id, { renderX: item.x, renderY: item.y })
  }
  return result
}
