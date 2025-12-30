<script setup lang="ts">
/**
 * UCard - Terminal-themed card component
 *
 * Features:
 * - Terminal green border
 * - Optional CRT screen effect
 * - Configurable padding
 * - Header and footer slots
 */

interface Props {
  title?: string
  padding?: 'none' | 'sm' | 'md' | 'lg' | 'xl'
  glow?: boolean
  crt?: boolean
  bordered?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  padding: 'md',
  glow: false,
  crt: false,
  bordered: true
})

const paddingClasses = {
  none: '',
  sm: 'p-4',
  md: 'p-6',
  lg: 'p-8',
  xl: 'p-10'
}

const cardClasses = [
  'bg-surface rounded-lg',
  props.bordered ? 'border-2 border-gray-800' : '',
  props.glow ? 'shadow-glow-md' : '',
  props.crt ? 'crt-screen' : '',
  paddingClasses[props.padding]
].filter(Boolean).join(' ')
</script>

<template>
  <div :class="cardClasses">
    <!-- Header Slot -->
    <div v-if="$slots.header || title" class="mb-4 border-b border-gray-700 pb-4">
      <slot name="header">
        <h3 class="text-xl font-bold text-terminalGreen terminal-glow">{{ title }}</h3>
      </slot>
    </div>

    <!-- Default Content Slot -->
    <slot></slot>

    <!-- Footer Slot -->
    <div v-if="$slots.footer" class="mt-4 border-t border-gray-700 pt-4">
      <slot name="footer"></slot>
    </div>
  </div>
</template>
