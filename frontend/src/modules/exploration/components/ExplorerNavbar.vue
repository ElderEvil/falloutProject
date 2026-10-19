<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'

withDefaults(
  defineProps<{
    currentIndex: number
    total: number
    hasPrevious: boolean
    hasNext: boolean
    canRecall?: boolean
  }>(),
  { canRecall: false }
)

const emit = defineEmits<{
  previous: []
  next: []
  recall: []
}>()
</script>

<template>
  <div class="explorer-navigation flex items-center">
    <Button
      v-if="canRecall"
      @click="emit('recall')"
      aria-label="Recall dweller"
      size="xs"
      class="h-8 mr-2 cursor-pointer border-theme-primary bg-theme-primary text-xs font-bold text-black hover:bg-theme-primary/80 focus-visible:ring-theme-primary focus-visible:ring-offset-2 focus-visible:ring-offset-black"
    >
      <Icon icon="mdi:arrow-u-left-top" class="h-4 w-4" />
      <span>Recall</span>
    </Button>
    <div
      class="explorer-navigation-box flex items-center gap-3 rounded-md border border-theme-primary/40 bg-black/30 px-2.5 py-1"
    >
      <button
        @click="emit('previous')"
        aria-label="Previous explorer"
        class="flex h-8 w-8 cursor-pointer items-center justify-center rounded border border-theme-primary bg-theme-primary/10 p-0 text-xl font-bold text-theme-primary [text-shadow:0_0_6px_var(--color-theme-glow)] transition-transform duration-[var(--transition-base)] hover:scale-105 hover:bg-theme-primary/20 focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-black disabled:cursor-not-allowed disabled:opacity-30"
        :disabled="!hasPrevious"
        :class="{ disabled: !hasPrevious }"
      >
        <Icon icon="mdi:chevron-left" />
      </button>
      <div
        class="min-w-12 text-center font-bold text-theme-primary [text-shadow:0_0_10px_var(--color-theme-glow)]"
      >
        {{ currentIndex + 1 }} / {{ total }}
      </div>
      <button
        @click="emit('next')"
        aria-label="Next explorer"
        class="flex h-8 w-8 cursor-pointer items-center justify-center rounded border border-theme-primary bg-theme-primary/10 p-0 text-xl font-bold text-theme-primary [text-shadow:0_0_6px_var(--color-theme-glow)] transition-transform duration-[var(--transition-base)] hover:scale-105 hover:bg-theme-primary/20 focus:outline-none focus:ring-2 focus:ring-theme-primary focus:ring-offset-2 focus:ring-offset-black disabled:cursor-not-allowed disabled:opacity-30"
        :disabled="!hasNext"
        :class="{ disabled: !hasNext }"
      >
        <Icon icon="mdi:chevron-right" />
      </button>
    </div>
  </div>
</template>
