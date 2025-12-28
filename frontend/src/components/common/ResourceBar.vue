<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  current: number
  max: number
  icon: any
}

const props = defineProps<Props>()

const percentage = computed(() => {
  if (props.max === 0) return 0
  return Math.min((props.current / props.max) * 100, 100)
})
</script>

<template>
  <div class="relative flex items-center space-x-4">
    <component :is="props.icon" class="h-8 w-8 text-terminalGreen" />

    <div class="relative h-6 w-40 rounded-full border-2 border-gray-600 bg-gray-800">
      <!-- Filled part of the bar -->
      <div class="h-full rounded-full bg-terminalGreen" :style="{ width: `${percentage}%` }"></div>
      <!-- Overlay with resource numbers, always visible -->
      <div class="absolute inset-0 flex items-center justify-center text-xs font-bold text-black">
        <span>{{ props.current }}/{{ props.max }}</span>
      </div>
    </div>
  </div>
</template>

<style scoped>
/* Additional styles if needed */
</style>
