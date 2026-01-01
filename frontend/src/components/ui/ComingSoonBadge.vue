<script setup lang="ts">
import { Icon } from '@iconify/vue'
import UTooltip from './UTooltip.vue'

interface Props {
  feature: string
  phase?: string
  quarter?: string
  size?: 'sm' | 'md' | 'lg'
  inline?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  phase: undefined,
  quarter: undefined,
  size: 'md',
  inline: false
})

const tooltipText = () => {
  let text = `${props.feature} - Coming Soon`
  if (props.phase) {
    text += ` (${props.phase})`
  }
  if (props.quarter) {
    text += ` [${props.quarter}]`
  }
  return text
}

const sizeClasses = {
  sm: 'text-xs px-1.5 py-0.5',
  md: 'text-sm px-2 py-1',
  lg: 'text-base px-3 py-1.5'
}
</script>

<template>
  <UTooltip :text="tooltipText()">
    <div
      class="coming-soon-badge"
      :class="[
        sizeClasses[size],
        inline ? 'inline-flex' : 'flex'
      ]"
    >
      <Icon icon="mdi:lock" class="lock-icon" />
      <span class="badge-text">Coming Soon</span>
      <span v-if="phase" class="phase-badge">{{ phase }}</span>
    </div>
  </UTooltip>
</template>

<style scoped>
.coming-soon-badge {
  align-items: center;
  gap: 0.5rem;
  background: rgba(0, 255, 0, 0.05);
  border: 1px solid rgba(0, 255, 0, 0.2);
  border-radius: 0.25rem;
  font-family: 'Courier New', monospace;
  color: rgba(0, 255, 0, 0.5);
  cursor: not-allowed;
  user-select: none;
  transition: all 0.2s ease;
}

.coming-soon-badge:hover {
  background: rgba(0, 255, 0, 0.08);
  border-color: rgba(0, 255, 0, 0.3);
}

.lock-icon {
  flex-shrink: 0;
  opacity: 0.6;
}

.badge-text {
  font-weight: 500;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.phase-badge {
  padding: 0.125rem 0.375rem;
  background: rgba(0, 255, 0, 0.1);
  border: 1px solid rgba(0, 255, 0, 0.3);
  border-radius: 0.25rem;
  font-size: 0.75em;
  font-weight: 600;
}

/* Scanline effect */
.coming-soon-badge::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to bottom,
    transparent 50%,
    rgba(0, 255, 0, 0.02) 50%
  );
  background-size: 100% 4px;
  pointer-events: none;
  opacity: 0.5;
}
</style>
