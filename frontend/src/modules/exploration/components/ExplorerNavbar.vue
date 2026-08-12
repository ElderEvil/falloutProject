<script setup lang="ts">
import { Icon } from '@iconify/vue'

defineProps<{
  currentIndex: number
  total: number
  hasPrevious: boolean
  hasNext: boolean
}>()

const emit = defineEmits<{
  back: []
  previous: []
  next: []
}>()
</script>

<template>
  <div
    class="sticky top-16 z-50 flex items-center justify-between border-b-[3px] border-theme-primary bg-surface-warm px-3 py-3 shadow-[0_2px_20px_var(--color-theme-glow)] sm:px-6 sm:py-4"
  >
    <button
      class="flex cursor-pointer items-center gap-2 rounded border-2 border-theme-primary bg-theme-primary/10 px-4 py-3 font-bold text-theme-primary [font-family:var(--font-family-mono)] [text-shadow:0_0_6px_var(--color-theme-glow)] transition duration-[var(--transition-base)] hover:scale-105 hover:bg-theme-primary/20 hover:shadow-[0_0_15px_var(--color-theme-glow)] focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-black"
      @click="emit('back')"
    >
      <Icon icon="mdi:arrow-left" />
      Back
    </button>
    <div class="font-bold text-theme-primary [text-shadow:0_0_10px_var(--color-theme-glow)] sm:text-xl">
      {{ currentIndex + 1 }} / {{ total }}
    </div>
    <div class="flex gap-2">
      <button
        @click="emit('previous')"
        class="flex cursor-pointer items-center gap-2 rounded border-2 border-theme-primary bg-theme-primary/10 px-4 py-3 text-2xl font-bold text-theme-primary [font-family:var(--font-family-mono)] [text-shadow:0_0_6px_var(--color-theme-glow)] transition duration-[var(--transition-base)] hover:scale-105 hover:bg-theme-primary/20 hover:shadow-[0_0_15px_var(--color-theme-glow)] focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-black disabled:cursor-not-allowed disabled:opacity-30"
        :disabled="!hasPrevious"
        :class="{ disabled: !hasPrevious }"
      >
        <Icon icon="mdi:chevron-left" />
      </button>
      <button
        @click="emit('next')"
        class="flex cursor-pointer items-center gap-2 rounded border-2 border-theme-primary bg-theme-primary/10 px-4 py-3 text-2xl font-bold text-theme-primary [font-family:var(--font-family-mono)] [text-shadow:0_0_6px_var(--color-theme-glow)] transition duration-[var(--transition-base)] hover:scale-105 hover:bg-theme-primary/20 hover:shadow-[0_0_15px_var(--color-theme-glow)] focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-black disabled:cursor-not-allowed disabled:opacity-30"
        :disabled="!hasNext"
        :class="{ disabled: !hasNext }"
      >
        <Icon icon="mdi:chevron-right" />
      </button>
    </div>
  </div>
</template>
