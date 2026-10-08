export function revealDisc(
  explored: Uint8Array,
  width: number,
  height: number,
  cx: number,
  cy: number,
  radius: number,
): void {
  for (let dy = -radius; dy <= radius; dy++) {
    for (let dx = -radius; dx <= radius; dx++) {
      if (dx * dx + dy * dy > radius * radius) continue
      const nx = cx + dx
      const ny = cy + dy
      if (nx < 0 || nx >= width || ny < 0 || ny >= height) continue
      explored[ny * width + nx] = 1
    }
  }
}

export function isExplored(
  explored: Uint8Array,
  width: number,
  height: number,
  x: number,
  y: number,
): boolean {
  if (x < 0 || x >= width || y < 0 || y >= height) return false
  return explored[y * width + x] === 1
}

/**
 * Single visibility predicate for the expedition-map contract: a tile is visible
 * when inspection is bypassed (developer / show-all) or it has been explored.
 * Rendering, selection, routing, ETA, and hit-testing must all call this instead
 * of re-deriving visibility.
 */
export function isVisible(
  explored: Uint8Array,
  width: number,
  height: number,
  x: number,
  y: number,
  bypass = false,
): boolean {
  return bypass || isExplored(explored, width, height, x, y)
}
