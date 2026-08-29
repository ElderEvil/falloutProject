<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UButton, UCard } from '@/core/components/ui'
import {
  getItemIcon,
  getOutfitStats,
  getRarityBorderClass,
  getRarityTextClass,
  getWeaponStats,
} from '@/core/models/items'
import { useItemImage } from '@/core/composables/useItemImage'

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

const itemIcon = computed(() => getItemIcon(normalizedItemType.value, item))

const rarityBorderClass = computed(() => getRarityBorderClass(item.rarity))

const rarityTextClass = computed(() => getRarityTextClass(item.rarity))

const { imageUrl, onImageError } = useItemImage(() => item.image_url)

// Format weapon/outfit type for display
const itemTypeDisplay = computed(() => {
  if (normalizedItemType.value === 'weapon') {
    return `${item.weapon_subtype || ''} • ${item.rarity || 'common'}`
  } else if (normalizedItemType.value === 'outfit') {
    return `${item.outfit_type || ''} • ${item.rarity || 'common'}`
  }
  return item.rarity || 'common'
})

// Unified stat rows (shared with EquipmentCard)
const itemStats = computed(() => {
  if (normalizedItemType.value === 'weapon') return getWeaponStats(item)
  if (normalizedItemType.value === 'outfit') return getOutfitStats(item)
  return []
})

// Show scrap button only for weapons and outfits
const canScrap = computed(() => {
  return normalizedItemType.value === 'weapon' || normalizedItemType.value === 'outfit'
})

// Show sell all button only for junk items and when there are multiple copies
const showSellAll = computed(() => {
  return count > 1 && normalizedItemType.value === 'junk'
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
          v-if="imageUrl"
          :src="imageUrl"
          :alt="item.name || 'Unknown Item'"
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
              {{ item.name || 'Unknown Item' }}
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
        {{ item.description || 'No description available' }}
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
          <span>{{ item.value || 0 }}</span>
        </div>
        <div class="flex flex-wrap justify-end gap-2">
          <UButton
            variant="secondary"
            size="sm"
            @click="emit('sell')"
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
            @click="emit('scrap')"
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
            @click="emit('sellAll')"
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
