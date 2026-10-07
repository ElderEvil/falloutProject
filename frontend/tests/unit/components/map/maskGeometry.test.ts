import { describe, expect, it } from 'vitest'
import { maskToRects } from '@/modules/map/utils/maskGeometry'

describe('maskToRects', () => {
  it('returns no rects for an empty mask', () => {
    expect(maskToRects([], 80)).toEqual([])
  })

  it('maps a single tile index to its wire-space cell', () => {
    // width 80 → tile 2 units: index 5 is column 5, row 0.
    expect(maskToRects([5], 80)).toEqual([{ x: 10, y: 0, width: 2, height: 2 }])
  })

  it('merges a horizontal run into one rect', () => {
    expect(maskToRects([40, 41, 42], 80)).toEqual([{ x: 80, y: 0, width: 6, height: 2 }])
  })

  it('merges a vertical run into one rect', () => {
    expect(maskToRects([10, 90, 170], 80)).toEqual([{ x: 20, y: 0, width: 2, height: 6 }])
  })

  it('does not merge a run across a row boundary', () => {
    expect(maskToRects([79, 80], 80)).toEqual([
      { x: 158, y: 0, width: 2, height: 2 },
      { x: 0, y: 2, width: 2, height: 2 },
    ])
  })

  it('merges a filled block into one rect', () => {
    expect(maskToRects([0, 1, 80, 81], 80)).toEqual([{ x: 0, y: 0, width: 4, height: 4 }])
  })

  it('returns no rects for a non-positive width', () => {
    expect(maskToRects([0, 1], 0)).toEqual([])
  })
})
