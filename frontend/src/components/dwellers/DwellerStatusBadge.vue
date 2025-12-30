<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { DwellerStatus } from '@/stores/dweller'

interface Props {
  status: DwellerStatus
  size?: 'small' | 'medium' | 'large'
  showLabel?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  size: 'small',
  showLabel: false
})

const statusConfig = computed(() => {
  switch (props.status) {
    case 'exploring':
      return {
        icon: 'mdi:compass-outline',
        label: 'Exploring',
        color: 'text-blue-400',
        bgColor: 'bg-blue-900/30',
        borderColor: 'border-blue-500/50',
        glowColor: 'shadow-blue-500/30'
      }
    case 'working':
      return {
        icon: 'mdi:hammer-wrench',
        label: 'Working',
        color: 'text-green-400',
        bgColor: 'bg-green-900/30',
        borderColor: 'border-green-500/50',
        glowColor: 'shadow-green-500/30'
      }
    case 'training':
      return {
        icon: 'mdi:dumbbell',
        label: 'Training',
        color: 'text-purple-400',
        bgColor: 'bg-purple-900/30',
        borderColor: 'border-purple-500/50',
        glowColor: 'shadow-purple-500/30'
      }
    case 'resting':
      return {
        icon: 'mdi:sleep',
        label: 'Resting',
        color: 'text-cyan-400',
        bgColor: 'bg-cyan-900/30',
        borderColor: 'border-cyan-500/50',
        glowColor: 'shadow-cyan-500/30'
      }
    case 'dead':
      return {
        icon: 'mdi:skull',
        label: 'Dead',
        color: 'text-red-400',
        bgColor: 'bg-red-900/30',
        borderColor: 'border-red-500/50',
        glowColor: 'shadow-red-500/30'
      }
    case 'idle':
      return {
        icon: 'mdi:coffee-outline',
        label: 'Idle',
        color: 'text-yellow-400',
        bgColor: 'bg-yellow-900/30',
        borderColor: 'border-yellow-500/50',
        glowColor: 'shadow-yellow-500/30'
      }
    default:
      return {
        icon: 'mdi:help-circle-outline',
        label: 'Unknown',
        color: 'text-gray-400',
        bgColor: 'bg-gray-900/30',
        borderColor: 'border-gray-500/50',
        glowColor: 'shadow-gray-500/30'
      }
  }
})

const sizeClasses = computed(() => {
  switch (props.size) {
    case 'small':
      return {
        container: 'h-5 px-1.5',
        icon: 'h-3 w-3',
        text: 'text-xs'
      }
    case 'medium':
      return {
        container: 'h-6 px-2',
        icon: 'h-4 w-4',
        text: 'text-sm'
      }
    case 'large':
      return {
        container: 'h-7 px-2.5',
        icon: 'h-5 w-5',
        text: 'text-base'
      }
    default:
      return {
        container: 'h-5 px-1.5',
        icon: 'h-3 w-3',
        text: 'text-xs'
      }
  }
})
</script>

<template>
  <div
    class="status-badge inline-flex items-center gap-1 rounded border transition-all"
    :class="[
      statusConfig.color,
      statusConfig.bgColor,
      statusConfig.borderColor,
      sizeClasses.container,
      `hover:${statusConfig.glowColor}`
    ]"
    :title="statusConfig.label"
  >
    <Icon :icon="statusConfig.icon" :class="sizeClasses.icon" />
    <span v-if="showLabel" :class="[sizeClasses.text, 'font-medium']">
      {{ statusConfig.label }}
    </span>
  </div>
</template>

<style scoped>
.status-badge {
  backdrop-filter: blur(4px);
  animation: pulse-glow 2s ease-in-out infinite;
}

@keyframes pulse-glow {
  0%, 100% {
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
