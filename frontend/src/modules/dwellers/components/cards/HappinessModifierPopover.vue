<script setup lang="ts">
import { ref } from 'vue'
import { Icon } from '@iconify/vue'
import { happinessService, type HappinessModifiers } from '../../services/happinessService'

interface Props {
  dwellerId: string
}

const props = defineProps<Props>()

const showModifiers = ref(false)
const happinessModifiers = ref<HappinessModifiers | null>(null)
const loadingModifiers = ref(false)

const loadHappinessModifiers = async () => {
  if (happinessModifiers.value) {
    showModifiers.value = !showModifiers.value
    return
  }

  loadingModifiers.value = true
  try {
    const response = await happinessService.getDwellerModifiers(props.dwellerId)
    happinessModifiers.value = response.data
    showModifiers.value = true
  } catch (error) {
    console.error('Failed to load happiness modifiers:', error)
  } finally {
    loadingModifiers.value = false
  }
}
</script>

<template>
  <div>
    <button
      @click="loadHappinessModifiers"
      class="happiness-info-button"
      :disabled="loadingModifiers"
      aria-label="View happiness modifiers"
      title="View happiness modifiers"
    >
      <Icon
        :icon="loadingModifiers ? 'mdi:loading' : 'mdi:information-outline'"
        :class="{ 'animate-spin': loadingModifiers }"
        class="h-4 w-4"
      />
    </button>

    <div v-if="showModifiers && happinessModifiers" class="happiness-modifiers">
      <div class="modifiers-header">
        <span class="modifiers-title">Happiness Modifiers</span>
        <button
          @click="showModifiers = false"
          class="close-button"
          aria-label="Close happiness modifiers"
        >
          <Icon icon="mdi:close" class="h-4 w-4" />
        </button>
      </div>

      <div v-if="happinessModifiers.positive.length > 0" class="modifiers-section">
        <div class="modifiers-label positive">Positive Effects</div>
        <div
          v-for="(modifier, index) in happinessModifiers.positive"
          :key="`pos-${index}`"
          class="modifier-item positive"
        >
          <Icon icon="mdi:arrow-up" class="modifier-icon" />
          <span class="modifier-name">{{ modifier.name }}</span>
          <span class="modifier-value">+{{ modifier.value.toFixed(1) }}</span>
        </div>
      </div>

      <div v-if="happinessModifiers.negative.length > 0" class="modifiers-section">
        <div class="modifiers-label negative">Negative Effects</div>
        <div
          v-for="(modifier, index) in happinessModifiers.negative"
          :key="`neg-${index}`"
          class="modifier-item negative"
        >
          <Icon icon="mdi:arrow-down" class="modifier-icon" />
          <span class="modifier-name">{{ modifier.name }}</span>
          <span class="modifier-value">{{ modifier.value.toFixed(1) }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.happiness-info-button {
  background: transparent;
  border: none;
  cursor: pointer;
  padding: 0.25rem;
  border-radius: 50%;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.happiness-info-button:hover:not(:disabled) {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
  transform: scale(1.1);
}

.happiness-info-button:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.happiness-modifiers {
  background: rgba(0, 0, 0, 0.8);
  border: 1px solid var(--color-theme-glow);
  border-radius: 6px;
  padding: 0.75rem;
  margin-top: 0.5rem;
  animation: slideDown 0.2s ease-out;
}

@keyframes slideDown {
  from {
    opacity: 0;
    transform: translateY(-10px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.modifiers-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.75rem;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.modifiers-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.close-button {
  background: transparent;
  border: none;
  cursor: pointer;
  color: var(--color-theme-primary);
  padding: 0.25rem;
  border-radius: 50%;
  transition: all 0.2s;
  display: flex;
  align-items: center;
  justify-content: center;
}

.close-button:hover {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  transform: rotate(90deg);
}

.modifiers-section {
  margin-top: 0.5rem;
}

.modifiers-section:first-of-type {
  margin-top: 0;
}

.modifiers-label {
  font-size: 0.75rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
  display: block;
}

.modifiers-label.positive {
  color: #4ade80;
}

.modifiers-label.negative {
  color: #ef4444;
}

.modifier-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem 0.5rem;
  margin-bottom: 0.25rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 4px;
  font-size: 0.8125rem;
  transition: all 0.2s;
}

.modifier-item:hover {
  background: rgba(0, 0, 0, 0.5);
  transform: translateX(2px);
}

.modifier-item.positive {
  border-left: 2px solid #4ade80;
}

.modifier-item.negative {
  border-left: 2px solid #ef4444;
}

.modifier-icon {
  font-size: 1rem;
  flex-shrink: 0;
}

.modifier-item.positive .modifier-icon {
  color: #4ade80;
}

.modifier-item.negative .modifier-icon {
  color: #ef4444;
}

.modifier-name {
  flex: 1;
  color: #e5e7eb;
}

.modifier-value {
  font-weight: 600;
  font-family: 'Courier New', monospace;
  flex-shrink: 0;
}

.modifier-item.positive .modifier-value {
  color: #4ade80;
}

.modifier-item.negative .modifier-value {
  color: #ef4444;
}
</style>
