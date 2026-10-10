<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import { Card } from '@/core/components/ui/card'
import { Skeleton } from '@/core/components/ui/skeleton'
import { getHappinessColor, getHappinessLevel } from '@/modules/dwellers/models/dweller'

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
  severelyIrradiatedDwellerCount?: number
  treatingDwellers?: boolean
  loading?: boolean
}

const {
  idleDwellerCount = 0,
  activeIncidentCount = 0,
  lowResourceCount = 0,
  radioHappinessMode = false,
  severelyIrradiatedDwellerCount = 0,
  treatingDwellers = false,
  loading = false,
  distribution,
  dwellerCount,
  vaultHappiness,
} = defineProps<Props>()

const emit = defineEmits<{
  (e: 'assign-idle'): void
  (e: 'activate-radio'): void
  (e: 'view-low-happiness'): void
  (e: 'treat-irradiated'): void
}>()

const dwellerDistribution = computed<DwellerDistribution>(() => distribution)

const happinessLevel = computed(() => getHappinessLevel(vaultHappiness))

const happinessColor = computed(() => getHappinessColor(happinessLevel.value))

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

// Treatment is only prompted once more than one dweller is severely irradiated
const TREATMENT_MIN_SEVERE_COUNT = 2

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

const showTreatmentAction = computed(
  () => severelyIrradiatedDwellerCount >= TREATMENT_MIN_SEVERE_COUNT
)

const distributionPercentage = (count: number) => {
  if (dwellerCount === 0) return 0
  return Math.round((count / dwellerCount) * 100)
}

interface DistributionBand {
  key: keyof DwellerDistribution
  label: string
  count: number
  percent: number
  barClass: string
  labelClass: string
}

// Ordered high → critical; drives both the stacked proportion bar and its legend.
const distributionBands = computed<DistributionBand[]>(() => {
  const bands: Array<Omit<DistributionBand, 'count' | 'percent'>> = [
    {
      key: 'high',
      label: 'High (75-100)',
      barClass: 'band-fill-high',
      labelClass: 'band-text-high',
    },
    {
      key: 'medium',
      label: 'Medium (50-74)',
      barClass: 'band-fill-medium',
      labelClass: 'band-text-medium',
    },
    {
      key: 'low',
      label: 'Low (25-49)',
      barClass: 'band-fill-low',
      labelClass: 'band-text-low',
    },
    {
      key: 'critical',
      label: 'Critical (10-24)',
      barClass: 'band-fill-critical',
      labelClass: 'band-text-critical',
    },
  ]
  return bands.map((band) => ({
    ...band,
    count: dwellerDistribution.value[band.key],
    percent: distributionPercentage(dwellerDistribution.value[band.key]),
  }))
})

const distributionAriaLabel = computed(() =>
  distributionBands.value.map((b) => `${b.label}: ${b.count} (${b.percent}%)`).join(', ')
)
</script>

<template>
  <Card
    v-if="loading"
    class="happiness-dashboard gap-0 rounded-lg border-2 border-theme-primary/20 bg-surface-raised p-4 shadow-none ring-0"
  >
    <Skeleton :style="{ width: '100%', height: '120px' }" class="rounded-lg" />
  </Card>
  <Card
    v-else
    class="happiness-dashboard gap-0 rounded-lg border-2 border-theme-primary/20 bg-surface-raised p-4 shadow-none ring-0"
  >
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
        <div class="distribution-stacked" role="img" :aria-label="distributionAriaLabel">
          <div
            v-for="band in distributionBands"
            :key="band.key"
            class="distribution-segment"
            :class="[band.barClass, band.labelClass]"
            :style="{ width: `${band.percent}%` }"
          ></div>
        </div>
        <div class="distribution-legend">
          <div v-for="band in distributionBands" :key="band.key" class="legend-item">
            <span class="legend-dot" :class="[band.barClass, band.labelClass]"></span>
            <span class="legend-label" :class="band.labelClass">{{ band.label }}</span>
            <span class="legend-count tabular-nums">{{ band.count }} ({{ band.percent }}%)</span>
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
            <span class="modifier-tag" :class="modifier.severity">
              {{ modifier.severity === 'negative' ? 'NEGATIVE' : 'POSITIVE' }}
            </span>
          </div>
        </div>
      </div>
    </div>

    <!-- Quick Actions Footer -->
    <div v-if="hasNegativeModifiers || showTreatmentAction" class="actions-footer">
      <h4 class="section-title">QUICK ACTIONS</h4>
      <div class="actions-grid">
        <Button
          v-if="showTreatmentAction"
          variant="outline"
          size="sm"
          :disabled="treatingDwellers"
          @click="emit('treat-irradiated')"
          class="action-button border-2 border-theme-primary bg-transparent hover:shadow-glow-md"
        >
          <Icon v-if="treatingDwellers" icon="mdi:loading" class="action-icon animate-spin" />
          <Icon v-else icon="mdi:radiation" class="action-icon" />
          Treat Irradiated Dwellers
        </Button>

        <Button
          v-if="idleDwellerCount > 0"
          variant="outline"
          size="sm"
          @click="emit('assign-idle')"
          class="action-button border-2 border-theme-primary bg-transparent hover:shadow-glow-md"
        >
          <Icon icon="mdi:account-arrow-right" class="action-icon" />
          Assign Idle Dwellers
        </Button>

        <Button
          v-if="!radioHappinessMode"
          variant="outline"
          size="sm"
          @click="emit('activate-radio')"
          class="action-button border-2 border-theme-primary bg-transparent hover:shadow-glow-md"
        >
          <Icon icon="mdi:radio" class="action-icon" />
          Activate Radio Mode
        </Button>

        <Button
          v-if="dwellerDistribution.critical > 0 || dwellerDistribution.low > 0"
          variant="outline"
          size="sm"
          @click="emit('view-low-happiness')"
          class="action-button border-2 border-theme-primary bg-transparent hover:shadow-glow-md"
        >
          <Icon icon="mdi:account-alert" class="action-icon" />
          View Low Happiness
        </Button>
      </div>
    </div>
    <div v-else class="footer-hint">
      <Icon icon="mdi:check-circle" class="hint-icon" />
      <span>All vault metrics are optimal</span>
    </div>
  </Card>
