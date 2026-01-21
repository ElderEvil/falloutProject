<script setup lang="ts">
/**
 * UTooltip - Terminal-themed tooltip component
 *
 * Features:
 * - Positioning options
 * - Hover and focus triggers
 * - Terminal green styling
 */

interface Props {
  text: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

const props = withDefaults(defineProps<Props>(), {
  position: 'top',
  delay: 200
})

import { ref } from 'vue'

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

const arrowClasses = {
  top: 'top-full left-1/2 -translate-x-1/2 border-t-terminalGreen',
  bottom: 'bottom-full left-1/2 -translate-x-1/2 border-b-terminalGreen',
  left: 'left-full top-1/2 -translate-y-1/2 border-l-terminalGreen',
  right: 'right-full top-1/2 -translate-y-1/2 border-r-terminalGreen'
}
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
          'bg-black text-terminalGreen',
          'px-3 py-2 rounded text-sm font-mono',
          'border border-terminalGreen',
          'shadow-[0_0_20px_rgba(0,255,0,0.4)]',
          'max-w-xs whitespace-pre-line',
          positionClasses[position]
        ]"
        role="tooltip"
      >
        {{ text }}

        <!-- Arrow -->
        <div
          :class="[
            'absolute w-0 h-0',
            'border-4 border-transparent',
            arrowClasses[position]
          ]"
        ></div>
      </div>
    </Transition>
  </div>
</template>

<style scoped>
.tooltip-enter-active,
.tooltip-leave-active {
  transition: opacity 0.2s ease;
}

.tooltip-enter-from,
.tooltip-leave-to {
  opacity: 0;
}
</style>
