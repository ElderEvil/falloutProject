<script setup lang="ts">
/**
 * UBadge - Terminal-themed badge component
 *
 * Features:
 * - Color variants for different states
 * - Size options
 * - Icon support
 */

interface Props {
  variant?: 'success' | 'warning' | 'danger' | 'info' | 'default'
  size?: 'sm' | 'md' | 'lg'
  icon?: any
  dot?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'default',
  size: 'md',
  dot: false
})

const variantClasses = {
  success: 'bg-success text-black',
  warning: 'bg-warning text-black border-warning',
  danger: 'bg-danger text-white border-danger',
  info: 'bg-info text-black border-info',
  default: 'bg-gray-700 border-gray-600'
}

const variantStyles = {
  success: { color: '#000', borderColor: 'var(--color-theme-primary)' },
  warning: {},
  danger: {},
  info: {},
  default: { color: 'var(--color-theme-primary)' }
}

const sizeClasses = {
  sm: 'px-2 py-0.5 text-xs',
  md: 'px-3 py-1 text-sm',
  lg: 'px-4 py-1.5 text-base'
}

const badgeClasses = [
  'inline-flex items-center gap-1.5',
  'font-bold rounded-full border-2',
  variantClasses[props.variant],
  sizeClasses[props.size]
].join(' ')
</script>

<template>
  <span :class="badgeClasses" :style="variantStyles[variant]">
    <!-- Dot indicator -->
    <span
      v-if="dot"
      class="h-2 w-2 rounded-full"
      :class="variantClasses[variant].split(' ')[0]"
    ></span>

    <!-- Icon -->
    <component v-if="icon" :is="icon" class="h-4 w-4" />

    <!-- Content -->
    <slot></slot>
  </span>
</template>
