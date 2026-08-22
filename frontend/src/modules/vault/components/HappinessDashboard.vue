<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import UCard from '@/core/components/ui/UCard.vue'
import UButton from '@/core/components/ui/UButton.vue'
import USkeleton from '@/core/components/ui/USkeleton.vue'

interface DwellerDistribution {
  high: number // 75-100
  medium: number // 50-74
  low: number // 25-49
  critical: number // 10-24
}

interface Props {
  vaultHappiness: number
  dwellerCount: number
  distribution: DwellerDistribution
  idleDwellerCount?: number
  activeIncidentCount?: number
  lowResourceCount?: number
  radioHappinessMode?: boolean
  loading?: boolean
}

const {
  idleDwellerCount = 0,
  activeIncidentCount = 0,
  lowResourceCount = 0,
  radioHappinessMode = false,
  loading = false,
  distribution,
  dwellerCount,
  vaultHappiness,
} = defineProps<Props>()

const emit = defineEmits<{
  (e: 'assign-idle'): void
  (e: 'activate-radio'): void
  (e: 'view-low-happiness'): void
}>()

const dwellerDistribution = computed<DwellerDistribution>(() => distribution)

const happinessLevel = computed(() => {
  const h = vaultHappiness
  if (h >= 75) return 'high'
  if (h >= 50) return 'medium'
  if (h >= 25) return 'low'
  return 'critical'
})

const happinessColor = computed(() => {
  switch (happinessLevel.value) {
    case 'high':
      return 'var(--color-theme-primary)'
    case 'medium':
      return 'var(--color-terminal-green-dark)'
    case 'low':
      return 'var(--color-warning)'
    case 'critical':
      return 'var(--color-danger)'
    default:
      return 'var(--color-theme-primary)'
  }
})

const happinessLabel = computed(() => {
  switch (happinessLevel.value) {
    case 'high':
      return 'EXCELLENT'
    case 'medium':
      return 'GOOD'
    case 'low':
      return 'POOR'
    case 'critical':
      return 'CRITICAL'
    default:
      return 'UNKNOWN'
  }
})

// Threshold for idle dwellers to trigger decreasing happiness trend
const IDLE_DWELLER_TREND_THRESHOLD = 3

// Calculate trend based on current modifiers and conditions
const happinessTrend = computed((): 'increasing' | 'decreasing' | 'stable' => {
  // Radio happiness mode takes priority when active and no critical issues
  if (radioHappinessMode && activeIncidentCount === 0 && lowResourceCount === 0) {
    return 'increasing'
  }

  // Critical issues always cause decreasing trend (idle dwellers checked separately)
  if (
    activeIncidentCount > 0 ||
    lowResourceCount > 0 ||
    idleDwellerCount >= IDLE_DWELLER_TREND_THRESHOLD
  ) {
    return 'decreasing'
  }

  // Otherwise stable
  return 'stable'
})

const trendIcon = computed(() => {
  switch (happinessTrend.value) {
    case 'increasing':
      return 'mdi:trending-up'
    case 'decreasing':
      return 'mdi:trending-down'
    default:
      return 'mdi:trending-neutral'
  }
})

const trendColor = computed(() => {
  switch (happinessTrend.value) {
    case 'increasing':
      return 'var(--color-theme-primary)'
    case 'decreasing':
      return 'var(--color-danger)'
    default:
      return 'var(--color-gray-400)'
  }
})

// Active modifiers affecting happiness
const activeModifiers = computed(() => {
  const modifiers = []

  if (lowResourceCount > 0) {
    modifiers.push({
      name: 'Low Resources',
      icon: 'mdi:alert-circle',
      severity: 'negative',
      color: 'var(--color-danger)',
    })
  }

  if (activeIncidentCount > 0) {
    modifiers.push({
      name: `Active Incidents (${activeIncidentCount})`,
      icon: 'mdi:fire',
      severity: 'negative',
      color: 'var(--color-warning)',
    })
  }

  if (idleDwellerCount >= IDLE_DWELLER_TREND_THRESHOLD) {
    modifiers.push({
      name: `Idle Dwellers (${idleDwellerCount})`,
      icon: 'mdi:sleep',
      severity: 'negative',
      color: 'var(--color-warning)',
    })
  }

  if (radioHappinessMode) {
    modifiers.push({
      name: 'Radio Happiness Mode',
      icon: 'mdi:radio',
      severity: 'positive',
      color: 'var(--color-theme-primary)',
    })
  }

  return modifiers.slice(0, 5) // Show top 5
})

