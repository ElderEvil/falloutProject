<template>
  <div class="setting-item">
    <span class="setting-label">{{ label }}</span>
    <span class="setting-value">
      {{ formattedValue }} <span v-if="unit" class="setting-unit">{{ unit }}</span>
    </span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

const props = defineProps<{
  label: string
  value: string | number | boolean
  unit?: string
  decimals?: number
}>()

const formattedValue = computed(() => {
  if (typeof props.value === 'number' && props.decimals !== undefined) {
    return props.value.toFixed(props.decimals)
  }
  if (typeof props.value === 'boolean') {
    return props.value ? 'Yes' : 'No'
  }
  return props.value
})
</script>

<style scoped>
.setting-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 0.75rem 1rem;
  border-bottom: 1px solid var(--color-border);
  font-family: var(--font-mono);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-label {
  color: var(--color-text-secondary);
  font-size: 0.875rem;
}

.setting-value {
  color: var(--color-primary);
  font-weight: 600;
  font-size: 0.875rem;
}

.setting-unit {
  color: var(--color-text-muted);
  font-weight: 400;
  margin-left: 0.25rem;
}
</style>
