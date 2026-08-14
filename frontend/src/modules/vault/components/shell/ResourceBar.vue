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
watch(
  () => props.current,
  (newVal, oldVal) => {
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
  }
)

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

const barColorClass = computed(() => {
  // Bar fill color changes based on resource status
  switch (status.value) {
    case 'critical':
      return 'bg-danger'
    case 'low':
      return 'bg-warning'
    case 'medium':
      return 'bg-yellow-500'
    default:
      return 'bg-theme-primary'
  }
})

const iconColor = computed(() => {
  switch (status.value) {
    case 'critical':
      return 'text-red-600 animate-pulse'
    case 'low':
      return 'text-orange-500'
    case 'medium':
      return 'text-yellow-500'
    default:
      return 'text-[var(--color-theme-primary)]'
  }
})

function formatForecast(minutes: number): string {
  const totalMinutes = Math.ceil(minutes)
  if (totalMinutes < 60) return `${totalMinutes} min`

  const hours = Math.floor(totalMinutes / 60)
  const remainingMinutes = totalMinutes % 60
  return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`
}

// Tooltip text with detailed information
const tooltipText = computed(() => {
  let text = `${props.label || 'Resource'}: ${props.current}/${props.max} (${percentage.value.toFixed(1)}%)`

  if (props.productionRate !== undefined) {
    const rateText =
      props.productionRate >= 0 ? `+${props.productionRate}` : `${props.productionRate}`
    text += `\nRate: ${rateText}/min`

    if (props.productionRate < 0 && props.current > 0) {
      text += `\nEstimated empty: ${formatForecast(props.current / -props.productionRate)}`
    } else if (props.productionRate > 0 && props.current < props.max) {
      text += `\nEstimated full: ${formatForecast((props.max - props.current) / props.productionRate)}`
    }
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
const ariaLabel = computed(
  () =>
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
      <Icon :icon="props.icon" class="h-8 w-8 transition-colors duration-300" :class="iconColor" />

      <div class="relative">
        <div
          class="relative h-6 w-40 rounded-full border-2 border-[#57534e] bg-[#292524] overflow-hidden"
        >
          <!-- Filled part of the bar with smooth transition -->
          <div
            class="absolute top-0 left-0 z-0 h-full rounded-full transition-all duration-500 ease-out"
            :class="barColorClass"
            :style="{
              width: `${percentage}%`,
            }"
            aria-hidden="true"
          ></div>

          <!-- Overlay with resource numbers -->
          <div
            class="absolute inset-0 flex items-center justify-center text-xs font-bold z-10"
            aria-hidden="true"
          >
            <span
              class="resource-value text-gray-900 drop-shadow-[0_2px_4px_rgba(255,255,255,0.9)]"
            >
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
.resource-value {
  text-shadow:
    0 0 8px rgba(255, 255, 255, 0.9),
    0 0 4px rgba(255, 255, 255, 0.8),
    0 1px 2px rgba(0, 0, 0, 0.8);
}
</style>
