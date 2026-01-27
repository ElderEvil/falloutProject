<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UCard, UButton } from '@/core/components/ui'

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

// Rarity-based Tailwind classes
const rarityBorderClass = computed(() => {
  switch (itemRarity.value) {
    case 'rare':
      return 'border-[--color-rarity-rare]'
    case 'legendary':
      return 'border-[--color-rarity-legendary]'
    default:
      return 'border-[--color-rarity-common]'
  }
})

const rarityTextClass = computed(() => {
  switch (itemRarity.value) {
    case 'rare':
      return 'text-[--color-rarity-rare]'
    case 'legendary':
      return 'text-[--color-rarity-legendary]'
    default:
      return 'text-[--color-rarity-common]'
  }
})
</script>

<template>
  <UCard
    :class="['transition-all duration-200 hover:bg-black/50 hover:-translate-y-0.5 hover:shadow-glow-md font-mono', rarityBorderClass]"
    padding="sm"
  >
    <div class="flex flex-col gap-3">
      <!-- Header -->
      <div class="flex items-center gap-3">
        <div class="w-10 h-10 flex items-center justify-center">
          <Icon :icon="itemIcon" class="w-10 h-10 text-[--color-theme-primary] drop-shadow-[0_0_4px_var(--color-theme-glow)]" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2">
            <h3 :class="['text-lg font-bold m-0 drop-shadow-[0_0_4px_currentColor]', rarityTextClass]">
              {{ itemName }}
            </h3>
            <span v-if="count > 1" class="inline-flex items-center justify-center min-w-[2rem] px-2 py-0.5 bg-[--color-theme-primary] text-black rounded-full text-xs font-bold shadow-[0_0_8px_var(--color-theme-glow)]">
              ×{{ count }}
            </span>
          </div>
          <p class="text-xs text-[--color-theme-primary] opacity-70 capitalize mt-1 m-0">
            {{ itemTypeDisplay }}
          </p>
        </div>
      </div>

      <!-- Description -->
      <p class="text-sm text-[--color-theme-primary] opacity-80 leading-normal m-0">
        {{ itemDescription }}
      </p>

      <!-- Stats -->
      <div v-if="itemStats.length > 0" class="flex flex-col gap-2 p-3 bg-black/30 rounded">
        <div v-for="stat in itemStats" :key="stat.label" class="flex items-center gap-2 text-sm">
          <Icon :icon="stat.icon" class="w-4 h-4 text-[--color-theme-primary]" />
          <span class="text-[--color-theme-primary] opacity-70">{{ stat.label }}:</span>
          <span class="text-[--color-theme-primary] font-bold ml-auto">{{ stat.value }}</span>
        </div>
      </div>

      <!-- Footer -->
      <div class="flex items-center justify-between gap-3 pt-3 border-t border-[--color-theme-glow]">
        <div class="flex items-center gap-1 text-[--color-theme-primary] font-bold text-base">
          <Icon icon="mdi:currency-usd" class="w-5 h-5 text-[--color-caps]" />
          <span>{{ itemValue }} caps</span>
        </div>
        <div class="flex items-center gap-2 flex-wrap">
          <UButton
            v-if="canScrap"
            variant="danger"
            size="sm"
            @click="handleScrap"
            title="Scrap for materials"
            class="font-mono"
          >
            <Icon icon="mdi:hammer-wrench" class="w-4 h-4" />
            <span>Scrap</span>
          </UButton>
          <div class="flex items-center gap-2 ml-auto">
            <UButton
              variant="secondary"
              size="sm"
              @click="handleSell"
              :title="count > 1 ? 'Sell one item' : 'Sell this item'"
              class="font-mono !text-[--color-caps] !border-[--color-caps] hover:!bg-[--color-caps]/20"
            >
              <Icon icon="mdi:cash" class="w-4 h-4" />
              <span>Sell{{ count > 1 ? ' One' : '' }}</span>
            </UButton>
            <UButton
              v-if="showSellAll"
              variant="primary"
              size="sm"
              @click="handleSellAll"
              title="Sell all items of this type"
              class="font-mono !bg-[--color-caps]/20 !text-[--color-caps] !border-[--color-caps] hover:!bg-[--color-caps]/30 font-extrabold"
            >
              <Icon icon="mdi:cash-multiple" class="w-4 h-4" />
              <span>Sell All ({{ count }})</span>
            </UButton>
          </div>
        </div>
      </div>
    </div>
  </UCard>

</template>
