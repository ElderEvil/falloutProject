<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'

interface Props {
  item: any
  itemType: 'weapon' | 'outfit' | 'junk' | 'weapons' | 'outfits'
  getRarityColor: (rarity?: string) => string
  count?: number
  ids?: string[]
}

const props = withDefaults(defineProps<Props>(), {
  count: 1,
  ids: () => []
})

const emit = defineEmits<{
  sell: []
  sellAll: []
  scrap: []
}>()

// Normalize item type (handle plural forms)
const normalizedItemType = computed(() => {
  if (props.itemType === 'weapons') return 'weapon'
  if (props.itemType === 'outfits') return 'outfit'
  return props.itemType
})

// Debug: Log item data on mount
console.log('[StorageItemCard] Item type:', props.itemType, '→ normalized:', normalizedItemType.value)
console.log('[StorageItemCard] Item fields:', Object.keys(props.item))
console.log('[StorageItemCard] weapon_subtype:', props.item.weapon_subtype)
console.log('[StorageItemCard] outfit_type:', props.item.outfit_type)

// Get item display name
const itemName = computed(() => {
  return props.item.name || 'Unknown Item'
})

// Get item description
const itemDescription = computed(() => {
  return props.item.description || 'No description available'
})

// Get item value
const itemValue = computed(() => {
  return props.item.value || 0
})

// Get item rarity
const itemRarity = computed(() => {
  return props.item.rarity || 'common'
})

// Get item type badge
const itemTypeBadge = computed(() => {
  if (props.itemType === 'weapon' && props.item.weapon_type && props.item.weapon_subtype) {
    return `${props.item.weapon_type} - ${props.item.weapon_subtype}`
  }
  return null
})

// Get detailed icon based on subtype
const itemIcon = computed(() => {
  if (normalizedItemType.value === 'weapon') {
    const subtype = props.item.weapon_subtype?.toString().toLowerCase()
    switch (subtype) {
      case 'pistol':
        return 'mdi:pistol'
      case 'rifle':
        return 'mdi:rifle'
      case 'shotgun':
        return 'mdi:shotgun'
      case 'automatic':
        return 'mdi:rifle'
      case 'explosive':
        return 'mdi:bomb'
      case 'flamer':
        return 'mdi:fire'
      case 'edged':
        return 'mdi:sword'
      case 'blunt':
        return 'mdi:hammer'
      case 'pointed':
        return 'mdi:spear'
      default:
        return 'mdi:pistol'
    }
  }

  if (normalizedItemType.value === 'outfit') {
    const outfitType = props.item.outfit_type?.toString().toLowerCase()
    switch (outfitType) {
      case 'power_armor':
        return 'mdi:robot'
      case 'legendary_outfit':
        return 'mdi:shield'
      case 'rare_outfit':
        return 'mdi:hard-hat'
      default:
        return 'mdi:tshirt-crew'
    }
  }

  // Junk items
  return 'mdi:wrench'
})

// Format weapon/outfit type for display
const itemTypeDisplay = computed(() => {
  if (normalizedItemType.value === 'weapon') {
    return `${props.item.weapon_subtype || ''} • ${itemRarity.value}`
  } else if (normalizedItemType.value === 'outfit') {
    return `${props.item.outfit_type || ''} • ${itemRarity.value}`
  }
  return itemRarity.value
})

// Get item stats in vertical format (matching WeaponCard/OutfitCard)
const itemStats = computed(() => {
  const stats: Array<{ label: string; value: string | number; icon: string }> = []

  if (normalizedItemType.value === 'weapon') {
    // Damage range
    if (props.item.damage_min !== undefined && props.item.damage_max !== undefined) {
      stats.push({
        label: 'Damage',
        value: `${props.item.damage_min}-${props.item.damage_max}`,
        icon: 'mdi:sword-cross'
      })
    }
    // SPECIAL stat
    if (props.item.stat) {
      stats.push({
        label: 'Uses',
        value: props.item.stat.toUpperCase(),
        icon: 'mdi:alphabet-latin'
      })
    }
    // Weapon type
    if (props.item.weapon_type) {
      stats.push({
        label: 'Type',
        value: props.item.weapon_type,
        icon: 'mdi:tag'
      })
    }
    // Optional extra stats
    if (props.item.weight !== undefined) {
      stats.push({ label: 'Weight', value: props.item.weight, icon: 'mdi:scale' })
    }
    if (props.item.durability !== undefined) {
      stats.push({ label: 'Durability', value: props.item.durability, icon: 'mdi:shield-check' })
    }
  } else if (normalizedItemType.value === 'outfit') {
    // Gender restriction
    if (props.item.gender) {
      stats.push({
        label: 'Gender',
        value: props.item.gender,
        icon: 'mdi:human-male-female'
      })
    }
    if (props.item.weight !== undefined) {
      stats.push({ label: 'Weight', value: props.item.weight, icon: 'mdi:scale' })
    }
    if (props.item.durability !== undefined) {
      stats.push({ label: 'Durability', value: props.item.durability, icon: 'mdi:shield-check' })
    }
  }

  return stats
})

const handleSell = () => {
  emit('sell')
}

const handleSellAll = () => {
  emit('sellAll')
}

const handleScrap = () => {
  emit('scrap')
}

// Show scrap button only for weapons and outfits
const canScrap = computed(() => {
  return normalizedItemType.value === 'weapon' || normalizedItemType.value === 'outfit'
})

// Show sell all button only for junk items and when there are multiple copies
const showSellAll = computed(() => {
  return props.count > 1 && normalizedItemType.value === 'junk'
})
</script>

