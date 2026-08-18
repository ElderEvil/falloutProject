<script setup lang="ts">
import { Icon } from '@iconify/vue'

defineProps<{
  canComplete: boolean
  isRecalling?: boolean
}>()

const emit = defineEmits<{
  complete: []
  recall: []
}>()
</script>

<template>
  <div class="grid grid-cols-1 gap-3 lg:grid-cols-2">
    <button
      v-if="canComplete"
      @click="emit('complete')"
      class="flex cursor-pointer items-center justify-center gap-2 rounded-md border-2 border-rarity-legendary bg-rarity-legendary/10 p-3.5 font-mono text-base font-bold text-rarity-legendary [text-shadow:0_0_10px_rgba(255,215,0,0.6)] transition-all duration-300 hover:scale-105 hover:bg-rarity-legendary/20 hover:shadow-[0_0_30px_rgba(255,215,0,0.5)]"
    >
      <Icon icon="mdi:check-circle" class="h-6 w-6" />
      Complete Exploration
    </button>
    <button
      @click="emit('recall')"
      class="flex cursor-pointer items-center justify-center gap-2 rounded-md border-2 border-[#ff4444] bg-[#ff4444]/10 p-3.5 font-mono text-base font-bold text-[#ff4444] [text-shadow:0_0_10px_rgba(255,68,68,0.6)] transition-all duration-300 hover:scale-105 hover:bg-[#ff4444]/20 hover:shadow-[0_0_30px_rgba(255,68,68,0.5)]"
    >
      <Icon icon="mdi:arrow-u-left-top" class="h-6 w-6" />
      Recall Dweller
    </button>
  </div>
</template>
