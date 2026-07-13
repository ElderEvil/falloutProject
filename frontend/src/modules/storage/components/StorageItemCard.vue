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

const { count = 1, ids, getRarityColor, item, itemType } = defineProps<Props>()

const emit = defineEmits<{
  sell: []
  sellAll: []
  scrap: []
}>()

// Normalize item type (handle plural forms)
const normalizedItemType = computed(() => {
  if (itemType === 'weapons') return 'weapon'
  if (itemType === 'outfits') return 'outfit'
  return itemType
})

// Get item display name
const itemName = computed(() => {
  return item.name || 'Unknown Item'
})

// Get item description
const itemDescription = computed(() => {
  return item.description || 'No description available'
})

// Get item value
const itemValue = computed(() => {
  return item.value || 0
})

// Get item rarity
const itemRarity = computed(() => {
  return item.rarity || 'common'
})

// Get item type badge
const itemTypeBadge = computed(() => {
  if (itemType === 'weapon' && item.weapon_type && item.weapon_subtype) {
    return `${item.weapon_type} - ${item.weapon_subtype}`
  }
  return null
})

// Get detailed icon based on subtype
const itemIcon = computed(() => {
  if (normalizedItemType.value === 'weapon') {
    const subtype = item.weapon_subtype?.toString().toLowerCase()
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
    const outfitType = item.outfit_type?.toString().toLowerCase()
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
    return `${item.weapon_subtype || ''} • ${itemRarity.value}`
  } else if (normalizedItemType.value === 'outfit') {
    return `${item.outfit_type || ''} • ${itemRarity.value}`
  }
  return itemRarity.value
})

