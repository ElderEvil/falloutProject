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

interface RadioStats {
  hasRadio: boolean
  recruitmentRate: number
  ratePerHour: number
  estimatedHoursPerRecruit: number
  speedupMultiplier: number
  manualCostCaps: number
  radioMode: string
  radioHappinessBonus: number
}

interface Props {
  productionInfo?: ProductionInfo
  radioStats?: RadioStats
  radioMode?: string
}

defineProps<Props>()
</script>

<template>
  <div class="section">
    <h3 class="section-title">
      <Icon icon="mdi:chart-line" class="h-5 w-5" />
      {{ radioStats ? 'Radio Statistics' : 'Production Statistics' }}
    </h3>
    <div class="production-stats">
      <template v-if="radioStats">
        <template v-if="radioMode === 'happiness'">
          <div class="stat-card">
            <div class="stat-label">Mode</div>
            <div class="stat-value">Happiness</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Happiness Bonus</div>
            <div class="stat-value">+{{ radioStats.radioHappinessBonus.toFixed(1) }}</div>
            <div class="stat-subvalue">per dweller per tick</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Speedup</div>
            <div class="stat-value">&times;{{ radioStats.speedupMultiplier.toFixed(1) }}</div>
          </div>
        </template>
        <template v-else>
          <div class="stat-card">
            <div class="stat-label">Mode</div>
            <div class="stat-value">Recruiting</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Recruits</div>
            <div class="stat-value">{{ radioStats.recruitmentRate.toFixed(2) }} /min</div>
            <div class="stat-subvalue">{{ radioStats.ratePerHour.toFixed(2) }} /hour</div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Recruit ETA</div>
            <div class="stat-value">
              {{ radioStats.estimatedHoursPerRecruit > 0 ? `${radioStats.estimatedHoursPerRecruit.toFixed(1)}h` : '—' }}
            </div>
          </div>
          <div class="stat-card">
            <div class="stat-label">Speedup</div>
            <div class="stat-value">&times;{{ radioStats.speedupMultiplier.toFixed(1) }}</div>
          </div>
        </template>
      </template>
      <template v-else-if="productionInfo">
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
      </template>
    </div>
  </div>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.9375rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  margin: 0;
}

.section-title :deep(svg) {
  width: 1rem;
  height: 1rem;
}

.production-stats {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
}

.stat-card {
  padding: 0.5rem 0.6rem;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-glow);
  border-radius: 4px;
  text-align: center;
}

.stat-label {
  font-size: 0.6875rem;
  color: var(--color-gray-400);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 1.125rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  margin-top: 0.2rem;
}

.stat-subvalue {
  font-size: 0.6875rem;
  color: var(--color-gray-500);
  margin-top: 0.15rem;
}

.text-success {
  color: var(--color-theme-primary) !important;
}
</style>
