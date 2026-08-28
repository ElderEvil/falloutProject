<script setup lang="ts">
import type { IconComponent } from '@/core/types/utils'
import { computed, useId } from 'vue'
import { Icon } from '@iconify/vue'

/**
 * UInput - Terminal-themed input component
 *
 * Features:
 * - Terminal green focus state
 * - Support for label and help text
 * - Error state with message
 * - Icon support
 */

interface Props {
  modelValue?: string | number
  type?: 'text' | 'email' | 'password' | 'number' | 'tel' | 'url'
  label?: string
  placeholder?: string
  helpText?: string
  error?: string
  required?: boolean
  disabled?: boolean
  icon?: IconComponent
  iconRight?: IconComponent
  labelIcon?: string
  size?: 'sm' | 'md' | 'lg'
  variant?: 'default' | 'terminal'
}

const {
  type = 'text',
  size = 'md',
  disabled = false,
  required = false,
  variant = 'default',
  error,
  helpText,
  icon,
  iconRight,
  label,
  labelIcon,
  modelValue,
  placeholder,
} = defineProps<Props>()

const emit = defineEmits<{
  // Native inputs always produce strings.
  (e: 'update:modelValue', value: string): void
  (e: 'blur'): void
  (e: 'focus'): void
}>()

const sizeClasses = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-5 py-3 text-lg',
}

const inputClasses = computed(() => {
  const base = [
    'w-full rounded text-terminal-green',
    'border-2 transition-colors',
    'focus:outline-none',
    'disabled:opacity-50 disabled:cursor-not-allowed',
    'placeholder:text-theme-primary/40',
    sizeClasses[size],
    icon ? 'pl-10' : '',
    iconRight ? 'pr-10' : '',
  ].filter(Boolean)

  if (variant === 'terminal') {
    base.push('bg-surface-sunken')
    base.push(error ? 'border-danger' : 'border-theme-primary/50')
    base.push(error ? 'focus:border-danger' : 'focus:border-theme-primary')
  } else {
    base.push('bg-surface-raised')
    base.push(error ? 'border-danger' : 'border-theme-primary/20')
    base.push(error ? 'focus:border-danger' : 'focus:border-terminal-green')
  }

  return base.join(' ')
})

const inputId = useId()

const handleInput = (event: InputEvent) => {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="w-full">
    <!-- Label -->
    <label v-if="label" :for="inputId" class="flex items-center gap-1 text-sm font-medium text-theme-primary/70 mb-1">
      <Icon v-if="labelIcon" :icon="labelIcon" class="h-3.5 w-3.5 text-theme-primary/60" />
      {{ label }}
      <span v-if="required" class="text-danger">*</span>
    </label>

    <!-- Input Container -->
    <div class="relative">
      <!-- Left Icon -->
      <div v-if="icon" class="absolute left-3 top-1/2 transform -translate-y-1/2 text-theme-primary/50">
        <component :is="icon" class="h-5 w-5" />
      </div>

      <!-- Input Field -->
      <input
        :id="inputId"
        v-bind="{ 'data-testid': 'ui-input' }"
        :type="type"
        :value="modelValue"
        :placeholder="placeholder"
        :disabled="disabled"
        :required="required"
        :class="inputClasses"
        @input="handleInput"
        @blur="emit('blur')"
        @focus="emit('focus')"
      />

      <!-- Right Icon -->
      <div
        v-if="iconRight"
        class="absolute right-3 top-1/2 transform -translate-y-1/2 text-theme-primary/50"
      >
        <component :is="iconRight" class="h-5 w-5" />
      </div>
    </div>

    <!-- Help Text -->
    <p v-if="helpText && !error" class="mt-1 text-xs text-theme-primary/50">
      {{ helpText }}
    </p>

    <!-- Error Message -->
    <p v-if="error" class="mt-1 text-xs text-danger">
      {{ error }}
    </p>
  </div>
</template>
