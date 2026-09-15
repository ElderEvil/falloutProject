<script setup lang="ts">
/**
 * UTooltip - Terminal-themed tooltip component
 *
 * The default slot's element is cloned and receives the trigger listeners, so no
 * wrapper box is introduced and the wrapped control keeps its own root element
 * (its layout classes and root-level listeners keep working). The default slot
 * also receives `tooltipId` for controls that set their own `aria-describedby`.
 */
import { cloneVNode, computed, mergeProps, ref, useAttrs, useId, useSlots } from 'vue'

interface Props {
  text?: string
  position?: 'top' | 'bottom' | 'left' | 'right'
  delay?: number
}

const { position = 'top', delay = 200, text } = defineProps<Props>()

// Attrs are merged onto the cloned trigger, never auto-applied to the fragment root.
defineOptions({ inheritAttrs: false })

const slots = useSlots()
const attrs = useAttrs()
const tooltipId = useId()
const isVisible = ref(false)
const triggerEl = ref<Element | null>(null)
let timeoutId: number | null = null

/**
 * The cloned slot vnode may be a component (`UButton`, Iconify `Icon`, …), in which
 * case Vue hands the ref a component instance instead of an element — measuring that
 * directly throws and the tooltip never opens. Resolve to the rendered root element.
 */
const setTriggerEl = (value: unknown) => {
  const candidate = value instanceof Element ? value : (value as { $el?: unknown } | null)?.$el
  triggerEl.value = candidate instanceof Element ? candidate : null
}

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

// Trigger handlers live on the consumer's own element (no wrapper box), so the
// wrapped control stays the root: its classes and root-level listeners keep working.
const triggerVNode = computed(() => {
  const node = slots.default?.({ tooltipId })?.[0]
  if (!node) return null
  return cloneVNode(
    node,
    mergeProps(
      attrs,
      {
        ref: setTriggerEl,
        onMouseenter: show,
        onMouseleave: hide,
        onFocusin: show,
        onFocusout: hide,
      },
      text ? { 'aria-describedby': tooltipId } : {}
    )
  )
})

const tooltipPositionStyle = computed(() => {
  const triggerElement = triggerEl.value
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
  <component :is="triggerVNode" v-if="triggerVNode" />

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
