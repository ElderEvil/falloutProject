<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Weapon, Outfit } from '@/modules/combat/models/equipment'
import {
  getItemIcon,
  getOutfitStats,
  getRarityTextClass,
  getWeaponStats,
  type ItemStat,
} from '@/core/models/items'
import { useItemImage } from '@/core/composables/useItemImage'
import UButton from '@/core/components/ui/UButton.vue'

interface Props {
  item: Weapon | Outfit
  type: 'weapon' | 'outfit'
  showActions?: boolean
  equipped?: boolean
}

const { showActions = false, equipped = false, item, type } = defineProps<Props>()

const emit = defineEmits<{
  (e: 'equip'): void
  (e: 'unequip'): void
}>()

const itemIcon = computed(() => getItemIcon(type, item))

const rarityTextClass = computed(() => getRarityTextClass(item.rarity))

const stats = computed<ItemStat[]>(() => {
  const base = type === 'weapon' ? getWeaponStats(item as Weapon) : getOutfitStats(item as Outfit)
  return item.value != null ? [...base, { label: 'Value', value: item.value, icon: 'mdi:currency-usd' }] : base
})

const itemTypeLabel = computed(() =>
  type === 'weapon' ? (item as Weapon).weapon_subtype : (item as Outfit).outfit_type
)

const { imageUrl, onImageError } = useItemImage(() => item.image_url)
</script>

<template>
  <div
    class="equipment-card"
    :class="[
      'flex flex-col gap-3 rounded-lg border-2 p-4 transition-all duration-200',
      equipped
        ? 'border-[var(--color-theme-primary)] bg-black/50 shadow-[0_0_12px_var(--color-theme-glow)]'
        : 'border-[var(--color-theme-glow)] bg-black/30 hover:border-[var(--color-theme-primary)] hover:bg-black/50 hover:-translate-y-0.5 hover:shadow-[0_4px_12px_var(--color-theme-glow)]',
    ]"
  >
    <div class="flex items-center gap-3">
      <img
        v-if="imageUrl"
        :src="imageUrl"
        :alt="item.name"
        class="h-16 w-16 object-contain"
        @error="onImageError"
      />
      <Icon v-else :icon="itemIcon" class="h-16 w-16 text-[var(--color-theme-primary)]" />
      <div class="flex-1">
        <h4 class="text-lg font-bold text-shadow-[0_0_4px_currentColor]" :class="rarityTextClass">
          {{ item.name }}
        </h4>
        <p class="text-xs capitalize text-[var(--color-theme-primary)] opacity-70">
          {{ itemTypeLabel }} • {{ item.rarity }}
        </p>
      </div>
    </div>

    <p class="text-sm leading-snug text-[var(--color-theme-primary)] opacity-80">{{ item.description }}</p>

    <div
      v-if="stats.length > 0"
      class="grid grid-cols-2 gap-x-2 gap-y-1.5 rounded bg-black/30 p-3 text-sm text-[var(--color-theme-primary)]"
    >
      <div v-for="stat in stats" :key="stat.label" class="flex min-w-0 items-center gap-2">
        <Icon :icon="stat.icon" class="h-4 w-4 shrink-0" />
        <span class="truncate opacity-70">{{ stat.label }}:</span>
        <span class="ml-auto font-bold">{{ stat.value }}</span>
      </div>
    </div>

    <div v-if="showActions" class="flex gap-2">
      <UButton
        v-if="!equipped"
        block
        variant="secondary"
        @click="emit('equip')"
      >
        <Icon icon="mdi:check" />
        Equip
      </UButton>
      <UButton
        v-else
        block
        variant="danger"
        @click="emit('unequip')"
      >
        <Icon icon="mdi:close" />
        Unequip
      </UButton>
    </div>
  </div>
</template>
