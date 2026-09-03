<script setup lang="ts">
import { Icon } from '@iconify/vue'

export interface DwellerFilterOption {
  value: string
  label: string
  icon: string
  accent?: string
}

interface Props {
  label: string
  icon: string
  options: readonly DwellerFilterOption[]
  modelValue: string
}

defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()
</script>

<template>
  <div class="filter-group">
    <div class="filter-group-label">
      <Icon :icon="icon" />
      <span>{{ label }}</span>
    </div>
    <div class="filter-options">
      <button
        v-for="option in options"
        :key="option.value"
        type="button"
        class="filter-chip"
        :class="{ active: modelValue === option.value }"
        :style="option.accent ? { '--filter-accent': option.accent } : undefined"
        :aria-pressed="modelValue === option.value"
        @click="emit('update:modelValue', option.value)"
      >
        <Icon :icon="option.icon" />
        <span>{{ option.label }}</span>
      </button>
    </div>
  </div>
</template>

<style scoped>
.filter-group {
  display: flex;
  min-width: 0;
  flex-direction: column;
  gap: 0.5rem;
}

.filter-group-label {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.filter-options {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.filter-chip {
  display: inline-flex;
  align-items: center;
  gap: 0.375rem;
  padding: 0.5rem 0.75rem;
  background: var(--color-surface-raised);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  color: var(--color-theme-primary);
  font-size: 0.8125rem;
  font-family: inherit;
  cursor: pointer;
  opacity: 0.6;
  transition: all 0.2s;
  white-space: nowrap;
}

.filter-chip:hover {
  opacity: 0.8;
  background: var(--color-surface-hover);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.filter-chip.active {
  opacity: 1;
  background: var(--color-surface-hover);
  border-color: var(--filter-accent, var(--color-theme-primary));
  box-shadow: 0 0 12px var(--filter-accent, var(--color-theme-primary));
  font-weight: 600;
}
</style>
