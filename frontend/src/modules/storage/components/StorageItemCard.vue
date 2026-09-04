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
  itemType: 'weapon' | 'outfit' | 'junk'
  count?: number
}

const { count = 1, item, itemType } = defineProps<Props>()

const emit = defineEmits<{
  sell: []
  sellAll: []
  scrap: []
}>()

const itemIcon = computed(() => getItemIcon(itemType, item as any))

const rarityBorderClass = computed(() => getRarityBorderClass((item as any).rarity))

const rarityTextClass = computed(() => getRarityTextClass((item as any).rarity))

const { imageUrl, onImageError } = useItemImage(() => (item as any).image_url)

const itemTypeDisplay = computed(() => {
  if (itemType === 'weapon') return `${(item as any).weapon_subtype || ''} • ${(item as any).rarity || 'common'}`
  if (itemType === 'outfit') return `${(item as any).outfit_type || ''} • ${(item as any).rarity || 'common'}`
  return (item as any).rarity || 'common'
})

const itemStats = computed(() =>
  itemType === 'weapon' ? getWeaponStats(item as any) : itemType === 'outfit' ? getOutfitStats(item as any) : []
)

const showSellAll = computed(() => count > 1 && itemType === 'junk')
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

      <div
        v-if="itemStats.length > 0"
        class="grid gap-1 rounded border border-theme-primary/15 bg-surface-sunken p-1.5 text-xs text-(--color-theme-primary)"
      >
        <div
          v-for="stat in itemStats"
          :key="stat.label"
          class="grid min-w-0 grid-cols-[auto_minmax(0,1fr)_auto] items-center gap-x-1.5 rounded-sm bg-surface-raised/40 px-2 py-1.5"
        >
          <Icon :icon="stat.icon" class="h-4 w-4 shrink-0" />
          <span class="truncate uppercase tracking-wide opacity-70">{{ stat.label }}:</span>
          <span class="whitespace-nowrap text-right font-bold tabular-nums">{{ stat.value }}</span>
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
            v-if="itemType !== 'junk'"
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
