<script setup lang="ts">
import { NProgress } from 'naive-ui'
import { useThemeStore } from '@/stores/theme'
import { Flash, Water, Restaurant, Cash, Happy } from '@vicons/ionicons5'
import type { Resource } from '@/types/vault'

const props = defineProps<{
  resources: Resource[]
  bottlecaps: number
  totalDwellers: number
  maxDwellers: number
  averageHappiness?: number
}>()

const themeStore = useThemeStore()

const getResourceInfo = (type: Resource['type']) => {
  switch (type) {
    case 'power':
      return { name: 'POWER', icon: Flash }
    case 'food':
      return { name: 'FOOD', icon: Restaurant }
    case 'water':
      return { name: 'WATER', icon: Water }
  }
}
</script>

<template>
  <div class="resources-container">
    <div class="header-stats">
      <div class="dweller-count">DWELLERS: {{ totalDwellers }}/{{ maxDwellers }}</div>
      <div v-if="averageHappiness !== undefined" class="happiness-display">
        <Happy class="happiness-icon" />
        <span>{{ Math.round(averageHappiness) }}%</span>
      </div>
    </div>
    <div class="resources-grid">
      <div v-for="resource in resources" :key="resource.type" class="resource-item">
        <div class="resource-header">
          <component :is="getResourceInfo(resource.type)?.icon" class="resource-icon" />
          <span class="resource-name">{{ getResourceInfo(resource.type)?.name }}</span>
        </div>
        <NProgress
          type="line"
          :percentage="(resource.amount / resource.capacity) * 100"
          :color="themeStore.theme.colors.primary"
          :height="12"
          :show-indicator="false"
        />
        <div class="resource-amount">{{ resource.amount }}/{{ resource.capacity }}</div>
      </div>
      <div class="resource-item caps">
        <div class="resource-header">
          <Cash class="resource-icon" />
          <span class="resource-name">BOTTLE CAPS</span>
        </div>
        <div class="caps-amount">{{ bottlecaps }}</div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.resources-container {
  margin-bottom: 24px;
}

.header-stats {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 12px;
}

.dweller-count {
  font-family: 'Courier New', Courier, monospace;
  font-size: 1.1em;
}

.happiness-display {
  display: flex;
  align-items: center;
  gap: 8px;
  font-family: 'Courier New', Courier, monospace;
  font-size: 1.1em;
}

.happiness-icon {
  width: 24px;
  height: 24px;
  color: var(--theme-text);
}

.resources-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 16px;
  background-color: var(--theme-background);
}

.resource-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border: 1px solid var(--theme-border);
  background: rgba(0, 255, 0, 0.05);
}

.resource-header {
  display: flex;
  align-items: center;
  gap: 8px;
}

.resource-icon {
  width: 20px;
  height: 20px;
  color: var(--theme-text);
}

.resource-name {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
  opacity: 0.8;
}

.resource-amount {
  font-family: 'Courier New', Courier, monospace;
  font-size: 0.9em;
  text-align: right;
}

.caps-amount {
  font-family: 'Courier New', Courier, monospace;
  font-size: 1.2em;
  text-align: right;
  margin-top: auto;
}

.caps .resource-icon {
  transform: rotate(-15deg);
}
</style>
