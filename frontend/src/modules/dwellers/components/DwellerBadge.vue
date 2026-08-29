<script setup lang="ts">
import { Icon } from '@iconify/vue'

withDefaults(
  defineProps<{
    icon: string
    color: string
    label: string
    showLabel?: boolean
    size?: 'sm' | 'md'
  }>(),
  { showLabel: true, size: 'md' }
)
</script>

<template>
  <span
    class="dweller-badge"
    :class="[`size-${size}`, { 'icon-only': !showLabel }]"
    :style="{ '--badge-color': color }"
    :title="label"
    :aria-label="label"
    role="img"
  >
    <Icon :icon="icon" class="badge-icon" />
    <span v-if="showLabel" class="badge-label">{{ label }}</span>
  </span>
</template>

<style scoped>
/* Informational badge (badge-info intent): color codes the category, but a fact
   never glows, never animates, and never responds to hover — that vocabulary is
   reserved for actions and live status. */
.dweller-badge {
  display: inline-flex;
  align-items: center;
  gap: 0.3rem;
  border: 1px solid var(--badge-color);
  border-radius: 999px;
  background: rgba(0, 0, 0, 0.4);
  color: var(--badge-color);
  white-space: nowrap;
}

.size-sm {
  padding: 0.15rem 0.4rem;
  font-size: 0.7rem;
}

.icon-only {
  justify-content: center;
  padding: 0;
}

.icon-only.size-sm {
  width: 1.5rem;
  height: 1.5rem;
}

.icon-only.size-md {
  width: 2.25rem;
  height: 2.25rem;
}

.size-md {
  padding: 0.5rem 1rem;
  font-size: 0.875rem;
}

.badge-icon {
  font-size: 1.25em;
}

.badge-label {
  font-weight: 700;
  text-transform: capitalize;
}
</style>
