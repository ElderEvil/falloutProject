<script setup lang="ts">
/**
 * USelect - Terminal-themed select dropdown
 *
 * Features:
 * - Terminal green focus state
 * - Support for label and help text
 * - Error state with message
 * - Matches UInput visual style
 */

interface Props {
  modelValue?: string
  label?: string
  placeholder?: string
  helpText?: string
  error?: string
  required?: boolean
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
}

const { size = 'md', disabled, error, helpText, label, modelValue, placeholder, required } = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const sizeClasses: Record<string, string> = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-3 py-2 text-sm',
  lg: 'px-4 py-3 text-base',
}
</script>

<template>
  <div class="select-wrapper">
    <label v-if="label" class="select-label" :class="{ 'text-danger': error }">
      {{ label }}
      <span v-if="required" class="text-danger">*</span>
    </label>
    <select
      :value="modelValue"
      @change="emit('update:modelValue', ($event.target as HTMLSelectElement).value)"
      :disabled="disabled"
      :class="[
        sizeClasses[size],
        'w-full bg-terminal-background border rounded font-mono transition-colors appearance-none',
        'text-theme-primary',
        error
          ? 'border-danger shadow-[0_0_8px_rgba(255,0,0,0.3)]'
          : 'border-[rgba(var(--color-theme-primary-rgb,0,255,0),0.3)] focus:border-theme-primary focus:shadow-[0_0_8px_var(--color-theme-glow)]',
        { 'opacity-50 cursor-not-allowed': disabled },
      ]"
    >
      <option value="" disabled>{{ placeholder || '—' }}</option>
      <slot />
    </select>
    <p v-if="helpText && !error" class="select-helptext">{{ helpText }}</p>
    <p v-if="error" class="select-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.select-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.select-label {
  font-size: 0.75rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  opacity: 0.7;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.select-helptext {
  font-size: 0.7rem;
  color: var(--color-theme-primary);
  opacity: 0.5;
}

.select-error {
  font-size: 0.7rem;
  color: var(--color-danger);
}

select option {
  background: var(--color-terminal-background);
  color: var(--color-theme-primary);
}
</style>
