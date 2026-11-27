import { describe, it, expect } from 'vite-plus/test'
import { shapeFor, shapeMeta, PURPOSE_META } from '@/modules/map/models/markerShape'

type Source = Parameters<typeof shapeFor>[0]

const place = (overrides: Partial<NonNullable<Source>>): NonNullable<Source> =>
  ({ type: 'visited', action: 'none', group_key: null, ...overrides }) as NonNullable<Source>

describe('shapeFor', () => {
  it('gives the home vault the square', () => {
    expect(shapeFor(place({ type: 'home_vault' }))).toBe('square')
  })

  it.each([
    ['clear', 'circle'],
    ['salvage', 'circle'],
  ])('folds %s into the circle', (action, expected) => {
    expect(shapeFor(place({ action }))).toBe(expected as 'circle')
  })

  it('gives a trade action the diamond', () => {
    expect(shapeFor(place({ action: 'trade', group_key: 'city' }))).toBe('diamond')
  })

  it('gives an actionless place the triangle', () => {
    expect(shapeFor(place({ action: 'none', group_key: 'landmark' }))).toBe('triangle')
  })

  it.each([['settlement'], ['city']])('falls back to the diamond for the %s group', (group_key) => {
    expect(shapeFor({ type: 'visited', group_key })).toBe('diamond')
  })

  it('falls back to the triangle when neither action nor group say otherwise', () => {
    expect(shapeFor({ type: 'origin', group_key: 'factory' })).toBe('triangle')
    expect(shapeFor(null)).toBe('triangle')
    expect(shapeFor(undefined)).toBe('triangle')
  })
})

describe('marker shapes', () => {
  it('gives every purpose its own silhouette, with only one round shape', () => {
    const shapes = PURPOSE_META.map((meta) => meta.shape)
    expect(new Set(shapes).size).toBe(PURPOSE_META.length)
    expect(shapes.filter((shape) => shape === 'circle')).toHaveLength(1)
  })

  it('defaults an unknown shape to the Look triangle, never to a raid circle', () => {
    expect(shapeMeta(null).purpose).toBe('look')
    expect(shapeMeta(null).shape).toBe('triangle')
  })

  it('maps each shape back to the legend entry that names it', () => {
    for (const meta of PURPOSE_META) {
      expect(shapeMeta(meta.shape).label).toBe(meta.label)
      expect(shapeMeta(meta.shape).hint).toBe(meta.hint)
    }
  })
})
