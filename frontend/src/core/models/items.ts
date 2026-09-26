/**
 * Single source of truth for item display: icons, rarity styling and stat rows.
 * Shared by combat (EquipmentCard), storage (StorageItemCard) and exploration loot lists.
 */

// Weapon subtype -> icon (game-icons used where MDI has no glyph)
export const WEAPON_SUBTYPE_ICONS: Record<string, string> = {
  pistol: 'mdi:pistol',
  rifle: 'game-icons:rifle',
  shotgun: 'game-icons:shotgun',
  automatic: 'game-icons:machine-gun',
  explosive: 'mdi:bomb',
  flamer: 'mdi:fire',
  edged: 'mdi:sword',
  blunt: 'mdi:hammer',
  pointed: 'mdi:spear',
}

// Outfit type -> icon
export const OUTFIT_TYPE_ICONS: Record<string, string> = {
  common_outfit: 'mdi:tshirt-crew',
  rare_outfit: 'mdi:hard-hat',
  legendary_outfit: 'mdi:shield',
  power_armor: 'mdi:robot',
  tiered_outfit: 'mdi:star',
}

export const JUNK_ICON = 'mdi:wrench'

// Generic storage items share the quest-reward icon language (see getItemIcon)
export const GENERIC_ITEM_ICONS: Record<string, string> = {
  consumable: 'mdi:bottle-tonic',
  lunchbox: 'mdi:gift',
  pet: 'mdi:paw',
}

export interface ItemIconSource {
  image_url?: string | null
  name?: string
  weapon_subtype?: string
  outfit_type?: string
}

export function getItemIcon(itemType: string, item: ItemIconSource): string {
  if (itemType === 'weapon') {
    return WEAPON_SUBTYPE_ICONS[item.weapon_subtype?.toLowerCase() ?? ''] ?? 'mdi:pistol'
  }
  if (itemType === 'outfit') {
    return OUTFIT_TYPE_ICONS[item.outfit_type?.toLowerCase() ?? ''] ?? 'mdi:tshirt-crew'
  }
  if (itemType === 'junk') return JUNK_ICON
  return GENERIC_ITEM_ICONS[itemType.toLowerCase()] ?? 'mdi:package-variant'
}

type RarityKey = 'common' | 'rare' | 'legendary'

const RARITY_TOKENS: Record<RarityKey, { color: string; border: string; text: string }> = {
  common: {
    color: 'var(--color-rarity-common)',
    border: 'border-(--color-rarity-common)',
    text: 'text-(--color-rarity-common)',
  },
  rare: {
    color: 'var(--color-rarity-rare)',
    border: 'border-(--color-rarity-rare)',
    text: 'text-(--color-rarity-rare)',
  },
  legendary: {
    color: 'var(--color-rarity-legendary)',
    border: 'border-(--color-rarity-legendary)',
    text: 'text-(--color-rarity-legendary)',
  },
}

function rarityKey(rarity?: string): RarityKey {
  const key = rarity?.trim().toLowerCase()
  return key === 'rare' || key === 'legendary' ? key : 'common'
}

export function getRarityColor(rarity?: string): string {
  return RARITY_TOKENS[rarityKey(rarity)].color
}

export function getRarityBorderClass(rarity?: string): string {
  return RARITY_TOKENS[rarityKey(rarity)].border
}

export function getRarityTextClass(rarity?: string): string {
  return RARITY_TOKENS[rarityKey(rarity)].text
}

// Stat rows shared by item cards
export interface ItemStat {
  label: string
  value: string | number
  icon: string
}

interface DamageSource {
  damage_min: number
  damage_max: number
}

export function getDamageRange(weapon: DamageSource): string {
  return `${weapon.damage_min}-${weapon.damage_max}`
}

// Outfit radiation resist, mirroring the backend mechanics map
// (backend/app/services/radiation_service.py): type base, specific names override.
const OUTFIT_RADIATION_RESIST_BY_TYPE: Record<string, number> = {
  power_armor: 0.75,
  common_outfit: 0,
}

const OUTFIT_RADIATION_RESIST_BY_NAME: Record<string, number> = {
  'hazmat suit': 1,
  'advanced hazmat suit': 1,
}

