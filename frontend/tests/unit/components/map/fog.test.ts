import { describe, expect, it } from 'vitest'
import { computeExploredMask, isExploredTile } from '@/modules/map/utils/fog'
import { registryToTile } from '@/modules/map/utils/atlasProjection'

describe('atlas fog of war', () => {
  it('reveals around the home vault', () => {
    const mask = computeExploredMask({ home: { coord_x: 50, coord_y: 50 }, discovered: [], trailPoints: [] })
    const x = registryToTile(50)
    const y = registryToTile(50)
    expect(isExploredTile(mask, x, y)).toBe(true)
    expect(isExploredTile(mask, 0, 0)).toBe(false)
  })

  it('reveals around discovered locations and trail points', () => {
    const mask = computeExploredMask({
      home: null,
      discovered: [{ coord_x: 20, coord_y: 20 }],
      trailPoints: [{ coord_x: 80, coord_y: 80 }],
    })
    expect(isExploredTile(mask, registryToTile(20), registryToTile(20))).toBe(true)
    expect(isExploredTile(mask, registryToTile(80), registryToTile(80))).toBe(true)
    expect(isExploredTile(mask, registryToTile(50), registryToTile(50))).toBe(false)
  })

  it('is empty with no discovery state', () => {
    const mask = computeExploredMask({ home: null, discovered: [], trailPoints: [] })
    expect(mask.every(value => value === 0)).toBe(true)
  })

  it('clamps reveals at the map edge without throwing', () => {
    const mask = computeExploredMask({ home: { coord_x: 0, coord_y: 0 }, discovered: [], trailPoints: [] })
    expect(isExploredTile(mask, 0, 0)).toBe(true)
    expect(mask.some(value => value === 1)).toBe(true)
  })
})
