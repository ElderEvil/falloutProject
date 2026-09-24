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
  flex-wrap: wrap;
  justify-content: space-between;
  align-items: center;
  gap: 0.25rem 1rem;
  margin-inline: 1.5rem;
  padding-block: 0.75rem;
  border-bottom: 1px solid var(--color-theme-accent);
  font-family: var(--font-family-mono);
}

.setting-item:last-child {
  border-bottom: none;
}

.setting-label {
  color: color-mix(in srgb, var(--color-theme-primary) 65%, transparent);
  font-size: 0.875rem;
}

.setting-value {
  color: var(--color-theme-primary);
  font-weight: 600;
  font-size: 0.875rem;
  overflow-wrap: anywhere;
  text-align: right;
}

.setting-unit {
  color: color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
  font-weight: 400;
  margin-left: 0.25rem;
}
</style>