interface ResistSource {
  outfit_type?: string
  name?: string
  radiation_resist?: number | null
  fire_resist?: number | null
}

// An explicit share declared on the outfit wins; older rows without one keep
// the type/name fallback below (mirrors radiation_service.outfit_radiation_resist).
export function getOutfitRadiationResist(outfit: ResistSource): number {
  if (outfit.radiation_resist != null) return outfit.radiation_resist
  const byName = OUTFIT_RADIATION_RESIST_BY_NAME[outfit.name?.trim().toLowerCase() ?? '']
  if (byName !== undefined) return byName
  return OUTFIT_RADIATION_RESIST_BY_TYPE[outfit.outfit_type?.trim().toLowerCase() ?? ''] ?? 0
}

export function getOutfitFireResist(outfit: ResistSource): number {
  return outfit.fire_resist ?? 0
}

interface BonusSource {
  strength?: number
  perception?: number
  endurance?: number
  charisma?: number
  intelligence?: number
  agility?: number
  luck?: number
}

// Ordered SPECIAL keys; the capitalized key is the full stat name shown on cards.
const OUTFIT_BONUS_KEYS = [
  'strength',
  'perception',
  'endurance',
  'charisma',
  'intelligence',
  'agility',
  'luck',
] as const satisfies readonly (keyof BonusSource)[]

function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}

export function getOutfitBonuses(outfit: BonusSource): { stat: string; bonus: number }[] {
  const bonuses: { stat: string; bonus: number }[] = []
  for (const key of OUTFIT_BONUS_KEYS) {
    const bonus = outfit[key]
    if (bonus) bonuses.push({ stat: capitalize(key), bonus })
  }
  return bonuses
}

interface CommonItemStats {
  weight?: number
  durability?: number
}

interface WeaponStatsSource extends DamageSource, CommonItemStats {
  stat?: string
  accuracy?: number | null
  weapon_type?: string
  weapon_subtype?: string
}

export function getWeaponStats(weapon: WeaponStatsSource): ItemStat[] {
  const stats: ItemStat[] = [{ label: 'Damage', value: getDamageRange(weapon), icon: 'mdi:sword-cross' }]
  if (weapon.stat) stats.push({ label: 'Uses', value: weapon.stat.toUpperCase(), icon: 'mdi:alphabet-latin' })
  if (weapon.accuracy != null) stats.push({ label: 'Accuracy', value: `${weapon.accuracy}%`, icon: 'mdi:target' })
  if (weapon.weapon_type) stats.push({ label: 'Type', value: weapon.weapon_type, icon: 'mdi:tag' })
  if (weapon.weapon_subtype) {
    stats.push({ label: 'Subtype', value: capitalize(weapon.weapon_subtype), icon: 'mdi:tag-outline' })
  }
  if (weapon.weight !== undefined) stats.push({ label: 'Weight', value: weapon.weight, icon: 'mdi:scale' })
  if (weapon.durability !== undefined) stats.push({ label: 'Durability', value: weapon.durability, icon: 'mdi:shield-check' })
  return stats
}

interface OutfitStatsSource extends BonusSource, CommonItemStats, ResistSource {
  gender?: string | null
}

export function getOutfitStats(outfit: OutfitStatsSource): ItemStat[] {
  const stats: ItemStat[] = getOutfitBonuses(outfit).map((bonus) => ({
    label: bonus.stat,
    value: `+${bonus.bonus}`,
    icon: 'mdi:chevron-up',
  }))
  const resist = getOutfitRadiationResist(outfit)
  if (resist > 0) stats.push({ label: 'RAD resist', value: `${Math.round(resist * 100)}%`, icon: 'mdi:radiation' })
  const fireResist = getOutfitFireResist(outfit)
  if (fireResist > 0) stats.push({ label: 'Fire resist', value: `${Math.round(fireResist * 100)}%`, icon: 'mdi:fire' })
  if (outfit.gender) stats.push({ label: 'Gender', value: outfit.gender, icon: 'mdi:human-male-female' })
  if (outfit.weight !== undefined) stats.push({ label: 'Weight', value: outfit.weight, icon: 'mdi:scale' })
  if (outfit.durability !== undefined) stats.push({ label: 'Durability', value: outfit.durability, icon: 'mdi:shield-check' })
  return stats
}
