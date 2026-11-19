import { describe, expect, it } from 'vite-plus/test'
import { getCreatureImagePath } from '@/core/utils/creatureAssets'

describe('getCreatureImagePath', () => {
  it.each([
    ['deathclaw', 'deathclaw'],
    ['radroach-swarm', 'radroach'],
    ['mole-rat-pack', 'mole-rat'],
    ['giant-radscorpion', 'radscorpion'],
    ['feral-ghoul', 'feral-ghoul'],
    ['training-eyebot', 'eyebot'],
    ['training-protectron', 'protectron'],
    ['training-mr-handy', 'mr-handy'],
    ['yao-guai', 'yao-guai'],
    ['mirelurk', 'mirelurk'],
    ['bloatfly', 'bloatfly'],
    ['radstag', 'radstag'],
    ['night-stalker', 'night-stalker'],
  ])('maps arena catalog key %s to the %s artwork', (key, filename) => {
    const expected =
      key === 'training-mr-handy'
        ? '/static/creature_images/originals/mr-handy.webp'
        : `/static/creature_images/assembled/${filename}.webp`
    expect(getCreatureImagePath(key)).toBe(expected)
  })

  it('returns undefined for an unknown creature key', () => {
    expect(getCreatureImagePath('mystery-beast')).toBeUndefined()
  })

  it('uses the seeded raider variant for raider keys', () => {
    expect(getCreatureImagePath('raider', 0)).toBe('/static/raider_images/variants/sable.webp?v=5')
  })
})
