<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import UButton from '@/core/components/ui/UButton.vue'
import UAlert from '@/core/components/ui/UAlert.vue'

interface Props {
  localRadioMode: string
  isRecruiting: boolean
  manualRecruitCost: number
  assignedDwellers: DwellerShort[]
}

defineProps<Props>()

const emit = defineEmits<{
  switchMode: [mode: 'recruitment' | 'happiness']
  recruit: []
}>()
</script>

<template>
  <div class="radio-controls">
    <div class="radio-header">
      <h3 class="radio-title">Broadcast Controls</h3>
      <div class="radio-status">
        <span
          class="status-dot"
          :class="{
            active: localRadioMode === 'recruitment',
          }"
        ></span>
        {{ localRadioMode === 'recruitment' ? 'Recruiting' : 'Broadcasting' }}
      </div>
    </div>

    <!-- Mode Switch -->
    <div class="radio-mode-switch">
      <button
        @click="emit('switchMode', 'recruitment')"
        class="mode-btn"
        :class="{
          active: localRadioMode === 'recruitment',
        }"
      >
        <Icon icon="mdi:radio-tower" class="h-4 w-4" />
        Recruitment
      </button>
      <button
        @click="emit('switchMode', 'happiness')"
        class="mode-btn"
        :class="{
          active: localRadioMode === 'happiness',
        }"
      >
        <Icon icon="mdi:emoticon-happy" class="h-4 w-4" />
        Happiness
      </button>
    </div>

    <!-- Staffing Warning -->
    <UAlert v-if="assignedDwellers.length === 0" variant="warning" class="mb-3">
      <Icon icon="mdi:alert" class="h-4 w-4" />
      Assign at least one dweller to operate the radio room before recruiting.
    </UAlert>

    <!-- Recruit Dweller Button -->
    <UButton
      @click="emit('recruit')"
      :disabled="isRecruiting || assignedDwellers.length === 0 || localRadioMode !== 'recruitment'"
      variant="secondary"
      size="sm"
      class="recruit-btn"
    >
      <Icon icon="mdi:account-plus" class="h-4 w-4" />
      <span>Recruit Dweller ({{ manualRecruitCost }} caps)</span>
    </UButton>
  </div>
</template>

<style scoped>
.radio-controls {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  width: 100%;
}

.radio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.radio-title {
  font-size: 0.9375rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.radio-status {
  font-size: 0.75rem;
  color: var(--color-gray-500);
  display: flex;
  align-items: center;
  gap: 0.35rem;
  text-transform: uppercase;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: var(--color-gray-600);
}

.status-dot.active {
  background-color: var(--color-theme-primary);
  animation: pulse 2s infinite;
}

@keyframes pulse {
  0% {
    opacity: 0.5;
  }
  50% {
    opacity: 1;
  }
  100% {
    opacity: 0.5;
  }
}

.radio-mode-switch {
  display: flex;
  background: var(--color-surface);
  border-radius: 6px;
  padding: 3px;
  gap: 3px;
  border: 1px solid var(--color-surface-hover);
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.4rem;
  border: 1px solid transparent;
  background: transparent;
  color: var(--color-gray-500);
  cursor: pointer;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s;
}

.mode-btn:hover {
  background: var(--color-surface-hover);
  color: var(--color-gray-300);
}

.mode-btn.active {
  border-color: var(--color-theme-primary);
  color: var(--color-theme-primary);
  font-weight: bold;
}

.recruit-btn {
  width: 100%;
}
</style>
