<script setup lang="ts">
import { NProgress } from 'naive-ui'
import { useThemeStore } from '@/stores/theme'
import type { Special } from '@/types/vault'

const props = defineProps<{
  special: Special
}>()

const themeStore = useThemeStore()

const stats = [
  { key: 'strength', label: 'STRENGTH' },
  { key: 'perception', label: 'PERCEPTION' },
  { key: 'endurance', label: 'ENDURANCE' },
  { key: 'charisma', label: 'CHARISMA' },
  { key: 'intelligence', label: 'INTELLIGENCE' },
  { key: 'agility', label: 'AGILITY' },
  { key: 'luck', label: 'LUCK' }
] as const
</script>

<template>
  <div class="special-stats">
    <div v-for="stat in stats" :key="stat.key" class="stat-row">
      <div class="stat-info">
        <span class="stat-label">{{ stat.label }}</span>
        <div class="progress-wrapper">
          <NProgress
            type="line"
            :percentage="special[stat.key] * 10"
            :color="themeStore.theme.colors.primary"
            :height="16"
            :show-indicator="false"
          />
          <div class="stat-value">{{ special[stat.key] }}/10</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.special-stats {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.stat-row {
  display: flex;
  align-items: center;
}

.stat-info {
  display: flex;
  align-items: center;
  width: 100%;
  gap: 16px;
}

.stat-label {
  width: 120px;
  font-weight: bold;
  font-size: 1em;
  text-shadow: 0 0 8px var(--theme-shadow);
}

.progress-wrapper {
  flex: 1;
  display: flex;
  align-items: center;
  gap: 12px;
}

.stat-value {
  min-width: 45px;
  font-size: 0.9em;
  opacity: 0.8;
}
</style>