// Get item stats in vertical format (matching WeaponCard/OutfitCard)
const itemStats = computed(() => {
  const stats: Array<{ label: string; value: string | number; icon: string }> = []

  if (normalizedItemType.value === 'weapon') {
    // Damage range
    if (item.damage_min !== undefined && item.damage_max !== undefined) {
      stats.push({
        label: 'Damage',
        value: `${item.damage_min}-${item.damage_max}`,
        icon: 'mdi:sword-cross',
      })
    }
    // SPECIAL stat
    if (item.stat) {
      stats.push({
        label: 'Uses',
        value: item.stat.toUpperCase(),
        icon: 'mdi:alphabet-latin',
      })
    }
    // Weapon type
    if (item.weapon_type) {
      stats.push({
        label: 'Type',
        value: item.weapon_type,
        icon: 'mdi:tag',
      })
    }
    // Optional extra stats
    if (item.weight !== undefined) {
      stats.push({ label: 'Weight', value: item.weight, icon: 'mdi:scale' })
    }
    if (item.durability !== undefined) {
      stats.push({ label: 'Durability', value: item.durability, icon: 'mdi:shield-check' })
    }
  } else if (normalizedItemType.value === 'outfit') {
    // Gender restriction
    if (item.gender) {
      stats.push({
        label: 'Gender',
        value: item.gender,
        icon: 'mdi:human-male-female',
      })
    }
    if (item.weight !== undefined) {
      stats.push({ label: 'Weight', value: item.weight, icon: 'mdi:scale' })
    }
    if (item.durability !== undefined) {
      stats.push({ label: 'Durability', value: item.durability, icon: 'mdi:shield-check' })
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
  return count > 1 && normalizedItemType.value === 'junk'
})

// Rarity-based Tailwind classes
const rarityBorderClass = computed(() => {
  switch (itemRarity.value) {
    case 'rare':
      return 'border-(--color-rarity-rare)'
    case 'legendary':
      return 'border-(--color-rarity-legendary)'
    default:
      return 'border-(--color-rarity-common)'
  }
})

const rarityTextClass = computed(() => {
  switch (itemRarity.value) {
    case 'rare':
      return 'text-(--color-rarity-rare)'
    case 'legendary':
      return 'text-(--color-rarity-legendary)'
    default:
      return 'text-(--color-rarity-common)'
  }
})
</script>

<template>
  <UCard
    :ui="{
      root: 'bg-black/90 ring-1 ring-(--color-theme-primary)/20',
      body: 'p-3 sm:p-3',
    }"
    :class="[
      'w-full transition-all duration-200 hover:bg-black/50 hover:-translate-y-0.5 hover:shadow-glow-md font-mono overflow-hidden',
      rarityBorderClass,
    ]"
  >
    <div class="flex flex-col gap-2">
      <!-- Header: icon + name + count badge -->
      <div class="flex items-center gap-2.5">
        <Icon
          :icon="itemIcon"
          class="w-11 h-11 shrink-0 text-(--color-theme-primary) drop-shadow-[0_0_4px_var(--color-theme-glow)]"
        />
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-1.5">
            <h3
              :class="[
                'text-sm font-bold truncate drop-shadow-[0_0_4px_currentColor]',
                rarityTextClass,
              ]"
            >
              {{ itemName }}
            </h3>
            <span
              v-if="count > 1"
              class="shrink-0 inline-flex items-center justify-center min-w-[1.4rem] h-5 px-1.5 bg-(--color-theme-primary) text-black rounded-full text-[11px] font-bold shadow-[0_0_6px_var(--color-theme-glow)]"
            >
              ×{{ count }}
            </span>
          </div>
          <p
            class="text-xs text-(--color-theme-primary) opacity-70 capitalize truncate leading-tight mt-0.5"
          >
            {{ itemTypeDisplay }}
          </p>
        </div>
      </div>

      <!-- Stats inline -->
      <div
        v-if="itemStats.length > 0"
        class="flex flex-wrap gap-x-3 gap-y-0.5 text-xs text-(--color-theme-primary) leading-tight"
      >
        <div v-for="stat in itemStats" :key="stat.label" class="flex items-center gap-1">
          <Icon :icon="stat.icon" class="w-3.5 h-3.5 shrink-0" />
          <span class="opacity-70">{{ stat.label }}:</span>
          <span class="font-bold">{{ stat.value }}</span>
        </div>
      </div>

      <!-- Footer: value + compact actions -->
      <div
        class="flex items-center justify-between gap-1.5 pt-2 border-t border-(--color-theme-primary)/20"
      >
        <div class="flex items-center gap-1 text-(--color-theme-primary) text-xs font-bold">
          <Icon icon="mdi:currency-usd" class="w-4 h-4 text-(--color-caps)" />
          <span>{{ itemValue }}</span>
        </div>
        <div class="flex items-center gap-1">
          <UButton
            v-if="canScrap"
            color="error"
            variant="solid"
            size="2xs"
            @click="handleScrap"
            title="Scrap"
            class="font-mono !px-1.5 !py-0.5 !text-[11px] !h-auto !min-h-0"
          >
            <Icon icon="mdi:hammer-wrench" class="w-3.5 h-3.5" />
          </UButton>
          <UButton
            color="primary"
            variant="outline"
            size="2xs"
            @click="handleSell"
            :title="count > 1 ? 'Sell one' : 'Sell'"
            class="font-mono !px-1.5 !py-0.5 !text-[11px] !h-auto !min-h-0 !text-(--color-caps) !border-(--color-caps) hover:!bg-(--color-caps)/20"
          >
            <Icon icon="mdi:cash" class="w-3.5 h-3.5" />
          </UButton>
          <UButton
            v-if="showSellAll"
            color="primary"
            variant="solid"
            size="2xs"
            @click="handleSellAll"
            title="Sell all ({{ count }})"
            class="font-mono !px-1.5 !py-0.5 !text-[11px] !h-auto !min-h-0 !bg-(--color-caps)/20 !text-(--color-caps) !border-(--color-caps) hover:!bg-(--color-caps)/30"
          >
            <Icon icon="mdi:cash-multiple" class="w-3.5 h-3.5" />
          </UButton>
        </div>
      </div>
    </div>
  </UCard>
</template>
