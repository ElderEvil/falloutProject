<script setup lang="ts">
/**
 * UTooltip - Terminal-themed tooltip component
 *
 * The default slot receives `tooltipId` so the control can set
 * `aria-describedby` and expose the relationship to assistive technology.
 */
import { computed, ref, useId } from 'vue'

interface Props {
  text?: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

const { position = 'top', delay = 200, text } = defineProps<Props>()

const isVisible = ref(false)
const triggerRef = ref<HTMLElement | null>(null)
const tooltipId = useId()
let timeoutId: number | null = null

const show = () => {
  if (!text) return
  if (timeoutId !== null) clearTimeout(timeoutId)
  timeoutId = window.setTimeout(() => {
    isVisible.value = true
    timeoutId = null
  }, delay)
}

const hide = () => {
  if (timeoutId !== null) {
    clearTimeout(timeoutId)
    timeoutId = null
  }
  isVisible.value = false
}

const tooltipPositionStyle = computed(() => {
  const triggerElement = triggerRef.value?.firstElementChild as HTMLElement | null
  if (!triggerElement) return { top: '0px', left: '0px', zIndex: 'var(--z-index-tooltip)' }

  const rect = triggerElement.getBoundingClientRect()
  const positions = {
    top: [rect.top - 8, rect.left + rect.width / 2],
    bottom: [rect.bottom + 8, rect.left + rect.width / 2],
    left: [rect.top + rect.height / 2, rect.left - 8],
    right: [rect.top + rect.height / 2, rect.right + 8],
  }
  const transforms = {
    top: 'translateX(-50%) translateY(-100%)',
    bottom: 'translateX(-50%)',
    left: 'translateY(-50%) translateX(-100%)',
    right: 'translateY(-50%)',
  }
  const [top, left] = positions[position]

  return {
    top: `${top}px`,
    left: `${left}px`,
    zIndex: 'var(--z-index-tooltip)',
    transform: transforms[position],
  }
})

const arrowPositionClasses = {
  top: 'top-full left-1/2 -translate-x-1/2',
  bottom: 'bottom-full left-1/2 -translate-x-1/2',
  left: 'left-full top-1/2 -translate-y-1/2',
  right: 'right-full top-1/2 -translate-y-1/2',
}

const arrowBorderProperties = {
  top: 'borderTopColor',
  bottom: 'borderBottomColor',
  left: 'borderLeftColor',
  right: 'borderRightColor',
}

const arrowStyle = computed(() => ({
  [arrowBorderProperties[position]]: 'var(--color-theme-primary)',
}))
</script>

<template>
  <span
    ref="triggerRef"
    class="contents"
    @mouseenter="show"
    @mouseleave="hide"
    @focusin="show"
    @focusout="hide"
  >
    <slot :tooltip-id="tooltipId"></slot>
  </span>

  <Teleport to="body">
    <Transition name="tooltip">
      <div
        v-if="isVisible && text"
        :id="tooltipId"
        class="tooltip-content fixed pointer-events-none max-w-xs rounded bg-black px-3 py-2 font-mono text-sm whitespace-pre-line"
        :style="tooltipPositionStyle"
        role="tooltip"
      >
        {{ text }}

        <div
          :class="['absolute h-0 w-0 border-4 border-transparent', arrowPositionClasses[position]]"
          :style="arrowStyle"
        ></div>
      </div>
    </Transition>
  </Teleport>
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
