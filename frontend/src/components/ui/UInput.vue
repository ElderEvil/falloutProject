<script setup lang="ts">
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
  icon?: any
  iconRight?: any
  size?: 'sm' | 'md' | 'lg'
}

const props = withDefaults(defineProps<Props>(), {
  type: 'text',
  size: 'md',
  disabled: false,
  required: false
})

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | number): void
  (e: 'blur'): void
  (e: 'focus'): void
}>()

const sizeClasses = {
  sm: 'px-3 py-1.5 text-sm',
  md: 'px-4 py-2 text-base',
  lg: 'px-5 py-3 text-lg'
}

const inputClasses = [
  'w-full rounded bg-gray-700 text-terminalGreen',
  'border-2 transition-colors',
  props.error ? 'border-danger' : 'border-gray-600',
  'focus:outline-none',
  props.error ? 'focus:border-danger' : 'focus:border-terminalGreen',
  'disabled:opacity-50 disabled:cursor-not-allowed',
  'placeholder:text-gray-400',
  sizeClasses[props.size],
  props.icon ? 'pl-10' : '',
  props.iconRight ? 'pr-10' : ''
].filter(Boolean).join(' ')

const handleInput = (event: Event) => {
  const target = event.target as HTMLInputElement
  emit('update:modelValue', target.value)
}
</script>

<template>
  <div class="w-full">
    <!-- Label -->
    <label v-if="label" class="block text-sm font-medium text-gray-300 mb-1">
      {{ label }}
      <span v-if="required" class="text-danger">*</span>
    </label>

    <!-- Input Container -->
    <div class="relative">
      <!-- Left Icon -->
      <div v-if="icon" class="absolute left-3 top-1/2 transform -translate-y-1/2 text-gray-400">
        <component :is="icon" class="h-5 w-5" />
      </div>

      <!-- Input Field -->
      <input
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
      <div v-if="iconRight" class="absolute right-3 top-1/2 transform -translate-y-1/2 text-gray-400">
        <component :is="iconRight" class="h-5 w-5" />
      </div>
    </div>

    <!-- Help Text -->
    <p v-if="helpText && !error" class="mt-1 text-xs text-gray-400">
      {{ helpText }}
    </p>

    <!-- Error Message -->
    <p v-if="error" class="mt-1 text-xs text-danger">
      {{ error }}
    </p>
  </div>
</template>
