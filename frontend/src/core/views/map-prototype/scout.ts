import { isExplored } from './fog'

export interface ScoutPoint {
  x: number
  y: number
}

const ORTHO: ReadonlyArray<readonly [number, number]> = [
  [1, 0],
  [-1, 0],
  [0, 1],
  [0, -1],
]

/**
 * A frontier tile is a revealed tile touching unknown territory. Scouts are
 * targeted here so the player never picks an invisible destination.
 */
export function isFrontierTile(
  explored: Uint8Array,
  width: number,
  height: number,
  x: number,
  y: number,
): boolean {
  if (!isExplored(explored, width, height, x, y)) return false
  for (const [dx, dy] of ORTHO) {
    const nx = x + dx
    const ny = y + dy
    if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
    if (!isExplored(explored, width, height, nx, ny)) return true
  }
  return false
}

/**
 * The probe endpoint a scout heads for past the frontier: `distance` tiles
 * beyond it, along the origin→frontier bearing, clamped to the map. The exact
 * destination is deliberately not surfaced to the player.
 */
export function scoutProbeTarget(
  from: ScoutPoint,
  origin: ScoutPoint,
  distance: number,
  width: number,
  height: number,
): ScoutPoint {
  const dx = from.x - origin.x
  const dy = from.y - origin.y
  const len = Math.hypot(dx, dy) || 1
  const tx = Math.round(from.x + (dx / len) * distance)
  const ty = Math.round(from.y + (dy / len) * distance)
  return { x: Math.min(width - 1, Math.max(0, tx)), y: Math.min(height - 1, Math.max(0, ty)) }
}

/**
 * Coarse, intentionally imprecise travel band for a scout: the known hours to
 * the frontier widened by one uncertainty step, bucketed so the player reads a
 * range rather than a false-precision number.
 */
export function scoutBand(knownHours: number): { low: number; high: number } {
  const step = knownHours <= 2 ? 1 : knownHours <= 6 ? 2 : knownHours <= 12 ? 4 : 8
  const low = Math.max(1, Math.floor(knownHours / step) * step)
  return { low, high: low + step * 2 }
}
