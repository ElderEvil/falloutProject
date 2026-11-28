import { describe, it, expect } from 'vite-plus/test'
import { shapeFor, shapeMeta, PURPOSE_META } from '@/modules/map/models/markerShape'

type Source = Parameters<typeof shapeFor>[0]

const place = (overrides: Partial<NonNullable<Source>>): NonNullable<Source> =>
  ({ type: 'visited', group_key: 'power', ...overrides }) as NonNullable<Source>

describe('shapeFor', () => {
  it.each([
    ['clear', 'circle'],
    ['trade', 'diamond'],
    ['look', 'square'],
  ])('maps purpose %s to %s', (purpose, shape) => {
    expect(shapeFor(place({ purpose }))).toBe(shape)
  })

  it('gives the home vault the hexagon, even against a conflicting purpose', () => {
    expect(shapeFor({ type: 'home_vault', group_key: null })).toBe('hexagon')
    expect(shapeFor(place({ type: 'home_vault', purpose: 'clear' }))).toBe('hexagon')
  })

  it('ignores action, so scouting or dispatch cannot redraw the body', () => {
    expect(shapeFor({ ...place({ purpose: 'clear' }), action: 'none' })).toBe('circle')
  })

  it.each([['settlement'], ['city']])('falls back to the diamond for the %s group', (group_key) => {
    expect(shapeFor({ type: 'visited', group_key })).toBe('diamond')
  })

  it('falls back to the Look square, never Home, for an unknown purpose', () => {
    expect(shapeFor(place({ purpose: 'bogus' }))).toBe('square')
    expect(shapeFor(place({ group_key: 'settlement', purpose: 'bogus' }))).toBe('diamond')
    expect(shapeFor(null)).toBe('square')
    expect(shapeFor(undefined)).toBe('square')
  })
})

describe('marker shapes', () => {
  it('gives every purpose its own silhouette, with only one round shape', () => {
    const shapes = PURPOSE_META.map((meta) => meta.shape)
    expect(new Set(shapes).size).toBe(PURPOSE_META.length)
    expect(shapes.filter((shape) => shape === 'circle')).toHaveLength(1)
  })

  it('defaults an unknown shape to the Look square, never to a raid circle', () => {
    expect(shapeMeta(null).purpose).toBe('look')
    expect(shapeMeta(null).shape).toBe('square')
  })

  it('maps each shape back to the legend entry that names it', () => {
    for (const meta of PURPOSE_META) {
      expect(shapeMeta(meta.shape).label).toBe(meta.label)
      expect(shapeMeta(meta.shape).hint).toBe(meta.hint)
    }
  })
})
