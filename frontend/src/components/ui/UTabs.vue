<script setup lang="ts">
import { computed } from 'vue'

export interface Tab {
  key: string
  label: string
  disabled?: boolean
}

interface Props {
  tabs: Tab[]
  modelValue: string
}

interface Emits {
  (e: 'update:modelValue', value: string): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const activeTab = computed({
  get: () => props.modelValue,
  set: (value: string) => emit('update:modelValue', value)
})

const selectTab = (key: string, disabled?: boolean) => {
  if (disabled) return
  activeTab.value = key
}
</script>

<template>
  <div class="utabs">
    <div class="utabs-header">
      <button
        v-for="tab in tabs"
        :key="tab.key"
        @click="selectTab(tab.key, tab.disabled)"
        :class="{
          active: activeTab === tab.key,
          disabled: tab.disabled
        }"
        :disabled="tab.disabled"
        class="utabs-button"
      >
        {{ tab.label }}
      </button>
    </div>
    <div class="utabs-content">
      <slot :active-tab="activeTab" />
    </div>
  </div>
</template>

<style scoped>
.utabs {
  display: flex;
  flex-direction: column;
  width: 100%;
}

.utabs-header {
  display: flex;
  gap: 0.5rem;
  border-bottom: 2px solid rgba(0, 255, 0, 0.2);
  margin-bottom: 1.5rem;
}

.utabs-button {
  padding: 0.75rem 1.5rem;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: rgba(0, 255, 0, 0.6);
  font-family: inherit;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  text-shadow: 0 0 3px rgba(0, 255, 0, 0.3);
  position: relative;
  margin-bottom: -2px;
}

.utabs-button:hover:not(.disabled) {
  color: rgba(0, 255, 0, 0.9);
  background: rgba(0, 255, 0, 0.05);
  text-shadow: 0 0 6px rgba(0, 255, 0, 0.5);
}

.utabs-button.active {
  color: #00ff00;
  border-bottom-color: #00ff00;
  text-shadow: 0 0 8px rgba(0, 255, 0, 0.6);
  background: rgba(0, 255, 0, 0.08);
}

.utabs-button.disabled {
  color: rgba(0, 255, 0, 0.3);
  cursor: not-allowed;
  opacity: 0.5;
}

.utabs-content {
  padding: 0.5rem 0;
}
</style>
