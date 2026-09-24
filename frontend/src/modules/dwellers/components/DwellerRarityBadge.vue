<script setup lang="ts">
import { computed } from 'vue'
import DwellerBadge from './DwellerBadge.vue'
import { RARITY_CONFIG_MAP } from '../models/dweller'
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

const rarity = computed<Rarity>(() => {
  const r = String(props.rarity ?? '').toLowerCase()
  return r === 'rare' || r === 'legendary' ? r : 'common'
})

const meta = computed(() => RARITY_CONFIG_MAP[rarity.value])
</script>

<template>
  <DwellerBadge
    :icon="meta.icon"
    :color="meta.color"
    :label="meta.label"
    :category="meta.category"
    :show-label="showLabel"
    :size="size"
  />
</template>
