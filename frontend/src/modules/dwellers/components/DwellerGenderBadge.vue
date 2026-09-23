<script setup lang="ts">
import { computed } from 'vue'
import DwellerBadge from './DwellerBadge.vue'
import { GENDER_CONFIG_MAP } from '../models/dweller'
import type { components } from '@/core/types/api.generated'

type Gender = components['schemas']['GenderEnum']

const props = withDefaults(
  defineProps<{
    gender?: Gender | string | null
    showLabel?: boolean
    size?: 'sm' | 'md'
  }>(),
  { gender: null, showLabel: false, size: 'md' }
)

const meta = computed(() => {
  const g = String(props.gender ?? '').toLowerCase()
  return g === 'male' || g === 'female' ? GENDER_CONFIG_MAP[g] : null
})
</script>

<template>
  <DwellerBadge
    v-if="meta"
    :icon="meta.icon"
    :color="meta.color"
    :label="meta.label"
    :category="meta.category"
    :show-label="showLabel"
    :size="size"
  />
</template>
