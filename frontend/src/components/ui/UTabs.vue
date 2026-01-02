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
  border-bottom: 2px solid var(--color-theme-glow);
  margin-bottom: 1.5rem;
}

.utabs-button {
  padding: 0.75rem 1.5rem;
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--color-theme-glow);
  font-family: inherit;
  font-size: 0.95rem;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s ease;
  text-shadow: 0 0 3px var(--color-theme-glow);
  position: relative;
  margin-bottom: -2px;
}

.utabs-button:hover:not(.disabled) {
  color: var(--color-theme-primary);
  background: var(--color-theme-glow);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.utabs-button.active {
  color: var(--color-theme-primary);
  border-bottom-color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
  background: var(--color-theme-glow);
}

.utabs-button.disabled {
  color: var(--color-theme-glow);
  cursor: not-allowed;
  opacity: 0.5;
}

.utabs-content {
  padding: 0.5rem 0;
}
</style>
