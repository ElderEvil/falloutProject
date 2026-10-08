export type TracePoint = [number, number]

function hash(...values: number[]): number {
  let h = 2166136261
  for (const value of values) {
    h = Math.imul(h ^ (value | 0), 16777619)
  }
  return (h >>> 0) / 0xffffffff
}

/**
 * Turn straight waypoint segments into a deterministic hand-drawn trace.
 *
 * Endpoints stay anchored to the real coordinates; intermediate points wobble
 * perpendicular to each segment, tapered so the line meets the markers cleanly.
 * Deterministic (hash-seeded) so re-renders and polls keep the same shape.
 */
export function tracePoints(points: TracePoint[], amplitude = 1.5, steps = 5): string {
  if (points.length === 0) return ''
  const out: string[] = [`${points[0][0]},${points[0][1]}`]

  for (let s = 0; s < points.length - 1; s++) {
    const [ax, ay] = points[s]
    const [bx, by] = points[s + 1]
    const dx = bx - ax
    const dy = by - ay
    const length = Math.hypot(dx, dy) || 1
    const nx = -dy / length
    const ny = dx / length

    for (let i = 1; i < steps; i++) {
      const t = i / steps
      const taper = Math.sin(Math.PI * t)
      const seed = hash(s, i, Math.round(ax), Math.round(ay), Math.round(bx), Math.round(by))
      const wobble = (seed * 2 - 1) * amplitude * taper
      out.push(`${(ax + dx * t + nx * wobble).toFixed(1)},${(ay + dy * t + ny * wobble).toFixed(1)}`)
    }
    out.push(`${bx},${by}`)
  }

  return out.join(' ')
}

/**
 * Smooth Catmull-Rom curve through the waypoints, as an SVG path `d` string.
 *
 * Unlike `tracePoints` (per-segment perpendicular wobble, which reads as a
 * zigzag), this rounds the corners so trails flow as gentle arcs while staying
 * anchored to every real waypoint.
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
