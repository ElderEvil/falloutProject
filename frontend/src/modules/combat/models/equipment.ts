// Weapon types (matching API)
export type WeaponType = 'melee' | 'gun' | 'energy' | 'heavy'
export type WeaponSubtype =
  | 'blunt'
  | 'edged'
  | 'pointed'
  | 'pistol'
  | 'rifle'
  | 'shotgun'
  | 'automatic'
  | 'explosive'
  | 'flamer'

// Outfit types (matching API)
export type OutfitType =
  | 'common_outfit'
  | 'rare_outfit'
  | 'legendary_outfit'
  | 'power_armor'
  | 'tiered_outfit'

// Gender types (matching API)
export type Gender = 'male' | 'female'

// Rarity levels (matching API)
export type Rarity = 'common' | 'rare' | 'legendary'

// Base item interface
export interface ItemBase {
  id: string
  name: string
  description?: string
  rarity: Rarity
  value?: number | null
  icon_url?: string
  image_url?: string | null
}

// Weapon interface
export interface Weapon extends ItemBase {
  weapon_type: WeaponType
  weapon_subtype: WeaponSubtype
  stat: string // Which SPECIAL stat this weapon uses
  damage_min: number
  damage_max: number
  bonus_damage?: number
  accuracy?: number
  crit_chance?: number
  crit_multiplier?: number
  dweller_id?: string | null
  storage_id?: string | null
}

// Outfit interface
export interface Outfit extends ItemBase {
  outfit_type: OutfitType
  gender?: Gender | null
  strength_bonus?: number
  perception_bonus?: number
  endurance_bonus?: number
  charisma_bonus?: number
  intelligence_bonus?: number
  agility_bonus?: number
  luck_bonus?: number
  dweller_id?: string | null
  storage_id?: string | null
}

// Rarity color, damage range and outfit bonuses live in the shared item-display module
export { getRarityColor, getDamageRange, getOutfitBonuses } from '@/core/models/items'
