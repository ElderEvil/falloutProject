<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import UTooltip from '@/core/components/ui/UTooltip.vue'

interface Props {
  current: number
  max: number
  icon: string // Icon name (e.g., 'mdi:lightning-bolt')
  label?: string
  productionRate?: number // Optional: production/consumption rate per minute
  tooltipInfo?: string // Optional: additional tooltip information
}

const props = defineProps<Props>()

const previousValue = ref(props.current)
const trend = ref<'up' | 'down' | 'stable'>('stable')
const showTrend = ref(false)

// Watch for changes in current value
watch(() => props.current, (newVal, oldVal) => {
  if (newVal > oldVal) {
    trend.value = 'up'
    showTrend.value = true
  } else if (newVal < oldVal) {
    trend.value = 'down'
    showTrend.value = true
  } else {
    trend.value = 'stable'
  }

  previousValue.value = newVal

  // Hide trend indicator after 2 seconds
  setTimeout(() => {
    showTrend.value = false
  }, 2000)
})

const percentage = computed(() => {
  if (props.max === 0) return 0
  return Math.min((props.current / props.max) * 100, 100)
})

const status = computed(() => {
  const pct = percentage.value
  if (pct <= 5) return 'critical'
  if (pct <= 20) return 'low'
  if (pct <= 50) return 'medium'
  return 'healthy'
})

const barColorStyle = computed(() => {
  // Bar fill color changes based on resource status
  switch (status.value) {
    case 'critical': return '#dc2626' // red-600
    case 'low': return '#f97316' // orange-500
    case 'medium': return '#eab308' // yellow-500
    default: return 'var(--color-theme-primary)' // Theme-aware
  }
})

const iconColor = computed(() => {
  switch (status.value) {
    case 'critical': return 'text-red-600 animate-pulse'
    case 'low': return 'text-orange-500'
    case 'medium': return 'text-yellow-500'
    default: return 'text-[var(--color-theme-primary)]'
  }
})

// Tooltip text with detailed information
const tooltipText = computed(() => {
  let text = `${props.label || 'Resource'}: ${props.current}/${props.max} (${percentage.value.toFixed(1)}%)`

  if (props.productionRate !== undefined) {
    const rateText = props.productionRate >= 0 ? `+${props.productionRate}` : `${props.productionRate}`
    text += `\nRate: ${rateText}/min`
  }

  if (props.tooltipInfo) {
    text += `\n${props.tooltipInfo}`
  }

  // Add status warning
  if (status.value === 'critical') {
    text += '\n⚠️ CRITICAL - Immediate action required!'
  } else if (status.value === 'low') {
    text += '\n⚠️ LOW - Attention needed'
  }

  return text
})

// ARIA label for accessibility
const ariaLabel = computed(() =>
  `${props.label || 'Resource'}: ${props.current} out of ${props.max}, ${percentage.value.toFixed(1)}% full, status: ${status.value}`
)
</script>

<template>
  <UTooltip :text="tooltipText" position="top">
    <div
      class="relative flex items-center space-x-2"
      role="meter"
      :aria-label="ariaLabel"
      :aria-valuenow="props.current"
      :aria-valuemin="0"
      :aria-valuemax="props.max"
      tabindex="0"
    >
      <Icon :icon="props.icon" class="h-8 w-8 transition-colors duration-300" :class="iconColor" aria-hidden="true" />

      <div class="relative">
        <div class="relative h-6 w-40 rounded-full border-2 border-gray-600 bg-gray-800 overflow-hidden">
          <!-- Filled part of the bar with smooth transition -->
          <div
            class="absolute top-0 left-0 h-full rounded-full transition-all duration-500 ease-out z-0"
            :style="{
              width: `${percentage}%`,
              backgroundColor: barColorStyle
            }"
            aria-hidden="true"
          ></div>

          <!-- Overlay with resource numbers -->
          <div class="absolute inset-0 flex items-center justify-center text-xs font-bold z-10" aria-hidden="true">
            <span class="text-gray-900 drop-shadow-[0_2px_4px_rgba(255,255,255,0.9)]"
                  style="text-shadow: 0 0 8px rgba(255,255,255,0.9), 0 0 4px rgba(255,255,255,0.8), 0 1px 2px rgba(0,0,0,0.8);">
              {{ props.current }}/{{ props.max }}
            </span>
          </div>
        </div>

      <!-- Trend Indicator -->
      <div
        v-if="showTrend && trend !== 'stable'"
        class="absolute -right-6 top-0 transition-opacity duration-300"
        :class="showTrend ? 'opacity-100' : 'opacity-0'"
      >
        <Icon
          v-if="trend === 'up'"
          icon="mdi:arrow-up"
          class="h-4 w-4 text-green-500 animate-bounce"
        />
        <Icon
          v-else-if="trend === 'down'"
          icon="mdi:arrow-down"
          class="h-4 w-4 text-red-500 animate-bounce"
        />
      </div>
    </div>

      <!-- Label (optional) -->
      <span v-if="label" class="text-xs text-gray-400" aria-hidden="true">{{ label }}</span>
    </div>
  </UTooltip>
</template>

<style scoped>
/* Additional styles if needed */
</style>
