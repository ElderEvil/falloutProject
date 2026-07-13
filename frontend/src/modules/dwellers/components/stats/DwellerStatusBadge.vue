<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { getStatusConfig } from '../../models/dweller'
import type { DwellerStatus } from '../../stores/dweller'

interface Props {
  status: DwellerStatus | null
  size?: 'small' | 'medium' | 'large'
  showLabel?: boolean
}

const { size = 'small', showLabel = false, status } = defineProps<Props>()

const sizeClasses = computed(() => {
  switch (size) {
    case 'small':
      return {
        container: 'h-5 px-1.5',
        icon: 'h-3 w-3',
        text: 'text-xs',
      }
    case 'medium':
      return {
        container: 'h-6 px-2',
        icon: 'h-4 w-4',
        text: 'text-sm',
      }
    case 'large':
      return {
        container: 'h-7 px-2.5',
        icon: 'h-5 w-5',
        text: 'text-base',
      }
    default:
      return {
        container: 'h-5 px-1.5',
        icon: 'h-3 w-3',
        text: 'text-xs',
      }
  }
})
</script>

<template>
  <div
    class="status-badge inline-flex items-center gap-1 rounded border transition-all"
    :class="[
      getStatusConfig(status).color,
      getStatusConfig(status).bgColor,
      getStatusConfig(status).borderColor,
      sizeClasses.container,
      `hover:${getStatusConfig(status).glowColor}`,
    ]"
    :title="getStatusConfig(status).label"
  >
    <Icon :icon="getStatusConfig(status).icon" :class="sizeClasses.icon" />
    <span v-if="showLabel" :class="[sizeClasses.text, 'font-medium']">
      {{ getStatusConfig(status).label }}
    </span>
  </div>
</template>

<style scoped lang="css">
.status-badge {
  animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.8;
  }
}

.status-badge:hover {
  animation: none;
  opacity: 1 !important;
}
</style>
