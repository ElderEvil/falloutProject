import { describe, it, expect } from 'vite-plus/test'
import { purposeFor, purposeMeta } from '@/modules/map/models/purposeMeta'

type Source = Parameters<typeof purposeFor>[0]

const place = (overrides: Partial<NonNullable<Source>>): NonNullable<Source> =>
  ({ type: 'visited', action: 'none', group_key: null, ...overrides }) as NonNullable<Source>

describe('purposeFor', () => {
  it('sends the home vault to Home', () => {
    expect(purposeFor(place({ type: 'home_vault' }))).toBe('home')
  })

  it.each([
    ['clear', 'clear'],
    ['salvage', 'clear'],
  ])('folds %s into Clear', (action, expected) => {
    expect(purposeFor(place({ action }))).toBe(expected as 'clear')
  })

  it('sends a trade action to Trade', () => {
    expect(purposeFor(place({ action: 'trade', group_key: 'city' }))).toBe('trade')
  })

  it('sends an actionless place to Look', () => {
    expect(purposeFor(place({ action: 'none', group_key: 'landmark' }))).toBe('look')
  })

  it.each([['settlement'], ['city']])('falls back to Trade for the %s group', (group_key) => {
    expect(purposeFor({ type: 'visited', group_key })).toBe('trade')
  })

  it('falls back to Look when neither action nor group say otherwise', () => {
    expect(purposeFor({ type: 'origin', group_key: 'factory' })).toBe('look')
    expect(purposeFor(null)).toBe('look')
    expect(purposeFor(undefined)).toBe('look')
  })
})

describe('purposeMeta', () => {
  it('gives every purpose its own body shape', () => {
    const shapes = ['clear', 'trade', 'look', 'home'].map((p) => purposeMeta(p as 'clear').shape)
    expect(new Set(shapes).size).toBe(4)
  })

  it('defaults an unknown purpose to Look, never to a raid shape', () => {
    expect(purposeMeta(null).purpose).toBe('look')
  })
})