</template>

<style scoped>
.happiness-dashboard {
  background: var(--color-surface-sunken);
  border-color: rgb(from var(--color-theme-primary) r g b / 0.4);
}

.compact-dashboard {
  display: grid;
  grid-template-columns: minmax(6rem, 8rem) minmax(0, 1fr);
  align-items: center;
  column-gap: 1.25rem;
  row-gap: 1rem;
}

.happiness-gauge {
  display: flex;
  justify-content: center;
  align-items: center;
}

.gauge-container {
  position: relative;
  width: 96px;
  height: 96px;
}

.gauge-svg {
  width: 100%;
  height: 100%;
  overflow: visible;
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
  font-size: 1.375rem;
  font-weight: 700;
  line-height: 1;
  font-variant-numeric: tabular-nums;
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
  margin-bottom: 0.75rem;
}

.distribution-stacked {
  display: flex;
  gap: 2px;
  height: 10px;
  margin-bottom: 0.5rem;
  padding: 1px;
  background: var(--color-surface-sunken);
  border: 1px solid var(--color-theme-glow);
  border-radius: 0.25rem;
  overflow: hidden;
}

.distribution-segment {
  height: 100%;
  border-radius: 2px;
  transition: width 0.5s ease;
  box-shadow: 0 0 6px currentColor;
}

.distribution-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 0.375rem 1rem;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 0.375rem;
  font-size: 0.75rem;
}

.legend-dot {
  width: 0.5rem;
  height: 0.5rem;
  border-radius: 9999px;
  box-shadow: 0 0 4px currentColor;
}

.legend-label {
  font-weight: 600;
}

.legend-count {
  color: var(--color-theme-primary);
  opacity: 0.6;
}

/* Distribution band colors live here (scoped, code-split) rather than as global
   Tailwind utilities, so the critical-path CSS budget is untouched. Green →
   amber → orange → red, fixed regardless of the active vault theme. */
.band-fill-high {
  background: var(--color-happiness-high);
}
.band-text-high {
  color: var(--color-happiness-high);
}
.band-fill-medium {
  background: var(--color-warning);
}
.band-text-medium {
  color: var(--color-warning);
}
.band-fill-low {
  background: var(--color-quest-locked);
}
.band-text-low {
  color: var(--color-quest-locked);
}
.band-fill-critical {
  background: var(--color-danger);
}
.band-text-critical {
  color: var(--color-danger);
}

/* Modifiers Section */
.modifiers-section {
  grid-column: 1 / -1;
  margin-top: 0.25rem;
  padding-top: 1rem;
  border-top: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
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
  padding: 0.5rem 0.625rem;
  background: var(--color-surface-sunken);
  border-radius: 0.25rem;
  font-size: 0.875rem;
}

.modifier-item.negative {
  border-left: 2px solid var(--color-danger);
  background: color-mix(in srgb, var(--color-danger) 8%, var(--color-surface-sunken));
}

.modifier-item.positive {
  border-left: 2px solid var(--color-theme-primary);
  background: color-mix(in srgb, var(--color-theme-primary) 8%, var(--color-surface-sunken));
}

.modifier-icon {
  font-size: 1.25rem;
}

.modifier-name {
  color: color-mix(in srgb, var(--color-theme-primary) 75%, transparent);
}

.modifier-tag {
  margin-left: auto;
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}

.modifier-tag.negative {
  color: var(--color-danger);
}

.modifier-tag.positive {
  color: var(--color-theme-primary);
}

/* Footer Actions Section */
.actions-footer {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
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
