<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton, UCard } from '@/core/components/ui'
import { getStaticImageUrl } from '@/core/utils/image'

interface Props {
  item: any
  itemType: 'weapon' | 'outfit' | 'junk' | 'weapons' | 'outfits'
  count?: number
}

const { count = 1, item, itemType } = defineProps<Props>()

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

// Get detailed icon based on subtype
const itemIcon = computed(() => {
  if (normalizedItemType.value === 'weapon') {
    const subtype = item.weapon_subtype?.toString().toLowerCase()
    switch (subtype) {
      case 'pistol':
        return 'mdi:pistol'
      case 'rifle':
        return 'game-icons:rifle'
      case 'shotgun':
        return 'game-icons:shotgun'
      case 'automatic':
        return 'game-icons:machine-gun'
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

const imageError = ref(false)

watch(
  () => item.image_url,
  () => {
    imageError.value = false
  },
)

const itemImageUrl = computed(() => {
  if (imageError.value || !item.image_url) {
    return ''
  }
  return getStaticImageUrl(item.image_url)
})

function onImageError() {
  imageError.value = true
}

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
    padding="sm"
    :class="[
      'h-full w-full overflow-hidden font-mono transition-all duration-200 hover:-translate-y-0.5 hover:bg-surface-raised hover:shadow-glow-md',
      rarityBorderClass,
    ]"
  >
    <div class="flex h-full flex-col gap-3">
      <!-- Header: icon + name + count badge -->
      <div class="flex items-start gap-3">
        <img
          v-if="itemImageUrl"
          :src="itemImageUrl"
          :alt="itemName"
          class="h-16 w-16 shrink-0 object-contain drop-shadow-[0_0_4px_var(--color-theme-glow)]"
          @error="onImageError"
        />
        <Icon
          v-else
          :icon="itemIcon"
          class="h-16 w-16 shrink-0 text-(--color-theme-primary) drop-shadow-[0_0_4px_var(--color-theme-glow)]"
        />
        <div class="min-w-0 flex-1">
          <div class="flex items-center gap-1.5">
            <h3
              :class="[
                'truncate text-base font-bold drop-shadow-[0_0_4px_currentColor]',
                rarityTextClass,
              ]"
            >
              {{ itemName }}
            </h3>
            <span
              v-if="count > 1"
              class="inline-flex h-6 min-w-6 shrink-0 items-center justify-center rounded-full bg-(--color-theme-primary) px-2 text-xs font-bold text-black shadow-[0_0_6px_var(--color-theme-glow)]"
            >
              ×{{ count }}
            </span>
          </div>
          <p
            class="mt-1 truncate text-xs capitalize leading-tight text-(--color-theme-primary)/70"
          >
            {{ itemTypeDisplay }}
          </p>
        </div>
      </div>

      <p class="min-h-8 text-xs leading-4 text-(--color-theme-primary)/70">
        {{ itemDescription }}
      </p>

      <!-- Item stats -->
      <div
        v-if="itemStats.length > 0"
        class="grid grid-cols-2 gap-x-2 gap-y-1.5 rounded border border-theme-primary/15 bg-surface-sunken p-2 text-xs text-(--color-theme-primary)"
      >
        <div v-for="stat in itemStats" :key="stat.label" class="flex min-w-0 items-center gap-1.5">
          <Icon :icon="stat.icon" class="h-4 w-4 shrink-0" />
          <span class="truncate opacity-70">{{ stat.label }}:</span>
          <span class="font-bold">{{ stat.value }}</span>
        </div>
      </div>

      <!-- Footer: value + inventory actions -->
      <div
        class="mt-auto flex items-center justify-between gap-3 border-t border-(--color-theme-primary)/20 pt-2"
      >
        <div class="flex items-center gap-1.5 text-sm font-bold text-(--color-theme-primary)">
          <Icon icon="mdi:currency-usd" class="h-4 w-4 text-(--color-caps)" />
          <span>{{ itemValue }}</span>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <UButton
            variant="secondary"
            size="sm"
            @click="handleSell"
            :title="count > 1 ? 'Sell one' : 'Sell'"
            class="font-mono border-(--color-caps)! text-(--color-caps)! hover:bg-(--color-caps)/20!"
          >
            <Icon icon="mdi:cash" class="h-4 w-4" />
            Sell
          </UButton>
          <UButton
            v-if="canScrap"
            variant="secondary"
            size="sm"
            @click="handleScrap"
            title="Scrap"
            class="font-mono border-danger/60! text-danger! hover:bg-danger/15!"
          >
            <Icon icon="mdi:hammer-wrench" class="h-4 w-4" />
            Scrap
          </UButton>
          <UButton
            v-if="showSellAll"
            variant="primary"
            size="sm"
            @click="handleSellAll"
            :title="`Sell all (${count})`"
            class="font-mono border-(--color-caps)! bg-(--color-caps)/20! text-(--color-caps)! hover:bg-(--color-caps)/30!"
          >
            <Icon icon="mdi:cash-multiple" class="h-4 w-4" />
            Sell all
          </UButton>
        </div>
      </div>
    </div>
  </UCard>
</template>
