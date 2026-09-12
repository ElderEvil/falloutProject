import { describe, it, expect } from 'vitest'
import { tracePoints } from '@/modules/map/utils/tracePath'

describe('tracePoints', () => {
  it('anchors the original endpoints', () => {
    const points = tracePoints([
      [0, 0],
      [10, 0],
    ]).split(' ')

    expect(points[0]).toBe('0,0')
    expect(points.at(-1)).toBe('10,0')
  })

  it('inserts wobble away from the straight line', () => {
    const points = tracePoints([
      [0, 0],
      [10, 0],
    ]).split(' ')

    expect(points.length).toBeGreaterThan(2)
    expect(points.some((point) => Number(point.split(',')[1]) !== 0)).toBe(true)
  })

  it('is deterministic across calls', () => {
    const a = tracePoints([
      [0, 0],
      [10, 0],
      [20, 5],
    ])
    const b = tracePoints([
      [0, 0],
      [10, 0],
      [20, 5],
    ])

    expect(a).toBe(b)
  })

  it('returns a single point unchanged', () => {
    expect(tracePoints([[3, 4]])).toBe('3,4')
  })
})
