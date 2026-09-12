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
