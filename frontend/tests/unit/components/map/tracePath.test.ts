import { describe, it, expect } from 'vitest'
import { smoothPath } from '@/modules/map/utils/tracePath'

describe('smoothPath', () => {
  it('returns an empty path for no waypoints', () => {
    expect(smoothPath([])).toBe('')
  })

  it('returns a bare move command for a single waypoint', () => {
    expect(smoothPath([[3, 4]])).toBe('M 3 4')
  })

  it('anchors both endpoints of a two-point path', () => {
    const path = smoothPath([
      [0, 0],
      [10, 0],
    ])

    expect(path).toBe('M 0 0 C 1.6666666666666667 0 8.333333333333334 0 10 0')
  })

  it('anchors every waypoint and draws one curve per segment', () => {
    const path = smoothPath([
      [0, 0],
      [10, 0],
      [20, 5],
    ])

    expect(path.startsWith('M 0 0')).toBe(true)
    expect(path.endsWith('20 5')).toBe(true)
    expect(path.match(/C/g)).toHaveLength(2)
  })

  it('produces deterministic output for a multi-point path', () => {
    const points: [number, number][] = [
      [0, 0],
      [10, 0],
      [20, 5],
    ]

    expect(smoothPath(points)).toBe(smoothPath(points))
    expect(smoothPath(points)).toBe(
      'M 0 0 C 1.6666666666666667 0 6.666666666666666 -0.8333333333333334 10 0 C 13.333333333333334 0.8333333333333334 18.333333333333332 4.166666666666667 20 5'
    )
  })
})