const hasNegativeModifiers = computed(() => {
  return activeModifiers.value.some((m) => m.severity === 'negative')
})

const distributionPercentage = (count: number) => {
  if (dwellerCount === 0) return 0
  return Math.round((count / dwellerCount) * 100)
}
</script>

<template>
  <UCard v-if="loading" padding="sm" class="happiness-dashboard">
    <USkeleton width="100%" height="120px" rounded="lg" />
  </UCard>
  <UCard v-else padding="sm" class="happiness-dashboard">
    <div class="dashboard-content compact-dashboard">
      <!-- Main Happiness Gauge -->
      <div class="happiness-gauge">
        <div class="gauge-container">
          <svg class="gauge-svg" viewBox="0 0 160 160">
            <!-- Background circle -->
            <circle
              cx="80"
              cy="80"
              r="65"
              fill="none"
              stroke="rgba(107, 114, 128, 0.3)"
              stroke-width="10"
            />
            <!-- Progress circle -->
            <circle
              cx="80"
              cy="80"
              r="65"
              fill="none"
              :stroke="happinessColor"
              stroke-width="10"
              stroke-linecap="round"
              :stroke-dasharray="`${(vaultHappiness / 100) * 408.4} 408.4`"
              transform="rotate(-90 80 80)"
              class="gauge-progress"
            />
          </svg>
          <div class="gauge-center">
            <div class="gauge-value-row">
              <div class="gauge-trend">
                <Icon :icon="trendIcon" :style="{ color: trendColor }" />
              </div>
              <div class="gauge-value" :style="{ color: happinessColor }">
                {{ vaultHappiness }}%
              </div>
            </div>
            <div class="gauge-label" :style="{ color: happinessColor }">
              {{ happinessLabel }}
            </div>
          </div>
        </div>
      </div>

      <!-- Dweller Distribution -->
      <div class="distribution-section">
        <h4 class="section-title">DWELLER DISTRIBUTION</h4>
        <div class="distribution-bars">
          <div class="distribution-item">
            <div class="distribution-header">
              <span class="distribution-label text-theme-primary">High (75-100)</span>
              <span class="distribution-count"
                >{{ dwellerDistribution.high }} ({{
                  distributionPercentage(dwellerDistribution.high)
                }}%)</span
              >
            </div>
            <div class="distribution-bar">
              <div
                class="distribution-fill bg-theme-primary"
                :style="{
                  width: `${distributionPercentage(dwellerDistribution.high)}%`,
                }"
              ></div>
            </div>
          </div>

            <div class="distribution-item">
            <div class="distribution-header">
              <span class="distribution-label text-terminal-green-dark">Medium (50-74)</span>
              <span class="distribution-count"
                >{{ dwellerDistribution.medium }} ({{
                  distributionPercentage(dwellerDistribution.medium)
                }}%)</span
              >
            </div>
            <div class="distribution-bar">
              <div
                class="distribution-fill bg-terminal-green-dark"
                :style="{
                  width: `${distributionPercentage(dwellerDistribution.medium)}%`,
                }"
              ></div>
            </div>
          </div>

          <div class="distribution-item">
            <div class="distribution-header">
              <span class="distribution-label text-warning">Low (25-49)</span>
              <span class="distribution-count"
                >{{ dwellerDistribution.low }} ({{
                  distributionPercentage(dwellerDistribution.low)
                }}%)</span
              >
            </div>
            <div class="distribution-bar">
              <div
                class="distribution-fill bg-warning"
                :style="{
                  width: `${distributionPercentage(dwellerDistribution.low)}%`,
                }"
              ></div>
            </div>
          </div>

          <div class="distribution-item">
            <div class="distribution-header">
              <span class="distribution-label text-danger">Critical (10-24)</span>
              <span class="distribution-count"
                >{{ dwellerDistribution.critical }} ({{
                  distributionPercentage(dwellerDistribution.critical)
                }}%)</span
              >
            </div>
            <div class="distribution-bar">
              <div
                class="distribution-fill bg-danger"
                :style="{
                  width: `${distributionPercentage(dwellerDistribution.critical)}%`,
                }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- Active Modifiers -->
      <div v-if="activeModifiers.length > 0" class="modifiers-section">
        <h4 class="section-title">ACTIVE MODIFIERS</h4>
        <div class="modifiers-list">
          <div
            v-for="(modifier, index) in activeModifiers"
            :key="index"
            class="modifier-item"
            :class="modifier.severity"
          >
            <Icon :icon="modifier.icon" :style="{ color: modifier.color }" class="modifier-icon" />
            <span class="modifier-name">{{ modifier.name }}</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions Footer -->
    <template #footer>
      <div v-if="hasNegativeModifiers" class="actions-footer">
        <h4 class="footer-title">QUICK ACTIONS</h4>
        <div class="actions-grid">
          <UButton
            v-if="idleDwellerCount > 0"
            variant="secondary"
            size="sm"
            @click="emit('assign-idle')"
            class="action-button"
          >
            <Icon icon="mdi:account-arrow-right" class="action-icon" />
            Assign Idle Dwellers
          </UButton>

          <UButton
            v-if="!radioHappinessMode"
            variant="secondary"
            size="sm"
            @click="emit('activate-radio')"
            class="action-button"
          >
            <Icon icon="mdi:radio" class="action-icon" />
            Activate Radio Mode
          </UButton>

          <UButton
            v-if="dwellerDistribution.critical > 0 || dwellerDistribution.low > 0"
            variant="secondary"
            size="sm"
            @click="emit('view-low-happiness')"
            class="action-button"
          >
            <Icon icon="mdi:account-alert" class="action-icon" />
            View Low Happiness
          </UButton>
        </div>
      </div>
      <div v-else class="footer-hint">
        <Icon icon="mdi:check-circle" class="hint-icon" />
        <span>All vault metrics are optimal</span>
      </div>
    </template>
  </UCard>
