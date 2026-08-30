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

type IconSource = { weapon_subtype?: string; outfit_type?: string }

export function getItemIcon(itemType: string, item: IconSource): string {
  if (itemType === 'weapon') {
    return WEAPON_SUBTYPE_ICONS[item.weapon_subtype?.toLowerCase() ?? ''] ?? 'mdi:pistol'
  }
  if (itemType === 'outfit') {
    return OUTFIT_TYPE_ICONS[item.outfit_type?.toLowerCase() ?? ''] ?? 'mdi:tshirt-crew'
  }
  return JUNK_ICON
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

interface BonusSource {
  strength_bonus?: number
  perception_bonus?: number
  endurance_bonus?: number
  charisma_bonus?: number
  intelligence_bonus?: number
  agility_bonus?: number
  luck_bonus?: number
}

export function getOutfitBonuses(outfit: BonusSource): { stat: string; bonus: number }[] {
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

interface CommonItemStats {
  weight?: number
  durability?: number
}

interface WeaponStatsSource extends DamageSource, CommonItemStats {
  stat?: string
  accuracy?: number | null
  weapon_type?: string
}

export function getWeaponStats(weapon: WeaponStatsSource): ItemStat[] {
  const stats: ItemStat[] = [{ label: 'Damage', value: getDamageRange(weapon), icon: 'mdi:sword-cross' }]
  if (weapon.stat) stats.push({ label: 'Uses', value: weapon.stat.toUpperCase(), icon: 'mdi:alphabet-latin' })
  if (weapon.accuracy != null) stats.push({ label: 'Accuracy', value: `${weapon.accuracy}%`, icon: 'mdi:target' })
  if (weapon.weapon_type) stats.push({ label: 'Type', value: weapon.weapon_type, icon: 'mdi:tag' })
  if (weapon.weight !== undefined) stats.push({ label: 'Weight', value: weapon.weight, icon: 'mdi:scale' })
  if (weapon.durability !== undefined) stats.push({ label: 'Durability', value: weapon.durability, icon: 'mdi:shield-check' })
  return stats
}

interface OutfitStatsSource extends BonusSource, CommonItemStats {
  gender?: string | null
}

export function getOutfitStats(outfit: OutfitStatsSource): ItemStat[] {
  const stats: ItemStat[] = getOutfitBonuses(outfit).map((bonus) => ({
    label: bonus.stat,
    value: `+${bonus.bonus}`,
    icon: 'mdi:chevron-up',
  }))
  if (outfit.gender) stats.push({ label: 'Gender', value: outfit.gender, icon: 'mdi:human-male-female' })
  if (outfit.weight !== undefined) stats.push({ label: 'Weight', value: outfit.weight, icon: 'mdi:scale' })
  if (outfit.durability !== undefined) stats.push({ label: 'Durability', value: outfit.durability, icon: 'mdi:shield-check' })
  return stats
}
