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
      <h4 class="radio-title">Radio Studio</h4>
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
      :disabled="
        isRecruiting || assignedDwellers.length === 0 || localRadioMode !== 'recruitment'
      "
      variant="primary"
      class="recruit-btn"
    >
      <Icon icon="mdi:account-plus" class="h-5 w-5" />
      <span>Recruit Dweller ({{ manualRecruitCost }} caps)</span>
    </UButton>
  </div>
</template>

<style scoped>
.radio-controls {
  display: flex;
  flex-direction: column;
  gap: 1rem;
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  margin-top: 0.5rem;
  width: 100%;
}

.radio-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.radio-title {
  font-size: 1rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  margin: 0;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.radio-status {
  font-size: 0.75rem;
  color: #888;
  display: flex;
  align-items: center;
  gap: 0.35rem;
  text-transform: uppercase;
}

.status-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background-color: #555;
  box-shadow: 0 0 4px rgba(0, 0, 0, 0.5);
}

.status-dot.active {
  background-color: var(--color-terminal-green);
  box-shadow: 0 0 8px var(--color-terminal-green);
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
  background: rgba(0, 0, 0, 0.5);
  border-radius: 6px;
  padding: 4px;
  gap: 4px;
  border: 1px solid rgba(255, 255, 255, 0.1);
}

.mode-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.5rem;
  border: none;
  background: transparent;
  color: #888;
  cursor: pointer;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 500;
  transition: all 0.2s;
}

.mode-btn:hover {
  background: rgba(255, 255, 255, 0.05);
  color: #aaa;
}

.mode-btn.active {
  background: var(--color-theme-primary);
  color: #000;
  font-weight: bold;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.3);
}

.recruit-btn {
  width: 100%;
  margin-top: 0.5rem;
}
</style>
