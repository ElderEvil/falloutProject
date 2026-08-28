<script setup lang="ts">
import { Icon } from '@iconify/vue'
import { computed, ref, useId } from 'vue'

export interface SelectOption {
  value: string
  label: string
}

interface Props {
  modelValue?: string
  options: readonly SelectOption[]
  label?: string
  placeholder?: string
  helpText?: string
  error?: string
  required?: boolean
  disabled?: boolean
  size?: 'sm' | 'md' | 'lg'
  labelIcon?: string
}

const {
  size = 'md',
  disabled = false,
  error,
  helpText,
  label,
  labelIcon,
  modelValue,
  options,
  placeholder,
  required,
} = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const isOpen = ref(false)
const selectId = useId()
const labelId = useId()
const selectedOption = computed(() => options.find((option) => option.value === modelValue))
const sizeClasses: Record<string, string> = {
  sm: 'px-2 py-1 text-xs',
  md: 'px-3 py-2 text-sm',
  lg: 'px-4 py-3 text-base',
}

function choose(option: SelectOption) {
  emit('update:modelValue', option.value)
  isOpen.value = false
}

function handleKeydown(event: KeyboardEvent) {
  if (event.key === 'Escape') {
    isOpen.value = false
    return
  }
  if (event.key === 'Enter' || event.key === ' ') {
    event.preventDefault()
    isOpen.value = !isOpen.value
  }
}

function handleFocusout(event: FocusEvent) {
  const nextTarget = event.relatedTarget
  const wrapper = event.currentTarget as HTMLElement
  if (!(nextTarget instanceof Node) || !wrapper.contains(nextTarget)) {
    isOpen.value = false
  }
}
</script>

<template>
  <div class="select-wrapper" @focusout="handleFocusout">
    <span v-if="label" :id="labelId" class="select-label" :class="{ 'text-danger': error }">
      <Icon v-if="labelIcon" :icon="labelIcon" class="label-icon" />
      {{ label }}
      <span v-if="required" class="text-danger">*</span>
    </span>
    <button
      :id="selectId"
      type="button"
      role="combobox"
      aria-haspopup="listbox"
      :aria-labelledby="label ? labelId : undefined"
      :aria-expanded="isOpen"
      :aria-controls="`${selectId}-options`"
      :disabled="disabled"
      :class="[
        sizeClasses[size],
        'select-trigger',
        error ? 'select-trigger-error' : '',
        { 'opacity-50 cursor-not-allowed': disabled },
      ]"
      @click="isOpen = !isOpen"
      @keydown="handleKeydown"
    >
      <span>{{ selectedOption?.label || placeholder || '—' }}</span>
      <Icon icon="mdi:chevron-down" class="h-4 w-4 shrink-0 transition-transform" :class="{ 'rotate-180': isOpen }" />
    </button>
    <div v-if="isOpen" :id="`${selectId}-options`" class="select-menu" role="listbox">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        role="option"
        class="select-option"
        :aria-selected="option.value === modelValue"
        @click="choose(option)"
      >
        <Icon v-if="option.value === modelValue" icon="mdi:check" class="h-4 w-4" />
        <span v-else class="h-4 w-4" aria-hidden="true" />
        {{ option.label }}
      </button>
    </div>
    <p v-if="helpText && !error" class="select-helptext">{{ helpText }}</p>
    <p v-if="error" class="select-error">{{ error }}</p>
  </div>
</template>

<style scoped>
.select-wrapper { position: relative; display: flex; flex-direction: column; gap: 0.25rem; }
.select-label { display: flex; align-items: center; gap: 0.25rem; font-size: 0.75rem; font-weight: 600; color: var(--color-theme-primary); opacity: 0.7; text-transform: uppercase; letter-spacing: 0.05em; }
.label-icon { width: 0.875rem; height: 0.875rem; }
.select-trigger { display: flex; align-items: center; justify-content: space-between; width: 100%; border: 1px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent); border-radius: var(--border-radius-base); background: var(--color-surface-raised); color: var(--color-theme-primary); font-family: var(--font-family-mono); text-align: left; transition: border-color var(--transition-base), box-shadow var(--transition-base); }
.select-trigger:focus-visible { border-color: var(--color-theme-primary); outline: none; box-shadow: 0 0 8px var(--color-theme-glow); }
.select-trigger-error { border-color: var(--color-danger); }
.select-menu { position: absolute; z-index: 10; top: 100%; right: 0; left: 0; max-height: 15rem; overflow-y: auto; margin-top: 0.25rem; padding: 0.25rem; border: 1px solid color-mix(in srgb, var(--color-theme-primary) 45%, transparent); border-radius: var(--border-radius-base); background: var(--color-surface-raised); box-shadow: 0 8px 20px var(--color-theme-glow); }
.select-option { display: flex; align-items: center; gap: 0.5rem; width: 100%; padding: 0.5rem; border: 0; border-radius: var(--border-radius-sm); background: transparent; color: var(--color-theme-primary); font: inherit; font-size: 0.875rem; text-align: left; cursor: pointer; }
.select-option:hover, .select-option:focus-visible, .select-option[aria-selected='true'] { background: color-mix(in srgb, var(--color-theme-primary) 12%, transparent); outline: none; }
.select-helptext, .select-error { font-size: 0.7rem; }
.select-helptext { color: var(--color-theme-primary); opacity: 0.5; }
.select-error { color: var(--color-danger); }
</style>
