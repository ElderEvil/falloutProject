import { MAP_UNITS } from './atlasProjection'

/**
 * Axis-aligned rectangle in map wire units (0–160), the projection space the
 * SVG viewBox and the terrain canvas share.
 */
export interface MaskRect {
  x: number
  y: number
  width: number
  height: number
}

/**
 * Merge a flat, row-major, sorted tile-index mask (tile = y * width + x) into
 * maximal wire-space rectangles. Road/river masks are display-only geometry, so
 * merging contiguous tiles keeps painting cheap and lets casing/bleed sit on
 * the run boundary instead of every tile seam. Returns [] for an empty mask or
 * a non-positive width.
 */
export function maskToRects(mask: readonly number[], width: number): MaskRect[] {
  if (width <= 0 || mask.length === 0) return []
  const tile = MAP_UNITS / width
  const present = new Set(mask)
  const used = new Set<number>()
  const rects: MaskRect[] = []
  const rowOpen = (row: number, x: number, w: number): boolean => {
    for (let dx = 0; dx < w; dx++) {
      const index = row * width + x + dx
      if (!present.has(index) || used.has(index)) return false
    }
    return true
  }
  for (const index of mask) {
    if (used.has(index)) continue
    const x = index % width
    const y = Math.floor(index / width)
    let w = 1
    while (x + w < width && present.has(index + w) && !used.has(index + w)) w++
    let h = 1
    while (rowOpen(y + h, x, w)) h++
    for (let dy = 0; dy < h; dy++) {
      for (let dx = 0; dx < w; dx++) used.add((y + dy) * width + x + dx)
    }
    rects.push({ x: x * tile, y: y * tile, width: w * tile, height: h * tile })
  }
  return rects
}
