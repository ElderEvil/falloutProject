import { describe, expect, it } from 'vitest'
import {
  getItemIcon,
  getOutfitBonuses,
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
  it('builds full weapon stat rows including accuracy, type, weight and durability', () => {
    const stats = getWeaponStats({
      damage_min: 3,
      damage_max: 7,
      stat: 'strength',
      accuracy: 75,
      weapon_type: 'gun',
      weight: 2.5,
      durability: 90,
    })

    expect(stats).toEqual([
      { label: 'Damage', value: '3-7', icon: 'mdi:sword-cross' },
      { label: 'Uses', value: 'STRENGTH', icon: 'mdi:alphabet-latin' },
      { label: 'Accuracy', value: '75%', icon: 'mdi:target' },
      { label: 'Type', value: 'gun', icon: 'mdi:tag' },
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
      strength_bonus: 2,
      agility_bonus: 1,
      gender: 'male',
      weight: 5,
      durability: 40,
    })

    expect(stats).toEqual([
      { label: 'S', value: '+2', icon: 'mdi:chevron-up' },
      { label: 'A', value: '+1', icon: 'mdi:chevron-up' },
      { label: 'Gender', value: 'male', icon: 'mdi:human-male-female' },
      { label: 'Weight', value: 5, icon: 'mdi:scale' },
      { label: 'Durability', value: 40, icon: 'mdi:shield-check' },
    ])
  })

  it('collects only non-zero outfit bonuses', () => {
    expect(getOutfitBonuses({ strength_bonus: 0, luck_bonus: 3 })).toEqual([{ stat: 'L', bonus: 3 }])
  })
})
