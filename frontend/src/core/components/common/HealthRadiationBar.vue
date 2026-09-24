<script setup lang="ts">
import { computed } from 'vue'
import { cn } from '@/core/utils/cn'
import { METER_FRAME_TERMINAL, METER_TRACK_BASE } from '@/core/components/ui/progress/meter'

interface Props {
  /** Healthy fill, 0-100 */
  value: number
  /** Radiation segment 0-100, drawn after the fill (Shelter-style, eats into it) */
  radiation?: number
  /** Bar height in px */
  height?: number
  /** Container glow */
  glow?: boolean
  'aria-label'?: string
}

const { value, radiation = 0, height = 10, glow = false, 'aria-label': ariaLabel } = defineProps<Props>()

const clampedValue = computed(() => Math.min(100, Math.max(0, value)))
const radiationWidth = computed(() => Math.min(clampedValue.value, Math.max(0, radiation)))
const healthyWidth = computed(() => clampedValue.value - radiationWidth.value)

// The frame owns the recessed inset; the glow adds the outer ring on top of it.
const frameStyle = computed(() => ({
  height: `${height}px`,
  ...(glow
    ? { boxShadow: 'inset 0 0 8px var(--color-surface-canvas), 0 0 6px var(--color-theme-glow)' }
    : {}),
}))
</script>

<template>
  <div
    :class="cn(METER_TRACK_BASE, METER_FRAME_TERMINAL)"
    :style="frameStyle"
    role="progressbar"
    :aria-valuenow="clampedValue"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-label="ariaLabel"
  >
    <div class="health-radiation-bar__fill" :style="{ width: `${healthyWidth}%` }" />
    <div
      v-if="radiationWidth > 0"
      class="health-radiation-bar__radiation"
      :style="{ width: `${radiationWidth}%` }"
    />
  </div>
</template>

<style scoped>
.health-radiation-bar__fill {
  flex: 0 0 auto;
  height: 100%;
  background: linear-gradient(90deg, var(--color-theme-primary) 0%, var(--color-theme-accent) 100%);
  box-shadow: 0 0 8px var(--color-theme-glow);
  transition: width 0.3s ease;
}

.health-radiation-bar__radiation {
  flex: 0 0 auto;
  height: 100%;
  background: linear-gradient(90deg, var(--color-danger, #ef4444) 0%, rgb(153 27 27) 100%);
  box-shadow: 0 0 8px rgb(239 68 68 / 0.5);
  transition: width 0.3s ease;
}

@media (prefers-reduced-motion: reduce) {
  .health-radiation-bar__fill,
  .health-radiation-bar__radiation {
    transition: none;
  }
}
</style>
