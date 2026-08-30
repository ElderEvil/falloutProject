<script setup lang="ts">
import { computed } from 'vue'
import DwellerBadge from './DwellerBadge.vue'
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

const AGE_META: Record<AgeGroup, { color: string; icon: string; label: string }> = {
  child: { color: '#38bdf8', icon: 'mdi:baby-face-outline', label: 'Child' },
  teen: { color: '#818cf8', icon: 'mdi:account-school', label: 'Teen' },
  adult: { color: '#4ade80', icon: 'mdi:account', label: 'Adult' },
}

const group = computed<AgeGroup>(() => {
  const g = String(props.ageGroup ?? '').toLowerCase()
  return (g === 'child' || g === 'teen' || g === 'adult' ? g : 'adult') as AgeGroup
})

const meta = computed(() => AGE_META[group.value])
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
