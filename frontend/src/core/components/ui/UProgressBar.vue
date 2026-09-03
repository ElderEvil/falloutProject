<script setup lang="ts">
import { computed } from 'vue'

/**
 * UProgressBar - Terminal-themed progress bar
 *
 * Reusable progress bar matching the terminal CRT aesthetic.
 * Used for health, happiness, XP, affinity, training, and more.
 *
 * Features:
 * - Configurable value (0-100)
 * - Optional radiation segment (0-100, stacked after the fill)
 * - Dynamic fill color
 * - Terminal glow border/shadow
 * - Optional pulse/shimmer/shine animations
 */
interface Props {
  /** Progress value 0-100 */
  modelValue?: number
  /** Radiation segment 0-100, eats into the fill Shelter-style so it stays visible at full HP */
  radiation?: number
  /** Bar height in px (default 10) */
  height?: number
  /** Fill color or gradient (CSS). Defaults to theme primary gradient */
  color?: string
  /** Show glow effect (default true) */
  glow?: boolean
  /** Animation variant */
  animation?: 'none' | 'pulse' | 'shimmer' | 'shine'
  /** Accessible description of the represented value */
  ariaLabel?: string
}

const { modelValue = 0, radiation = 0, height = 10, glow = true, animation = 'none', color, ariaLabel } = defineProps<Props>()

const clampedValue = computed(() => Math.min(100, Math.max(0, modelValue)))
const visibleRadiation = computed(() => Math.min(clampedValue.value, Math.max(0, radiation)))
const healthyWidth = computed(() => clampedValue.value - visibleRadiation.value)
</script>

<template>
  <div
    class="u-progress-bar u-progress-bar--sunken"
    :class="{
      'u-progress-bar--pulse': animation === 'pulse',
      'u-progress-bar--shimmer': animation === 'shimmer',
      'u-progress-bar--glow': glow,
    }"
    :style="{ height: `${height}px` }"
    role="progressbar"
    :aria-valuenow="clampedValue"
    aria-valuemin="0"
    aria-valuemax="100"
    :aria-label="ariaLabel"
  >
    <div
      class="u-progress-bar__fill"
      :class="{
        'u-progress-bar__fill--pulse': animation === 'pulse',
        'u-progress-bar__fill--shimmer': animation === 'shimmer',
        'u-progress-bar__fill--shine': animation === 'shine',
      }"
      :style="{
        width: `${healthyWidth}%`,
        ...(color ? { background: color } : {}),
      }"
    >
      <div v-if="animation === 'shine'" class="u-progress-bar__shine"></div>
    </div>
    <div
      v-if="visibleRadiation > 0"
      class="u-progress-bar__radiation"
      :style="{ width: `${visibleRadiation}%` }"
    ></div>
  </div>
</template>

<style scoped>
.u-progress-bar {
  display: flex;
  width: 100%;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-glow);
  border-radius: 999px;
  overflow: hidden;
  transition: box-shadow 0.3s ease;
}

.u-progress-bar--glow {
  box-shadow: 0 0 6px var(--color-theme-glow);
}

.u-progress-bar--pulse {
  border-color: rgb(250 204 21 / 0.8);
  box-shadow: 0 0 8px rgb(250 204 21 / 0.4);
  animation: u-progress-pulse 1.5s ease-in-out infinite;
}

.u-progress-bar--shimmer {
  border-color: rgb(250 204 21);
  box-shadow: 0 0 12px rgb(250 204 21 / 0.5);
}

.u-progress-bar__fill {
  flex: 0 0 auto;
  height: 100%;
  background: linear-gradient(90deg, var(--color-theme-primary) 0%, var(--color-theme-accent) 100%);
  box-shadow: 0 0 8px var(--color-theme-glow);
  transition: width 0.3s ease;
  border-radius: 0;
}

.u-progress-bar__fill--shimmer {
  background: linear-gradient(90deg, rgb(250 204 21) 0%, rgb(251 191 36) 50%, rgb(250 204 21) 100%);
  background-size: 200% 100%;
  animation: u-progress-shimmer 3s linear infinite;
}

.u-progress-bar__fill--pulse {
  background: linear-gradient(90deg, rgb(250 204 21) 0%, rgb(234 179 8) 50%, rgb(250 204 21) 100%);
}

.u-progress-bar__fill--shine {
  position: relative;
  overflow: hidden;
}

.u-progress-bar__radiation {
  flex: 0 0 auto;
  height: 100%;
  background: linear-gradient(90deg, var(--color-danger, #ef4444) 0%, rgb(153 27 27) 100%);
  box-shadow: 0 0 8px rgb(239 68 68 / 0.5);
  transition: width 0.3s ease;
}
.u-progress-bar__shine {
  position: absolute;
  top: 0;
  left: -100%;
  width: 100%;
  height: 100%;
  background: linear-gradient(
    90deg,
    transparent 0%,
    rgba(255, 255, 255, 0.25) 50%,
    transparent 100%
  );
  animation: u-progress-shine 3s ease-in-out infinite;
}

@keyframes u-progress-pulse {
  0%,
  100% {
    box-shadow: 0 0 8px rgb(250 204 21 / 0.4);
  }
  50% {
    box-shadow: 0 0 16px rgb(250 204 21 / 0.8);
  }
}

@keyframes u-progress-shimmer {
  0% {
    background-position: 200% 0;
  }
  100% {
    background-position: -200% 0;
  }
}

@keyframes u-progress-shine {
  0% {
    left: -100%;
  }
  50%,
  100% {
    left: 200%;
  }
}
</style>
