import { describe, expect, it } from 'vitest'
import {
  getItemIcon,
  getOutfitBonuses,
  getOutfitFireResist,
  getOutfitRadiationResist,
  getOutfitStats,
  getRarityBorderClass,
  getRarityColor,
  getRarityTextClass,
  getWeaponStats,
} from '@/core/models/items'

describe('item icon mapping', () => {
  it('maps every weapon subtype to an icon', () => {
    expect(getItemIcon('weapon', { weapon_subtype: 'rifle' })).toBe('game-icons:rifle')
    expect(getItemIcon('weapon', { weapon_subtype: 'pistol' })).toBe('mdi:pistol')
    expect(getItemIcon('weapon', { weapon_subtype: 'shotgun' })).toBe('game-icons:shotgun')
    expect(getItemIcon('weapon', { weapon_subtype: 'automatic' })).toBe('game-icons:machine-gun')
    expect(getItemIcon('weapon', { weapon_subtype: 'explosive' })).toBe('mdi:bomb')
    expect(getItemIcon('weapon', { weapon_subtype: 'flamer' })).toBe('mdi:fire')
    expect(getItemIcon('weapon', { weapon_subtype: 'edged' })).toBe('mdi:sword')
    expect(getItemIcon('weapon', { weapon_subtype: 'blunt' })).toBe('mdi:hammer')
    expect(getItemIcon('weapon', { weapon_subtype: 'pointed' })).toBe('mdi:spear')
  })

  it('maps outfit types and junk, with fallbacks for unknown values', () => {
    expect(getItemIcon('outfit', { outfit_type: 'power_armor' })).toBe('mdi:robot')
    expect(getItemIcon('outfit', { outfit_type: 'tiered_outfit' })).toBe('mdi:star')
    expect(getItemIcon('outfit', {})).toBe('mdi:tshirt-crew')
    expect(getItemIcon('junk', {})).toBe('mdi:wrench')
    expect(getItemIcon('weapon', { weapon_subtype: 'RIFLE' })).toBe('game-icons:rifle')
    expect(getItemIcon('weapon', {})).toBe('mdi:pistol')
  })
})

describe('rarity styling', () => {
  it('returns token-based colors, normalizing case and whitespace', () => {
    expect(getRarityColor('rare')).toBe('var(--color-rarity-rare)')
    expect(getRarityColor(' LEGENDARY ')).toBe('var(--color-rarity-legendary)')
    expect(getRarityColor('unknown')).toBe('var(--color-rarity-common)')
    expect(getRarityColor()).toBe('var(--color-rarity-common)')
  })

  it('returns Tailwind border and text classes per rarity', () => {
    expect(getRarityBorderClass('legendary')).toBe('border-(--color-rarity-legendary)')
    expect(getRarityBorderClass('bogus')).toBe('border-(--color-rarity-common)')
    expect(getRarityTextClass('rare')).toBe('text-(--color-rarity-rare)')
    expect(getRarityTextClass(undefined)).toBe('text-(--color-rarity-common)')
  })
})

describe('stat rows', () => {
  it('builds full weapon stat rows including accuracy, type, subtype, weight and durability', () => {
    const stats = getWeaponStats({
      damage_min: 3,
      damage_max: 7,
      stat: 'strength',
      accuracy: 75,
      weapon_type: 'gun',
      weapon_subtype: 'rifle',
      weight: 2.5,
      durability: 90,
    })

    expect(stats).toEqual([
      { label: 'Damage', value: '3-7', icon: 'mdi:sword-cross' },
      { label: 'Uses', value: 'STRENGTH', icon: 'mdi:alphabet-latin' },
      { label: 'Accuracy', value: '75%', icon: 'mdi:target' },
      { label: 'Type', value: 'gun', icon: 'mdi:tag' },
      { label: 'Subtype', value: 'Rifle', icon: 'mdi:tag-outline' },
      { label: 'Weight', value: 2.5, icon: 'mdi:scale' },
      { label: 'Durability', value: 90, icon: 'mdi:shield-check' },
    ])
  })

  it('omits optional weapon stats when absent', () => {
    const labels = getWeaponStats({ damage_min: 1, damage_max: 2 }).map((s) => s.label)
    expect(labels).toEqual(['Damage'])
  })

  it('builds outfit stat rows with SPECIAL bonuses, gender, weight and durability', () => {
    const stats = getOutfitStats({
      strength: 2,
      agility: 1,
      gender: 'male',
      weight: 5,
      durability: 40,
    })

    expect(stats).toEqual([
      { label: 'Strength', value: '+2', icon: 'mdi:chevron-up' },
      { label: 'Agility', value: '+1', icon: 'mdi:chevron-up' },
      { label: 'Gender', value: 'male', icon: 'mdi:human-male-female' },
      { label: 'Weight', value: 5, icon: 'mdi:scale' },
      { label: 'Durability', value: 40, icon: 'mdi:shield-check' },
    ])
  })

  it('collects only non-zero outfit bonuses', () => {
    expect(getOutfitBonuses({ strength: 0, luck: 3 })).toEqual([{ stat: 'Luck', bonus: 3 }])
  })

  it('resolves outfit radiation resist by type, with name overrides winning', () => {
    expect(getOutfitRadiationResist({ outfit_type: 'power_armor' })).toBe(0.75)
    expect(getOutfitRadiationResist({ outfit_type: 'POWER_ARMOR' })).toBe(0.75)
    expect(getOutfitRadiationResist({ outfit_type: 'rare_outfit' })).toBe(0)
    expect(getOutfitRadiationResist({ name: 'Hazmat suit', outfit_type: 'rare_outfit' })).toBe(1)
    expect(getOutfitRadiationResist({ name: '  Hazmat suit  ', outfit_type: 'rare_outfit' })).toBe(1)
    expect(getOutfitRadiationResist({ name: 'ADVANCED HAZMAT SUIT', outfit_type: 'legendary_outfit' })).toBe(1)
    expect(getOutfitRadiationResist({ outfit_type: 'common_outfit' })).toBe(0)
    expect(getOutfitRadiationResist({})).toBe(0)
  })

  it('shows a RAD resist row only when the outfit protects', () => {
    const armored = getOutfitStats({ outfit_type: 'power_armor', name: 'T-51d power armor' })
    expect(armored).toContainEqual({ label: 'RAD resist', value: '75%', icon: 'mdi:radiation' })

    const plain = getOutfitStats({ strength: 1 }).map((s) => s.label)
    expect(plain).not.toContain('RAD resist')
  })

  it('prefers a declared radiation share over the type fallback', () => {
    expect(getOutfitRadiationResist({ radiation_resist: 0, outfit_type: 'power_armor' })).toBe(0)
    expect(getOutfitRadiationResist({ radiation_resist: 1, outfit_type: 'rare_outfit' })).toBe(1)
    expect(getOutfitRadiationResist({ radiation_resist: null, outfit_type: 'power_armor' })).toBe(0.75)
  })

  it('reports the declared fire share', () => {
    expect(getOutfitFireResist({ fire_resist: 0.5 })).toBe(0.5)
    expect(getOutfitFireResist({ fire_resist: null })).toBe(0)
    expect(getOutfitFireResist({})).toBe(0)
  })

  it('shows a fire resist row only when the outfit is fire-rated', () => {
    const rated = getOutfitStats({ fire_resist: 0.5 })
    expect(rated).toContainEqual({ label: 'Fire resist', value: '50%', icon: 'mdi:fire' })

    const plain = getOutfitStats({ fire_resist: 0, strength: 1 }).map((s) => s.label)
    expect(plain).not.toContain('Fire resist')
  })
})