</template>

<style scoped>
.happiness-dashboard {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.compact-dashboard {
  display: grid;
  grid-template-columns: minmax(7.5rem, 10rem) minmax(0, 1fr);
  align-items: center;
  column-gap: 1.25rem;
  row-gap: 1rem;
}

/* Happiness Gauge */
.happiness-gauge {
  display: flex;
  justify-content: center;
  align-items: center;
}

.gauge-container {
  position: relative;
  width: 120px;
  height: 120px;
}

.gauge-svg {
  width: 100%;
  height: 100%;
}

.gauge-progress {
  transition:
    stroke-dasharray 0.5s ease,
    stroke 0.3s ease;
  filter: drop-shadow(0 0 8px currentColor);
}

.gauge-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.gauge-value-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.25rem;
}

.gauge-value {
  font-size: 1.625rem;
  font-weight: 700;
  line-height: 1;
  text-shadow: 0 0 10px currentColor;
}

.gauge-label {
  font-size: 0.75rem;
  font-weight: 600;
  margin-top: 0.25rem;
  letter-spacing: 0.1em;
}

.gauge-trend {
  display: flex;
  font-size: 1.125rem;
}

/* Distribution Section */
.distribution-section {
  min-width: 0;
}

.section-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 1rem;
}

.distribution-bars {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.distribution-item {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.distribution-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
}

.distribution-label {
  font-weight: 600;
}

.distribution-count {
  color: var(--color-gray-400);
}

.distribution-bar {
  height: 8px;
  background: rgba(107, 114, 128, 0.3);
  border-radius: 4px;
  overflow: hidden;
}

.distribution-fill {
  height: 100%;
  transition: width 0.5s ease;
  border-radius: 4px;
  box-shadow: 0 0 8px currentColor;
}

/* Modifiers Section */
.modifiers-section {
  grid-column: 1 / -1;
}

.modifiers-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.modifier-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.3);
  border-radius: 0.25rem;
  font-size: 0.875rem;
}

.modifier-item.negative {
  border-left: 2px solid var(--color-danger);
}

.modifier-item.positive {
  border-left: 2px solid var(--color-theme-primary);
}

.modifier-icon {
  font-size: 1.25rem;
}

.modifier-name {
  color: var(--color-gray-200);
}

/* Footer Actions Section */
.actions-footer {
  padding-top: 0.75rem;
  border-top: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
}

.footer-title {
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  margin-bottom: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.footer-hint {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
}

.hint-icon {
  font-size: 1.25rem;
}

.actions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 0.75rem;
}

.action-button {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  justify-content: center;
  white-space: nowrap;
}

.action-icon {
  font-size: 1.125rem;
}

/* Responsive */
@media (max-width: 640px) {
  .compact-dashboard {
    grid-template-columns: 1fr;
  }

  .gauge-container {
    width: 110px;
    height: 110px;
  }

  .gauge-value {
    font-size: 1.5rem;
  }

  .actions-grid {
    grid-template-columns: 1fr;
  }

}
</style>
