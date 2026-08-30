<script setup lang="ts">
import { computed } from 'vue'
import DwellerBadge from './DwellerBadge.vue'
import type { components } from '@/core/types/api.generated'

type Rarity = components['schemas']['RarityEnum']

const props = withDefaults(
  defineProps<{
    rarity?: Rarity | string | null
    showLabel?: boolean
    size?: 'sm' | 'md'
  }>(),
  { rarity: null, showLabel: false, size: 'md' }
)

const RARITY_META: Record<Rarity, { color: string; icon: string; label: string }> = {
  common: { color: 'var(--color-rarity-common)', icon: 'mdi:star-outline', label: 'Common' },
  rare: { color: 'var(--color-rarity-rare)', icon: 'mdi:star', label: 'Rare' },
  legendary: {
    color: 'var(--color-rarity-legendary)',
    icon: 'mdi:star-four-points',
    label: 'Legendary',
  },
}

const rarity = computed<Rarity>(() => {
  const r = String(props.rarity ?? '').toLowerCase()
  return r === 'rare' || r === 'legendary' ? r : 'common'
})

const meta = computed(() => RARITY_META[rarity.value])
</script>

<template>
  <DwellerBadge
    :icon="meta.icon"
    :color="meta.color"
    :label="meta.label"
    :show-label="showLabel"
    :size="size"
  />
</template>
