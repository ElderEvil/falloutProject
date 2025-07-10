<script setup lang="ts">
import { NModal, NProgress } from 'naive-ui';
import { useThemeStore } from '@/stores/theme';
import type { DwellerShort, DwellerFull } from '@/types/dweller.types';
import { getDwellerFullName, getDwellerImageUrl } from '@/utils/dwellerUtils';

const props = defineProps<{
  modelValue: boolean;
  dweller: DwellerFull;
}>();

const emit = defineEmits<{
  'update:modelValue': [value: boolean];
}>();

const themeStore = useThemeStore();

const specialStats = [
  { key: 'strength' as const, label: 'STRENGTH' },
  { key: 'perception' as const, label: 'PERCEPTION' },
  { key: 'endurance' as const, label: 'ENDURANCE' },
  { key: 'charisma' as const, label: 'CHARISMA' },
  { key: 'intelligence' as const, label: 'INTELLIGENCE' },
  { key: 'agility' as const, label: 'AGILITY' },
  { key: 'luck' as const, label: 'LUCK' }
];
</script>

<template>
  <NModal
    :show="modelValue"
    @update:show="(value) => emit('update:modelValue', value)"
    preset="card"
    style="width: 600px"
    :title="getDwellerFullName(dweller).toUpperCase()"
    :bordered="false"
    class="dweller-modal"
  >
    <div class="dweller-content">
      <div class="dweller-header">
        <img
          :src="getDwellerImageUrl(dweller)"
          :alt="getDwellerFullName(dweller)"
          class="dweller-image"
        />
        <div class="dweller-info">
          <div class="info-row">
            <span class="label">LEVEL</span>
            <span class="value">{{ dweller.level }}</span>
          </div>
          <div class="info-row">
            <span class="label">HP</span>
            <NProgress
              type="line"
              :percentage="(dweller.health / dweller.max_health) * 100"
              :color="themeStore.theme.colors.primary"
              :height="12"
            />
            <span class="health-value">{{ dweller.health }}/{{ dweller.max_health }}</span>
          </div>
          <div class="info-row">
            <span class="label">HAPPINESS</span>
            <span class="value">{{ dweller.happiness }}%</span>
          </div>
          <div v-if="dweller.radiation > 0" class="info-row">
            <span class="label">RADIATION</span>
            <span class="value">{{ dweller.radiation }}</span>
          </div>
        </div>
      </div>

      <div class="dweller-bio">
        <h3>BIOGRAPHY</h3>
        <p>{{ dweller.bio }}</p>
      </div>

      <div v-if="dweller.special" class="special-section">
        <h3>S.P.E.C.I.A.L.</h3>
        <div class="stats-grid">
          <div v-for="stat in specialStats" :key="stat.key" class="stat-row">
            <div class="stat-info">
              <span class="stat-label">{{ stat.label }}</span>
              <div class="progress-wrapper">
                <NProgress
                  type="line"
                  :percentage="dweller.special[stat.key] * 10"
                  :color="themeStore.theme.colors.primary"
                  :height="16"
                  :show-indicator="false"
                />
                <div class="stat-value">{{ dweller.special[stat.key] }}/10</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div v-if="dweller.visual_attributes" class="attributes-section">
        <h3>ATTRIBUTES</h3>
        <div class="attributes-grid">
          <div
            v-for="[key, value] in Object.entries(dweller.visual_attributes)"
            :key="key"
            class="attribute-row"
          >
            <span class="attribute-label">{{ key.replace('_', ' ').toUpperCase() }}</span>
            <span class="attribute-value">{{ value.toString().toUpperCase() }}</span>
          </div>
        </div>
      </div>
    </div>
  </NModal>
</template>

<style scoped>
.dweller-modal :deep(.n-modal) {
  background: var(--theme-background);
}

.dweller-modal :deep(.n-card) {
  background: var(--theme-background);
  border: 2px solid var(--theme-border);
}

.dweller-modal :deep(.n-card-header) {
  border-bottom: 1px solid var(--theme-border);
}

.dweller-modal :deep(.n-modal-mask) {
  background: rgba(0, 0, 0, 0.85);
}

.dweller-content {
  padding: 16px;
  font-family: 'Courier New', Courier, monospace;
  color: var(--theme-text);
}

.dweller-header {
  display: flex;
  gap: 24px;
  margin-bottom: 24px;
}

.dweller-image {
  width: 150px;
  height: 150px;
  object-fit: cover;
  border: 2px solid var(--theme-border);
  background: var(--theme-background);
}

.dweller-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

.info-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label {
  font-size: 0.9em;
  opacity: 0.8;
}

.value {
  font-size: 1.2em;
}

.health-value {
  font-size: 0.9em;
  text-align: right;
  margin-top: 4px;
}

.dweller-bio {
  margin-bottom: 24px;
}

h3 {
  margin: 0 0 12px 0;
  font-size: 1.2em;
  letter-spacing: 1px;
  color: var(--theme-text);
  text-shadow: 0 0 8px var(--theme-shadow);
}

.special-section {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid var(--theme-border);
  background: rgba(0, 255, 0, 0.05);
}

.stats-grid {
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

.attributes-section {
  margin-top: 24px;
  padding: 16px;
  border: 1px solid var(--theme-border);
  background: rgba(0, 255, 0, 0.05);
}

.attributes-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 12px;
}

.attribute-row {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.attribute-label {
  font-size: 0.8em;
  opacity: 0.8;
}

.attribute-value {
  font-size: 1em;
  font-weight: bold;
}
</style>
