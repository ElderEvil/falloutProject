<script setup lang="ts">
import { computed } from 'vue'
import DwellerBadge from './DwellerBadge.vue'
import { AGE_CONFIG_MAP } from '../models/dweller'
import type { components } from '@/core/types/api.generated'

type AgeGroup = components['schemas']['AgeGroupEnum']

const props = withDefaults(
  defineProps<{
    ageGroup?: AgeGroup | string | null
    showLabel?: boolean
    size?: 'sm' | 'md'
  }>(),
  { ageGroup: null, showLabel: false, size: 'md' }
)

const group = computed<AgeGroup>(() => {
  const g = String(props.ageGroup ?? '').toLowerCase()
  return (g === 'child' || g === 'teen' || g === 'adult' || g === 'elder' ? g : 'adult') as AgeGroup
})

const meta = computed(() => AGE_CONFIG_MAP[group.value])
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
