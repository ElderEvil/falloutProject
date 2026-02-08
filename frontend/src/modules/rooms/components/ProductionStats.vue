<script setup lang="ts">
import { Icon } from '@iconify/vue'

interface ProductionInfo {
  resourceType: string
  abilitySum: number
  productionPerMinute: string
  productionPerSecond: string
  efficiency: number
  isFullyStaffed: boolean
}

interface Props {
  productionInfo: ProductionInfo
}

defineProps<Props>()
</script>

<template>
  <div class="section">
    <h3 class="section-title">
      <Icon icon="mdi:chart-line" class="h-5 w-5" />
      Production Statistics
    </h3>
    <div class="production-stats">
      <div class="stat-card">
        <div class="stat-label">Resource Type</div>
        <div class="stat-value">
          {{ productionInfo.resourceType }}
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Production Rate</div>
        <div class="stat-value">{{ productionInfo.productionPerMinute }} /min</div>
        <div class="stat-subvalue">{{ productionInfo.productionPerSecond }} /sec</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Efficiency</div>
        <div
          class="stat-value"
          :class="{
            'text-success': productionInfo.isFullyStaffed,
          }"
        >
          {{ productionInfo.efficiency }}%
        </div>
      </div>
      <div class="stat-card">
        <div class="stat-label">Total Stat Points</div>
        <div class="stat-value">
          {{ productionInfo.abilitySum }}
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  margin: 0;
}

.production-stats {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(150px, 1fr));
  gap: 1rem;
}

.stat-card {
  padding: 1rem;
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  text-align: center;
}

.stat-label {
  font-size: 0.75rem;
  color: #aaa;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  margin-top: 0.5rem;
}

.stat-subvalue {
  font-size: 0.75rem;
  color: #888;
  margin-top: 0.25rem;
}

.text-success {
  color: #00ff00 !important;
  text-shadow: 0 0 8px var(--color-theme-glow);
}
</style>
