<script setup lang="ts">
/**
 * UTooltip - Terminal-themed tooltip component
 *
 * Features:
 * - Positioning options
 * - Hover and focus triggers
 * - Theme-aware styling (uses CSS variables)
 */
import { ref, computed } from 'vue'

interface Props {
  text: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

const props = withDefaults(defineProps<Props>(), {
  position: 'top',
  delay: 200
})

const isVisible = ref(false)
let timeoutId: number | null = null

const show = () => {
  timeoutId = window.setTimeout(() => {
    isVisible.value = true
  }, props.delay)
}

const hide = () => {
  if (timeoutId) {
    clearTimeout(timeoutId)
    timeoutId = null
  }
  isVisible.value = false
}

const positionClasses = {
  top: 'bottom-full left-1/2 -translate-x-1/2 mb-2',
  bottom: 'top-full left-1/2 -translate-x-1/2 mt-2',
  left: 'right-full top-1/2 -translate-y-1/2 mr-2',
  right: 'left-full top-1/2 -translate-y-1/2 ml-2'
}

const arrowPositionClasses = {
  top: 'top-full left-1/2 -translate-x-1/2',
  bottom: 'bottom-full left-1/2 -translate-x-1/2',
  left: 'left-full top-1/2 -translate-y-1/2',
  right: 'right-full top-1/2 -translate-y-1/2'
}

const arrowStyle = computed(() => {
  const borderColor = 'var(--color-theme-primary)'
  switch (props.position) {
    case 'top': return { borderTopColor: borderColor }
    case 'bottom': return { borderBottomColor: borderColor }
    case 'left': return { borderLeftColor: borderColor }
    case 'right': return { borderRightColor: borderColor }
    default: return { borderTopColor: borderColor }
  }
})
</script>

<template>
  <div class="relative inline-block">
    <!-- Trigger Element -->
    <div
      @mouseenter="show"
      @mouseleave="hide"
      @focus="show"
      @blur="hide"
    >
      <slot></slot>
    </div>

    <!-- Tooltip -->
    <Transition name="tooltip">
      <div
        v-if="isVisible"
        :class="[
          'absolute z-tooltip',
          'bg-black',
          'px-3 py-2 rounded text-sm font-mono',
          'max-w-xs whitespace-pre-line',
          positionClasses[position]
        ]"
        class="tooltip-content"
        role="tooltip"
      >
        {{ text }}

        <!-- Arrow -->
        <div
          :class="[
            'absolute w-0 h-0',
            'border-4 border-transparent',
            arrowPositionClasses[position]
          ]"
          :style="arrowStyle"
        ></div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.tooltip-content {
  color: var(--color-theme-primary);
  border: 1px solid var(--color-theme-primary);
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.tooltip-enter-active,
.tooltip-leave-active {
  transition: opacity 0.2s ease;
}

.tooltip-enter-from,
.tooltip-leave-to {
  opacity: 0;
}
</style>
