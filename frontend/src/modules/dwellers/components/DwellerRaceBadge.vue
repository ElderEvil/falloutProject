<script setup lang="ts">
import { computed } from 'vue'
import DwellerBadge from './DwellerBadge.vue'
import { getRaceConfig } from '../models/dweller'

const props = withDefaults(
  defineProps<{
    race?: string | null
    showLabel?: boolean
    size?: 'sm' | 'md'
  }>(),
  { race: null, showLabel: false, size: 'md' }
)

const meta = computed(() => getRaceConfig(props.race))
</script>

<template>
  <!-- Race has no per-value colour token, so it stays theme-primary like the identity signal. -->
  <DwellerBadge
    v-if="race"
    :icon="meta.icon"
    color="var(--color-theme-primary)"
    :label="meta.label"
    :show-label="showLabel"
    :size="size"
  />
  <span v-else class="opacity-50">—</span>
</template>
