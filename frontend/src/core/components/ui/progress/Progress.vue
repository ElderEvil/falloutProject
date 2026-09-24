<script setup lang="ts">
import type { ProgressRootProps } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import { computed } from 'vue'
import { reactiveOmit } from '@vueuse/core'
import { ProgressIndicator, ProgressRoot } from 'reka-ui'
import { cn } from '@/core/utils/cn'
import {
  METER_FRAME_TERMINAL,
  METER_SIZE_CLASS,
  METER_TICKS_CLASS,
  METER_TICKS_STYLE,
  METER_TRACK_BASE,
} from './meter'

type ProgressSize = 'xs' | 'sm' | 'md'
type ProgressTone = 'default' | 'info' | 'warning' | 'danger' | 'success'

const props = withDefaults(
  defineProps<
    ProgressRootProps & {
      class?: HTMLAttributes['class']
      /** Fixed height scale. `sm` is the historical 6px bar. */
      size?: ProgressSize
      /** Semantic fill tone. Ignored when `fill` is set. */
      tone?: ProgressTone
      /** Explicit CSS colour for a dynamic/domain fill; takes precedence over `tone`. */
      fill?: string
      /** Decorative terminal divisions. Never changes the announced value. */
      segmented?: boolean
      /** Accessible name for the meter. */
      label?: string
      /** Accessible value text, e.g. "45%". */
      valueText?: string
    }
  >(),
  {
    modelValue: 0,
    size: 'sm',
    tone: 'default',
    segmented: false,
  },
)

const delegatedProps = reactiveOmit(
  props,
  'class',
  'size',
  'tone',
  'fill',
  'segmented',
  'label',
  'valueText',
)

// Resolve through the theme tokens so a runtime palette swap re-resolves; an
// explicit `fill` wins over the tone.
const TONE_FILL: Record<ProgressTone, string> = {
  default: 'var(--primary)',
  info: 'var(--color-info)',
  warning: 'var(--color-warning)',
  danger: 'var(--color-destructive)',
  success: 'var(--color-success)',
}

const resolvedFill = computed(() => props.fill ?? TONE_FILL[props.tone])
</script>

<template>
  <!-- @vue-ignore -->
  <ProgressRoot
    data-slot="progress"
    v-bind="delegatedProps"
    :aria-label="label"
    :aria-valuetext="valueText"
    :style="{ '--progress-fill': resolvedFill }"
    :class="
      cn(
        METER_TRACK_BASE,
        METER_SIZE_CLASS[props.size],
        props.segmented && METER_FRAME_TERMINAL,
        props.class,
      )
    "
  >
    <!-- The `background` shorthand, not `bg-[…]`: a `fill` may be a gradient, and
         `background-color` silently drops one (rendering no fill at all). -->
    <!-- @vue-ignore -->
    <ProgressIndicator
      data-slot="progress-indicator"
      class="[background:var(--progress-fill)] size-full flex-1 transition-transform motion-reduce:transition-none"
      :style="`transform: translateX(-${100 - (props.modelValue ?? 0)}%);`"
    />
    <!-- @vue-ignore -->
    <div
      v-if="segmented"
      data-slot="progress-segments"
      aria-hidden="true"
      :class="METER_TICKS_CLASS"
      :style="METER_TICKS_STYLE"
    />
  </ProgressRoot>
</template>
