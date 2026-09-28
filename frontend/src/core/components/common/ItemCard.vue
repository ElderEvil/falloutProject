<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import {
  formatItemLabel,
  getOutfitStats,
  getRarityTextClass,
  getWeaponStats,
  type ItemCardSource,
  type ItemStat,
  type OutfitStatsSource,
  type WeaponStatsSource,
} from '@/core/models/items'
import ItemIcon from '@/core/components/common/ItemIcon.vue'

interface Props {
  item: ItemCardSource
  // Widened from 'weapon' | 'outfit' because StorageItemCard feeds junk/supplies
  // through this shell too; those item types simply produce no stats.
  itemType: string
  variant?: 'grid' | 'list'
  count?: number
  showValueAsStat?: boolean
}

const {
  item,
  itemType,
  variant = 'grid',
  count = 1,
  showValueAsStat = false,
} = defineProps<Props>()

const rarityTextClass = computed(() => getRarityTextClass(item.rarity ?? undefined))

const stats = computed<ItemStat[]>(() => {
  if (itemType !== 'weapon' && itemType !== 'outfit') return []
  const base =
    itemType === 'weapon'
      ? getWeaponStats(item as WeaponStatsSource)
      : getOutfitStats(item as OutfitStatsSource)
  return showValueAsStat && item.value != null
    ? [...base, { label: 'Value', value: item.value, icon: 'mdi:currency-usd' }]
    : base
})

const itemTypeDisplay = computed(() => {
  if (itemType === 'weapon') {
    return `${formatItemLabel(item.weapon_subtype)} • ${item.rarity ?? 'common'}`
  }
  if (itemType === 'outfit') {
    return `${formatItemLabel(item.outfit_type)} • ${item.rarity ?? 'common'}`
  }
  if (itemType === 'junk' && item.junk_type) {
    return `Junk • ${formatItemLabel(item.junk_type)} • ${item.rarity ?? 'common'}`
  }
  return `${formatItemLabel(itemType)} • ${item.rarity ?? 'common'}`
})
</script>

<template>
  <div class="flex flex-col gap-3">
    <!-- Header: icon + name + optional count badge + type/rarity subtitle -->
    <div v-if="variant === 'list'" class="flex items-center gap-3">
      <ItemIcon :item="item" :item-type="itemType" />
      <div class="min-w-0 flex-1">
        <h4
          class="truncate text-lg font-bold text-shadow-[0_0_4px_currentColor]"
          :class="rarityTextClass"
        >
          {{ item.name }}
        </h4>
        <p class="truncate text-xs capitalize text-theme-primary opacity-70">
          {{ itemTypeDisplay }}
        </p>
      </div>
    </div>
    <div v-else class="flex items-start gap-3">
      <ItemIcon
        :item="item"
        :item-type="itemType"
        imgClass="h-16 w-16 shrink-0 object-contain drop-shadow-[0_0_4px_var(--color-theme-glow)]"
        iconClass="h-16 w-16 shrink-0 text-(--color-theme-primary) drop-shadow-[0_0_4px_var(--color-theme-glow)]"
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
        <p class="mt-1 truncate text-xs capitalize leading-tight text-(--color-theme-primary)/70">
          {{ itemTypeDisplay }}
        </p>
      </div>
    </div>

    <!-- Description -->
    <p v-if="variant === 'list'" class="text-sm leading-snug text-theme-primary opacity-80">
      {{ item.description }}
    </p>
    <p v-else class="min-h-8 text-xs leading-4 text-(--color-theme-primary)/70">
      {{ item.description || 'No description available' }}
    </p>

    <!-- Stat block: vertical list (dweller) or 2-column grid (storage) -->
    <div
      v-if="stats.length > 0 && variant === 'list'"
      class="flex flex-col gap-1.5 rounded bg-black/30 p-3 text-sm text-theme-primary"
    >
      <div v-for="stat in stats" :key="stat.label" class="flex min-w-0 items-center gap-2">
        <Icon :icon="stat.icon" class="h-4 w-4 shrink-0" />
        <span class="truncate opacity-70">{{ stat.label }}:</span>
        <span class="ml-auto font-bold tabular-nums">{{ stat.value }}</span>
      </div>
    </div>
    <div
      v-else-if="stats.length > 0"
      class="grid grid-cols-2 gap-1 rounded border border-theme-primary/15 bg-surface-sunken p-1.5 text-xs text-(--color-theme-primary)"
    >
      <div
        v-for="stat in stats"
        :key="stat.label"
        class="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-1.5 rounded-sm bg-surface-raised/40 px-2 py-1.5"
      >
        <Icon :icon="stat.icon" class="h-4 w-4 shrink-0" />
        <span class="truncate uppercase tracking-wide opacity-70">{{ stat.label }}:</span>
        <span class="whitespace-nowrap text-right font-bold tabular-nums">{{ stat.value }}</span>
      </div>
    </div>

    <!-- Context-specific actions (equip/unequip, sell/scrap/open) -->
    <slot name="actions" />
  </div>
</template>
