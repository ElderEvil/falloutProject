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
  counts?: Record<string, number>
}

const props = defineProps<Props>()

const emit = defineEmits<{
  'update:modelValue': [value: string]
}>()

const hasCount = (value: string): boolean => props.counts !== undefined && value in props.counts
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
        :class="{
          active: modelValue === option.value,
          empty: counts !== undefined && counts[option.value] === 0,
        }"
        :style="option.accent ? { '--filter-accent': option.accent } : undefined"
        :aria-pressed="modelValue === option.value"
        @click="emit('update:modelValue', option.value)"
      >
        <Icon :icon="option.icon" />
        <span>{{ option.label }}</span>
        <span v-if="hasCount(option.value)" class="filter-count">{{ counts?.[option.value] }}</span>
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
  opacity: 0.7;
  transition:
    background 0.2s,
    border-color 0.2s,
    box-shadow 0.2s,
    opacity 0.2s,
    font-weight 0.2s,
    outline 0.2s;
  white-space: nowrap;
}

.filter-chip:hover {
  opacity: 0.9;
  background: var(--color-surface-hover);
  box-shadow: 0 0 8px var(--color-theme-glow);
}

.filter-chip:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

/* A zero-count chip stays clickable so the filter can be kept, but reads as empty. */
.filter-chip.empty:not(.active) {
  opacity: 0.4;
}

/* Matches .view-toggle-btn.active so the toolbar's selected state reads as one control set. */
.filter-chip.active {
  opacity: 1;
  background: var(--color-surface-hover);
  border-color: var(--filter-accent, var(--color-theme-primary));
  box-shadow: 0 0 12px var(--filter-accent, var(--color-theme-primary));
  font-weight: 600;
}

.filter-count {
  font-size: 0.6875rem;
  font-variant-numeric: tabular-nums;
  opacity: 0.75;
}
</style>
