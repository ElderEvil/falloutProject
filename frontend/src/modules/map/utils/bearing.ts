/**
 * Compass bearing math for map-first departures.
 *
 * Coordinate convention: the map SVG uses a viewBox where x grows east and y
 * grows south (screen space). Compass degrees are measured clockwise from
 * north: 0 = N, 90 = E, 180 = S, 270 = W.
 *
 * Because y grows south, the screen-space angle from the +x axis already
 * rotates clockwise, so the compass bearing is the standard screen-to-compass
 * conversion `atan2(dx, -dy)`:
 *   - due north (dy < 0) → 0°
 *   - due east  (dx > 0) → 90°
 *   - due south (dy > 0) → 180°
 *   - due west  (dx < 0) → 270°
 *
 * A heading expresses a direction from the vault origin; it never promises
 * arrival at a hidden destination.
 */

export interface BearingPoint {
  x: number
  y: number
}

export const COMPASS_LABELS = ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'] as const

export type CompassLabel = (typeof COMPASS_LABELS)[number]

/**
 * Compass degrees (0-360, clockwise from north) from origin to target.
 * A click exactly on the origin is degenerate and reads as 0 (north).
 */
export function bearingDegrees(origin: BearingPoint, target: BearingPoint): number {
  const dx = target.x - origin.x
  const dy = target.y - origin.y
  if (dx === 0 && dy === 0) return 0
  const degrees = (Math.atan2(dx, -dy) * 180) / Math.PI
  const normalized = (degrees + 360) % 360
  // Round to 2 decimals so float noise (89.99999999999999) never leaks into
  // the wire payload or the picker display.
  return Math.round(normalized * 100) / 100
}

/** 8-point compass label for a heading (N, NE, E, ...). */
export function compassLabel(degrees: number): CompassLabel {
  const normalized = ((degrees % 360) + 360) % 360
  return COMPASS_LABELS[Math.round(normalized / 45) % 8]
}

/** Human-readable heading, e.g. "E / 90°". */
export function formatHeading(degrees: number): string {
  return `${compassLabel(degrees)} / ${Math.round(degrees)}°`
}