<template>
  <div class="item-card" :style="{ borderColor: getRarityColor(itemRarity) }">
    <!-- Header -->
    <div class="item-header">
      <div class="item-icon-wrapper">
        <Icon :icon="itemIcon" class="item-icon" />
      </div>
      <div class="item-info">
        <div class="name-row">
          <h3 class="item-name" :style="{ color: getRarityColor(itemRarity) }">
            {{ itemName }}
          </h3>
          <span v-if="count > 1" class="count-badge">×{{ count }}</span>
        </div>
        <p class="item-type">{{ itemTypeDisplay }}</p>
      </div>
    </div>

    <!-- Description -->
    <p class="item-description">{{ itemDescription }}</p>

    <!-- Stats -->
    <div v-if="itemStats.length > 0" class="item-stats-section">
      <div class="stat-item" v-for="stat in itemStats" :key="stat.label">
        <Icon :icon="stat.icon" class="stat-icon" />
        <span class="stat-label">{{ stat.label }}:</span>
        <span class="stat-value">{{ stat.value }}</span>
      </div>
    </div>

    <!-- Footer -->
    <div class="item-footer">
      <div class="item-value">
        <Icon icon="mdi:currency-usd" class="caps-icon" />
        <span>{{ itemValue }} caps</span>
      </div>
      <div class="action-buttons">
        <button v-if="canScrap" class="scrap-btn" @click="handleScrap" title="Scrap for materials">
          <Icon icon="mdi:hammer-wrench" />
          <span>Scrap</span>
        </button>
        <div class="sell-buttons">
          <button class="sell-btn" @click="handleSell" :title="count > 1 ? 'Sell one item' : 'Sell this item'">
            <Icon icon="mdi:cash" />
            <span>Sell{{ count > 1 ? ' One' : '' }}</span>
          </button>
          <button v-if="showSellAll" class="sell-all-btn" @click="handleSellAll" title="Sell all items of this type">
            <Icon icon="mdi:cash-multiple" />
            <span>Sell All ({{ count }})</span>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.item-card {
  background: rgba(0, 0, 0, 0.3);
  border: 2px solid;
  border-radius: 8px;
  padding: 1rem;
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
}

.item-card:hover {
  background: rgba(0, 0, 0, 0.5);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px var(--color-theme-glow);
}

/* Header */
.item-header {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.item-icon-wrapper {
  width: 2.5rem;
  height: 2.5rem;
  display: flex;
  align-items: center;
  justify-content: center;
}

.item-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 4px var(--color-theme-glow));
}

.item-info {
  flex: 1;
  min-width: 0;
}

.name-row {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.item-name {
  font-size: 1.125rem;
  font-weight: 700;
  margin: 0;
  text-shadow: 0 0 4px currentColor;
}

.count-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 2rem;
  padding: 0.125rem 0.5rem;
  background: var(--color-theme-primary);
  color: #000;
  border-radius: 12px;
  font-size: 0.75rem;
  font-weight: 700;
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.item-type {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-transform: capitalize;
  margin: 0.25rem 0 0 0;
}

/* Description */
.item-description {
  font-size: 0.875rem;
  color: var(--color-theme-primary);
  opacity: 0.8;
  line-height: 1.4;
  margin: 0;
}

/* Stats Section (matching WeaponCard style) */
.item-stats-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.stat-icon {
  width: 1rem;
  height: 1rem;
  color: var(--color-theme-primary);
}

.stat-label {
  color: var(--color-theme-primary);
  opacity: 0.7;
}

.stat-value {
  color: var(--color-theme-primary);
  font-weight: 700;
  margin-left: auto;
}

/* Footer */
.item-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  padding-top: 0.75rem;
  border-top: 1px solid var(--color-theme-glow);
}

.item-value {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  color: var(--color-theme-primary);
  font-weight: 700;
  font-size: 1rem;
}

.caps-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: #ffd700;
}

.action-buttons {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  flex-wrap: wrap;
}

.sell-buttons {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  margin-left: auto;
}

.scrap-btn,
.sell-btn,
.sell-all-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem 1rem;
  border: 2px solid;
  border-radius: 4px;
  font-weight: 700;
  font-size: 0.875rem;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Courier New', monospace;
}

.scrap-btn {
  background: rgba(255, 87, 34, 0.1);
  border-color: #ff5722;
  color: #ff5722;
}

.scrap-btn:hover {
  background: rgba(255, 87, 34, 0.2);
  box-shadow: 0 0 15px rgba(255, 87, 34, 0.5);
  transform: scale(1.05);
}

.sell-btn {
  background: rgba(255, 215, 0, 0.1);
  border-color: #ffd700;
  color: #ffd700;
}

.sell-btn:hover {
  background: rgba(255, 215, 0, 0.2);
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.5);
  transform: scale(1.05);
}

.scrap-btn:active,
.sell-btn:active {
  transform: scale(0.98);
}

.sell-all-btn {
  background: rgba(255, 215, 0, 0.2);
  border-color: #ffd700;
  color: #ffd700;
  font-weight: 800;
}

.sell-all-btn:hover {
  background: rgba(255, 215, 0, 0.3);
  box-shadow: 0 0 20px rgba(255, 215, 0, 0.6);
  transform: scale(1.05);
}

.sell-all-btn:active {
  transform: scale(0.98);
}

.scrap-btn svg,
.sell-btn svg,
.sell-all-btn svg {
  width: 1rem;
  height: 1rem;
}
</style>
