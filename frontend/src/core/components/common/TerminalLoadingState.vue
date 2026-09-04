<script setup lang="ts">
import { Icon } from '@iconify/vue'
import UCard from '@/core/components/ui/UCard.vue'

withDefaults(defineProps<{ message: string; fullHeight?: boolean }>(), { fullHeight: false })
</script>

<template>
  <div
    role="status"
    aria-live="polite"
    class="flex items-center justify-center p-8"
    :class="{ 'min-h-[60vh]': fullHeight }"
  >
    <UCard glow crt padding="lg">
      <div class="flex flex-col items-center gap-6">
        <Icon icon="mdi:loading" class="h-16 w-16 animate-spin text-theme-primary terminal-glow" />
        <p class="text-base text-theme-primary terminal-glow">{{ message }}</p>
        <div class="flex w-full max-w-75 flex-col gap-2">
          <div class="h-1 w-full rounded-sm bg-theme-primary/30 flicker" />
          <div class="h-1 w-3/4 rounded-sm bg-theme-primary/30 flicker-slow" />
          <div class="h-1 w-1/2 rounded-sm bg-theme-primary/30 flicker-random" />
        </div>
      </div>
    </UCard>
  </div>
</template>
