<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { RouterLink, type RouteLocationRaw } from 'vue-router'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'

interface Props {
  current: number
  max: number
  icon: string // Icon name (e.g., 'mdi:lightning-bolt')
  label?: string
  productionRate?: number // Optional: production/consumption rate per minute
  tooltipInfo?: string // Optional: additional tooltip information
  navbar?: boolean
  /** Route to the room that fixes this resource; makes the critical warning actionable. */
  criticalTo?: RouteLocationRaw
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

// Persistent warning: resource is draining and critically low
const isDrainingCritical = computed(
  () => (props.productionRate ?? 0) < 0 && (status.value === 'critical' || status.value === 'low')
)

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
      return 'text-theme-primary'
  }
})

function formatForecast(minutes: number): string {
  const totalMinutes = Math.ceil(minutes)
  if (totalMinutes < 60) return `${totalMinutes} min`

  const hours = Math.floor(totalMinutes / 60)
  const remainingMinutes = totalMinutes % 60
  return remainingMinutes ? `${hours}h ${remainingMinutes}m` : `${hours}h`
}

// Persistent, non-hover forecast for a resource that is draining toward empty.
const criticalForecast = computed(() => {
  const rate = props.productionRate
  if (!isDrainingCritical.value || rate === undefined || rate >= 0) return ''
  const label = props.label || 'Resource'
  if (props.current <= 0) return `${label} depleted`
  return `${label} empty in ~${formatForecast(props.current / -rate)}`
})

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

  if (isDrainingCritical.value) {
    text += '\n↓ Depleting - resource will run out!'
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
  <div class="flex items-center gap-2">
    <TooltipProvider :delay-duration="200">
      <Tooltip>
        <TooltipTrigger as-child>
          <div
            class="relative flex items-center space-x-2"
            role="meter"
            :aria-label="ariaLabel"
            :aria-valuenow="props.current"
            :aria-valuemin="0"
            :aria-valuemax="props.max"
            tabindex="0"
          >
            <Icon
              :icon="props.icon"
              class="h-8 w-8 transition-colors duration-300"
              :class="iconColor"
            />

            <div class="relative">
              <div
                class="relative h-6 rounded-full border-2 border-stone-600 bg-stone-800 overflow-hidden"
                :class="props.navbar ? 'w-20 xl:w-24 2xl:w-28' : 'w-40'"
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

              <!-- Trend Indicator (transient on change, persistent while draining) -->
              <div
                v-if="(showTrend && trend !== 'stable') || isDrainingCritical"
                class="absolute -right-6 top-0"
              >
                <Icon
                  v-if="isDrainingCritical || trend === 'down'"
                  icon="mdi:arrow-down"
                  class="h-4 w-4 text-red-500 animate-bounce"
                />
                <Icon
                  v-else-if="trend === 'up'"
                  icon="mdi:arrow-up"
                  class="h-4 w-4 text-green-500 animate-bounce"
                />
              </div>
            </div>

            <!-- Label (optional) -->
            <span v-if="label" class="text-xs text-gray-400" aria-hidden="true">{{ label }}</span>
          </div>
        </TooltipTrigger>
        <TooltipContent side="bottom" class="whitespace-pre-line">{{ tooltipText }}</TooltipContent>
      </Tooltip>
    </TooltipProvider>

    <!-- Persistent critical warning: the forecast must not live in a hover-only tooltip. -->
    <RouterLink
      v-if="criticalForecast && criticalTo"
      :to="criticalTo"
      class="critical-warning flex items-center gap-1 whitespace-nowrap rounded border border-danger/60 bg-danger/10 px-2 py-1 text-xs font-bold text-danger transition-colors hover:bg-danger/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
      :aria-label="`${criticalForecast} — open the production room`"
    >
      <Icon icon="mdi:alert" class="h-3.5 w-3.5" :ariaHidden="true" />
      <span>{{ criticalForecast }}</span>
    </RouterLink>
    <span
      v-else-if="criticalForecast"
      class="critical-warning flex items-center gap-1 whitespace-nowrap rounded border border-danger/60 bg-danger/10 px-2 py-1 text-xs font-bold text-danger"
    >
      <Icon icon="mdi:alert" class="h-3.5 w-3.5" :ariaHidden="true" />
      <span>{{ criticalForecast }}</span>
    </span>
  </div>
</template>

<style scoped>
.resource-value {
  text-shadow:
    0 0 8px rgba(255, 255, 255, 0.9),
    0 0 4px rgba(255, 255, 255, 0.8),
    0 1px 2px rgba(0, 0, 0, 0.8);
}
</style>
