<script setup lang="ts">
import { computed } from 'vue'

interface Props {
  current: number
  max: number
  icon: string
  label?: string
}

const props = defineProps<Props>()

const percentage = computed(() => {
  if (props.max === 0) return 0
  return Math.min((props.current / props.max) * 100, 100)
})
</script>

<template>
  <div class="flex items-center space-x-2 border-2 border-primary-600 bg-black px-4 py-2">
    <UIcon :name="icon" class="h-6 w-6 text-primary-500 flex-shrink-0" />
    <div class="flex-1">
      <div v-if="label" class="text-xs text-primary-700 uppercase">{{ label }}</div>
      <div class="relative h-4 w-full rounded border border-primary-800 bg-black">
        <div class="h-full rounded bg-primary-500 transition-all" :style="{ width: `${percentage}%` }" />
        <div class="absolute inset-0 flex items-center justify-center">
          <span class="text-[10px] font-bold text-white drop-shadow-[0_1px_1px_rgba(0,0,0,0.8)]">
            {{ current }}/{{ max }}
          </span>
        </div>
      </div>
    </div>
  </div>
</template>
