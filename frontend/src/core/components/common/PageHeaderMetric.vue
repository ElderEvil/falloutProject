<script setup lang="ts">
import { computed, useAttrs } from 'vue'
import { Icon } from '@iconify/vue'
import { Card } from '@/core/components/ui/card'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import { cn } from '@/core/utils/cn'

const props = withDefaults(
  defineProps<{
    label: string
    value: number | string
    icon: string
    tooltip?: string
    valueClass?: string
    compact?: boolean
    /** Turns the metric into a button: the label swaps to this action on hover. */
    hoverText?: string
    disabled?: boolean
  }>(),
  {
    tooltip: '',
    valueClass: '',
    compact: false,
    hoverText: '',
    disabled: false,
  }
)

const emit = defineEmits<{ click: [] }>()

const isInteractive = computed(() => Boolean(props.hoverText))

const interactiveAttrs = computed(() =>
  isInteractive.value
    ? {
        role: 'button',
        tabindex: props.disabled ? '-1' : '0',
        'aria-disabled': props.disabled ? 'true' : undefined,
        'aria-label': props.disabled
          ? `${props.label}: ${props.value}`
          : `${props.hoverText}: ${props.value}`,
      }
    : {}
)

// The tooltip branch is focusable so its content can be revealed from the
// keyboard; an interactive metric owns its own focus and role instead.
const rootAttrs = computed(() =>
  isInteractive.value
    ? { ...interactiveAttrs.value, onClick: handleClick, onKeydown: handleKeydown }
    : props.tooltip
      ? { tabindex: '0' }
      : {}
)

function handleClick(): void {
  if (!isInteractive.value || props.disabled) return
  emit('click')
}

function handleKeydown(event: KeyboardEvent): void {
  if (event.key !== 'Enter' && event.key !== ' ') return
  event.preventDefault()
  handleClick()
}

// Reka's TooltipProvider sets inheritAttrs: false, so a caller class would be
// swallowed on the tooltip branch — forward it to the Card explicitly. The
// plain branch keeps automatic fallthrough and stays untouched.
const attrs = useAttrs()

const labelClasses = computed(() =>
  cn(
    'mt-1 text-[0.65rem] font-bold uppercase leading-tight tracking-[0.1em] text-theme-primary/55',
    props.compact && 'sr-only'
  )
)

const valueClasses = computed(() =>
  cn(
    'page-header-metric-value whitespace-nowrap text-lg font-bold leading-none text-theme-primary',
    props.compact && 'text-base',
    props.valueClass
  )
)

const iconClasses = computed(() =>
  cn('h-4 w-4 shrink-0 text-theme-primary/70', props.compact && 'h-6 w-6 text-theme-primary')
)

// The card is focusable only when it opens a tooltip: a focus stop that reveals
// nothing is a keyboard trap, not an affordance.
const cardClasses = computed(() =>
  cn(
    'min-w-28 flex-row items-center gap-2 rounded-md border border-theme-primary/20 bg-surface-sunken px-3 py-2 shadow-none ring-0',
    props.compact &&
      'min-w-0 rounded-none border-0 bg-transparent px-0 py-0 data-[size=sm]:gap-2 data-[size=sm]:py-0',
    props.tooltip && !isInteractive.value && 'cursor-help',
    isInteractive.value &&
      (props.disabled
        ? 'opacity-60'
        : 'group cursor-pointer transition-colors hover:border-theme-primary/60')
  )
)
</script>

<template>
  <!--
    The tooltip branch is kept structurally separate from the plain branch on
    purpose: mounting TooltipTrigger unconditionally makes reka's `as-child`
    merge overwrite the Card's own `data-slot="card"` hook with
    `data-slot="tooltip-trigger"`, which would change the rendered DOM for every
    existing consumer. The long class literal is shared via `cardClasses`.
  -->
  <TooltipProvider v-if="tooltip" :delay-duration="200">
    <Tooltip>
      <TooltipTrigger as-child>
        <Card size="sm" :class="[cardClasses, attrs.class]" v-bind="rootAttrs">
          <Icon :icon="icon" :class="iconClasses" :ariaHidden="true" />
          <div class="min-w-0">
            <div :class="valueClasses">
              {{ value }}
            </div>
            <div :class="labelClasses">
              <span :class="isInteractive && !disabled && 'group-hover:hidden'">{{ label }}</span>
              <span v-if="isInteractive" :class="['hidden', !disabled && 'group-hover:inline']">{{
                hoverText
              }}</span>
            </div>
          </div>
        </Card>
      </TooltipTrigger>
      <TooltipContent side="bottom" class="whitespace-pre-line">{{ tooltip }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
  <Card v-else size="sm" :class="cardClasses" v-bind="rootAttrs">
    <Icon :icon="icon" :class="iconClasses" :ariaHidden="true" />
    <div class="min-w-0">
      <div :class="valueClasses">
        {{ value }}
      </div>
      <div :class="labelClasses">
        <span :class="isInteractive && !disabled && 'group-hover:hidden'">{{ label }}</span>
        <span v-if="isInteractive" :class="['hidden', !disabled && 'group-hover:inline']">{{
          hoverText
        }}</span>
      </div>
    </div>
  </Card>
</template>
