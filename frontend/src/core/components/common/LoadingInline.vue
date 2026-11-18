<script setup lang="ts">
import { Icon } from '@iconify/vue'

/**
 * One loading presentation for inline feedback.
 * Standalone use announces a status; `decorative` is silent for buttons whose
 * own busy label already announces the state.
 */
withDefaults(defineProps<{ label?: string; decorative?: boolean }>(), {
  label: 'Loading…',
  decorative: false,
})
</script>

<template>
  <span v-if="decorative" aria-hidden="true" class="inline-flex items-center">
    <Icon icon="mdi:loading" class="animate-spin" />
  </span>
  <span v-else role="status" aria-live="polite" class="inline-flex items-center gap-2">
    <Icon icon="mdi:loading" class="animate-spin" :ariaHidden="true" />
    <span>{{ label }}</span>
  </span>
</template>
