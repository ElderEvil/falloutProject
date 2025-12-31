// Weapon types
export enum WeaponType {
  MELEE = 'MELEE',
  RANGED = 'RANGED'
}

export enum WeaponSubtype {
  FIST = 'FIST',
  BLADE = 'BLADE',
  BLUNT = 'BLUNT',
  PISTOL = 'PISTOL',
  RIFLE = 'RIFLE',
  SHOTGUN = 'SHOTGUN',
  HEAVY = 'HEAVY'
}

// Outfit types
export enum OutfitType {
  CASUAL = 'CASUAL',
  WORK = 'WORK',
  COMBAT = 'COMBAT',
  SPECIAL = 'SPECIAL'
}

export enum Gender {
  MALE = 'MALE',
  FEMALE = 'FEMALE'
}

// Rarity levels
export enum Rarity {
  COMMON = 'COMMON',
  UNCOMMON = 'UNCOMMON',
  RARE = 'RARE',
  LEGENDARY = 'LEGENDARY'
}

// Base item interface
export interface ItemBase {
  id: string
  name: string
  description: string
  rarity: Rarity
  value: number
  icon_url?: string
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

// Helper function to get rarity color
export function getRarityColor(rarity: Rarity): string {
  switch (rarity) {
    case Rarity.COMMON:
      return '#9CA3AF' // gray-400
    case Rarity.UNCOMMON:
      return '#10B981' // green-500
    case Rarity.RARE:
      return '#3B82F6' // blue-500
    case Rarity.LEGENDARY:
      return '#F59E0B' // amber-500
    default:
      return '#9CA3AF'
  }
}

// Helper to get damage range display
export function getDamageRange(weapon: Weapon): string {
  return `${weapon.damage_min}-${weapon.damage_max}`
}

// Helper to get total outfit bonuses
export function getOutfitBonuses(outfit: Outfit): { stat: string; bonus: number }[] {
  const bonuses: { stat: string; bonus: number }[] = []

  if (outfit.strength_bonus) bonuses.push({ stat: 'S', bonus: outfit.strength_bonus })
  if (outfit.perception_bonus) bonuses.push({ stat: 'P', bonus: outfit.perception_bonus })
  if (outfit.endurance_bonus) bonuses.push({ stat: 'E', bonus: outfit.endurance_bonus })
  if (outfit.charisma_bonus) bonuses.push({ stat: 'C', bonus: outfit.charisma_bonus })
  if (outfit.intelligence_bonus) bonuses.push({ stat: 'I', bonus: outfit.intelligence_bonus })
  if (outfit.agility_bonus) bonuses.push({ stat: 'A', bonus: outfit.agility_bonus })
  if (outfit.luck_bonus) bonuses.push({ stat: 'L', bonus: outfit.luck_bonus })

  return bonuses
}
