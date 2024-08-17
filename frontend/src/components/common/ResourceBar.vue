<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  current: number
  max: number
  icon: any // Changed from string to any to accept component
}

const props = defineProps<Props>()

const percentage = computed(() => {
  return Math.min((props.current / props.max) * 100, 100)
})
</script>

<template>
  <div class="relative flex items-center space-x-2">
    <component :is="icon" class="h-6 w-6 text-green-500" />

    <div class="relative h-4 w-32 rounded bg-gray-700">
      <!-- Filled part of the bar -->
      <div class="h-full rounded-l bg-green-500" :style="{ width: `${percentage}%` }"></div>
      <!-- Overlay with resource numbers, always visible -->
      <div class="absolute inset-0 flex items-center justify-center rounded text-xs text-white">
        <span>{{ current }}/{{ max }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Additional styles if needed */
</style>
