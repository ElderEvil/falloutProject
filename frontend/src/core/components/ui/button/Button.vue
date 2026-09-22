<script setup lang="ts">
import type { PrimitiveProps } from 'reka-ui'
import type { HTMLAttributes } from 'vue'
import type { ButtonVariants } from '.'
import { computed, useAttrs } from 'vue'
import { Primitive } from 'reka-ui'
import { cn } from '@/core/utils/cn'
import { buttonVariants } from '.'

interface Props extends PrimitiveProps {
  variant?: ButtonVariants['variant']
  size?: ButtonVariants['size']
  class?: HTMLAttributes['class']
  disabled?: boolean
  'aria-label'?: string
  ariaLabel?: string
  'aria-expanded'?: boolean
  ariaExpanded?: boolean
  title?: string
  type?: string
}

const props = withDefaults(defineProps<Props>(), {
  as: 'button',
})

const emit = defineEmits<{
  (e: 'click', event: MouseEvent): void
}>()

// A single `<Primitive>` root (no leading `@vue-ignore` comment) keeps this
// component composable with Reka `asChild` triggers such as TooltipTrigger,
// which resolve the child's `$el` and inject pointer/focus handlers. Every
// attribute is passed through one v-bind object so `strictTemplates` still
// accepts the extra data-/aria- attributes on `Primitive`.
const attrs = useAttrs()
const rootAttrs = computed<Record<string, unknown>>(() => ({
  'data-slot': 'button',
  'data-variant': props.variant,
  'data-size': props.size,
  disabled: props.disabled,
  type: props.type,
  'aria-label': props.ariaLabel ?? props['aria-label'],
  'aria-expanded': props.ariaExpanded ?? props['aria-expanded'],
  title: props.title,
  onClick: (event: MouseEvent) => emit('click', event),
  class: cn(buttonVariants({ variant: props.variant, size: props.size }), props.class),
  ...attrs,
}))
</script>

<template>
  <Primitive :as="as" :as-child="asChild" v-bind="rootAttrs">
    <slot />
  </Primitive>
</template>
