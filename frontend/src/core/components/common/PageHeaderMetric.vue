<script setup lang="ts">
import { computed } from 'vue'
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
  }>(),
  {
    tooltip: '',
    valueClass: '',
    compact: false,
  }
)

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
  cn(
    'h-4 w-4 shrink-0 text-theme-primary/70',
    props.compact && 'h-6 w-6 text-theme-primary'
  )
)

// The card is focusable only when it opens a tooltip: a focus stop that reveals
// nothing is a keyboard trap, not an affordance.
const cardClasses = computed(() =>
  cn(
    'min-w-28 flex-row items-center gap-2 rounded-md border border-theme-primary/20 bg-surface-sunken px-3 py-2 shadow-none ring-0',
    props.compact &&
      'min-w-0 rounded-none border-0 bg-transparent px-0 py-0 data-[size=sm]:gap-2 data-[size=sm]:py-0',
    props.tooltip && 'cursor-help'
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
        <Card size="sm" :class="cardClasses" v-bind="{ tabindex: '0' }">
          <Icon :icon="icon" :class="iconClasses" :ariaHidden="true" />
          <div class="min-w-0">
            <div :class="valueClasses">
              {{ value }}
            </div>
            <div :class="labelClasses">
              {{ label }}
            </div>
          </div>
        </Card>
      </TooltipTrigger>
      <TooltipContent side="bottom" class="whitespace-pre-line">{{ tooltip }}</TooltipContent>
    </Tooltip>
  </TooltipProvider>
  <Card v-else size="sm" :class="cardClasses">
    <Icon :icon="icon" :class="iconClasses" :ariaHidden="true" />
    <div class="min-w-0">
      <div :class="valueClasses">
        {{ value }}
      </div>
      <div :class="labelClasses">
        {{ label }}
      </div>
    </div>
  </Card>
</template>
