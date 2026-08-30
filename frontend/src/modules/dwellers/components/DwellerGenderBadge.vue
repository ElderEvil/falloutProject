<script setup lang="ts">
import { computed } from 'vue'
import DwellerBadge from './DwellerBadge.vue'
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

const GENDER_META: Record<Gender, { color: string; icon: string; label: string }> = {
  male: { color: '#60a5fa', icon: 'mdi:gender-male', label: 'Male' },
  female: { color: '#f472b6', icon: 'mdi:gender-female', label: 'Female' },
}

const gender = computed<Gender>(() => {
  const g = String(props.gender ?? '').toLowerCase()
  return g === 'male' || g === 'female' ? g : 'male'
})

const meta = computed(() => GENDER_META[gender.value])
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
