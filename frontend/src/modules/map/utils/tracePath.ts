export type TracePoint = [number, number]

/**
 * Smooth Catmull-Rom curve through the waypoints, as an SVG path `d` string.
 *
 * Rounds the corners so trails flow as gentle arcs while staying anchored to
 * every real waypoint.
 */
export function smoothPath(points: TracePoint[]): string {
  const first = points[0]
  if (first === undefined) return ''
  if (points.length === 1) return `M ${first[0]} ${first[1]}`

  let d = `M ${first[0]} ${first[1]}`
  for (let i = 0; i < points.length - 1; i++) {
    const p0 = points[i - 1] ?? points[i]
    const p1 = points[i]
    const p2 = points[i + 1]
    const p3 = points[i + 2] ?? p2
    if (p0 === undefined || p1 === undefined || p2 === undefined || p3 === undefined) continue
    const cp1x = p1[0] + (p2[0] - p0[0]) / 6
    const cp1y = p1[1] + (p2[1] - p0[1]) / 6
    const cp2x = p2[0] - (p3[0] - p1[0]) / 6
    const cp2y = p2[1] - (p3[1] - p1[1]) / 6
    d += ` C ${cp1x} ${cp1y} ${cp2x} ${cp2y} ${p2[0]} ${p2[1]}`
  }
  return d
}
