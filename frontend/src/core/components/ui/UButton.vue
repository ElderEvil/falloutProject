<script setup lang="ts">
import type { IconComponent } from '@/core/types/utils'

/**
 * UButton - Terminal-themed button component wrapping Nuxt UI
 *
 * Variants:
 * - primary: Solid terminal green background
 * - secondary: Outlined terminal green
 * - danger: Red for destructive actions
 * - ghost: Transparent with hover effect
 */

interface Props {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost'
  size?: 'xs' | 'sm' | 'md' | 'lg' | 'xl'
  disabled?: boolean
  loading?: boolean
  icon?: IconComponent
  iconRight?: IconComponent
  block?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  variant: 'primary',
  size: 'md',
  disabled: false,
  loading: false,
  block: false
})

const emit = defineEmits<{
  (e: 'click', event: MouseEvent): void
}>()

const variantClasses = {
  primary: 'btn-primary',
  secondary: 'btn-secondary',
  danger: 'btn-danger',
  ghost: 'btn-ghost'
}

const sizeClasses = {
  xs: 'px-2 py-1 text-xs',
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-6 py-3 text-lg',
  xl: 'px-8 py-4 text-xl'
}

const buttonClasses = [
  'inline-flex items-center justify-center gap-2',
  'font-bold rounded transition-all duration-200',
  'focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed',
  variantClasses[props.variant],
  sizeClasses[props.size],
  props.block ? 'w-full' : ''
].filter(Boolean).join(' ')

const handleClick = (event: MouseEvent) => {
  if (!props.disabled && !props.loading) {
    emit('click', event)
  }
}
</script>

<template>
  <button
    :class="buttonClasses"
    :disabled="disabled || loading"
    @click="handleClick"
    type="button"
  >
    <component v-if="icon && !loading" :is="icon" class="h-5 w-5" />
    <span v-if="loading" class="animate-spin">⚙</span>
    <slot></slot>
    <component v-if="iconRight" :is="iconRight" class="h-5 w-5" />
  </button>
</template>

<style scoped>
@keyframes spin {
  from { transform: rotate(0deg); }
  to { transform: rotate(360deg); }
}

.animate-spin {
  animation: spin 1s linear infinite;
}

/* Button Variants */
.btn-primary {
  background-color: var(--color-theme-accent);
  color: #000;
  border: 2px solid var(--color-theme-primary);
}

.btn-primary:hover:not(:disabled) {
  background-color: var(--color-theme-primary);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.btn-secondary {
  background-color: transparent;
  color: var(--color-theme-primary);
  border: 2px solid var(--color-theme-primary);
}

.btn-secondary:hover:not(:disabled) {
  background-color: var(--color-theme-glow);
}

.btn-danger {
  background-color: var(--color-danger);
  color: #fff;
  border: 2px solid var(--color-danger);
}

.btn-danger:hover:not(:disabled) {
  opacity: 0.8;
}

.btn-ghost {
  background-color: transparent;
  color: var(--color-theme-primary);
  border: 2px solid transparent;
}

.btn-ghost:hover:not(:disabled) {
  background-color: var(--color-surface-light);
}
</style>
