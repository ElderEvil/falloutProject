<script setup lang="ts">
import { computed } from 'vue';
import { Icon } from '@iconify/vue';
import UCard from '@/components/ui/UCard.vue';
import UButton from '@/components/ui/UButton.vue';

interface DwellerDistribution {
  high: number;    // 75-100
  medium: number;  // 50-74
  low: number;     // 25-49
  critical: number; // 10-24
}

interface Props {
  vaultHappiness: number;
  dwellerCount: number;
  distribution: DwellerDistribution;
  idleDwellerCount?: number;
  activeIncidentCount?: number;
  lowResourceCount?: number;
  radioHappinessMode?: boolean;
  loading?: boolean;
}

const props = withDefaults(defineProps<Props>(), {
  idleDwellerCount: 0,
  activeIncidentCount: 0,
  lowResourceCount: 0,
  radioHappinessMode: false,
  loading: false,
});

const emit = defineEmits<{
  (e: 'assign-idle'): void;
  (e: 'activate-radio'): void;
  (e: 'view-low-happiness'): void;
}>();

const dwellerDistribution = computed<DwellerDistribution>(() => props.distribution);

const happinessLevel = computed(() => {
  const h = props.vaultHappiness;
  if (h >= 75) return 'high';
  if (h >= 50) return 'medium';
  if (h >= 25) return 'low';
  return 'critical';
});

const happinessColor = computed(() => {
  switch (happinessLevel.value) {
    case 'high': return 'var(--color-theme-primary)';
    case 'medium': return '#4ade80';
    case 'low': return '#fbbf24';
    case 'critical': return '#ef4444';
    default: return 'var(--color-theme-primary)';
  }
});

const happinessLabel = computed(() => {
  switch (happinessLevel.value) {
    case 'high': return 'EXCELLENT';
    case 'medium': return 'GOOD';
    case 'low': return 'POOR';
    case 'critical': return 'CRITICAL';
    default: return 'UNKNOWN';
  }
});

// TODO (v1.14): Calculate trend from historical data
const happinessTrend = computed(() => {
  // For now, show stable
  return 'stable'; // 'increasing' | 'decreasing' | 'stable'
});

const trendIcon = computed(() => {
  switch (happinessTrend.value) {
    case 'increasing': return 'mdi:trending-up';
    case 'decreasing': return 'mdi:trending-down';
    default: return 'mdi:trending-neutral';
  }
});

const trendColor = computed(() => {
  switch (happinessTrend.value) {
    case 'increasing': return 'var(--color-theme-primary)';
    case 'decreasing': return '#ef4444';
    default: return '#9ca3af';
  }
});

// Active modifiers affecting happiness
const activeModifiers = computed(() => {
  const modifiers = [];

  if (props.lowResourceCount > 0) {
    modifiers.push({
      name: 'Low Resources',
      icon: 'mdi:alert-circle',
      severity: 'negative',
      color: '#ef4444',
    });
  }

  if (props.activeIncidentCount > 0) {
    modifiers.push({
      name: `Active Incidents (${props.activeIncidentCount})`,
      icon: 'mdi:fire',
      severity: 'negative',
      color: '#f97316',
    });
  }

  if (props.idleDwellerCount > 0) {
    modifiers.push({
      name: `Idle Dwellers (${props.idleDwellerCount})`,
      icon: 'mdi:sleep',
      severity: 'negative',
      color: '#fbbf24',
    });
  }

  if (props.radioHappinessMode) {
    modifiers.push({
      name: 'Radio Happiness Mode',
      icon: 'mdi:radio',
      severity: 'positive',
      color: 'var(--color-theme-primary)',
    });
  }

  return modifiers.slice(0, 5); // Show top 5
});

const hasNegativeModifiers = computed(() => {
  return activeModifiers.value.some(m => m.severity === 'negative');
});

const distributionPercentage = (count: number) => {
  if (props.dwellerCount === 0) return 0;
  return Math.round((count / props.dwellerCount) * 100);
};
</script>

<template>
  <UCard class="happiness-dashboard">
    <div class="dashboard-content">
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
            <div class="gauge-value" :style="{ color: happinessColor }">
              {{ vaultHappiness }}%
            </div>
            <div class="gauge-label" :style="{ color: happinessColor }">
              {{ happinessLabel }}
            </div>
            <div class="gauge-trend">
              <Icon :icon="trendIcon" :style="{ color: trendColor }" />
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
              <span class="distribution-label" style="color: var(--color-theme-primary)">High (75-100)</span>
              <span class="distribution-count">{{ dwellerDistribution.high }} ({{ distributionPercentage(dwellerDistribution.high) }}%)</span>
            </div>
            <div class="distribution-bar">
              <div
                class="distribution-fill"
                :style="{
                  width: `${distributionPercentage(dwellerDistribution.high)}%`,
                  backgroundColor: 'var(--color-theme-primary)'
                }"
              ></div>
            </div>
          </div>

          <div class="distribution-item">
            <div class="distribution-header">
              <span class="distribution-label" style="color: #4ade80">Medium (50-74)</span>
              <span class="distribution-count">{{ dwellerDistribution.medium }} ({{ distributionPercentage(dwellerDistribution.medium) }}%)</span>
            </div>
            <div class="distribution-bar">
              <div
                class="distribution-fill"
                :style="{
                  width: `${distributionPercentage(dwellerDistribution.medium)}%`,
                  backgroundColor: '#4ade80'
                }"
              ></div>
            </div>
          </div>

          <div class="distribution-item">
            <div class="distribution-header">
              <span class="distribution-label" style="color: #fbbf24">Low (25-49)</span>
              <span class="distribution-count">{{ dwellerDistribution.low }} ({{ distributionPercentage(dwellerDistribution.low) }}%)</span>
            </div>
            <div class="distribution-bar">
              <div
                class="distribution-fill"
                :style="{
                  width: `${distributionPercentage(dwellerDistribution.low)}%`,
                  backgroundColor: '#fbbf24'
                }"
              ></div>
            </div>
          </div>

          <div class="distribution-item">
            <div class="distribution-header">
              <span class="distribution-label" style="color: #ef4444">Critical (10-24)</span>
              <span class="distribution-count">{{ dwellerDistribution.critical }} ({{ distributionPercentage(dwellerDistribution.critical) }}%)</span>
            </div>
            <div class="distribution-bar">
              <div
                class="distribution-fill"
                :style="{
                  width: `${distributionPercentage(dwellerDistribution.critical)}%`,
                  backgroundColor: '#ef4444'
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

      <!-- Quick Actions -->
      <div v-if="hasNegativeModifiers" class="actions-section">
        <h4 class="section-title">QUICK ACTIONS</h4>
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
    </div>
  </UCard>
</template>

<style scoped>
.happiness-dashboard {
  background: rgba(0, 0, 0, 0.6);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.dashboard-content {
  display: flex;
  flex-direction: column;
  gap: 1.5rem;
}

/* Happiness Gauge */
.happiness-gauge {
  display: flex;
  justify-content: center;
  align-items: center;
  padding: 0.5rem;
}

.gauge-container {
  position: relative;
  width: 160px;
  height: 160px;
}

.gauge-svg {
  width: 100%;
  height: 100%;
}

.gauge-progress {
  transition: stroke-dasharray 0.5s ease, stroke 0.3s ease;
  filter: drop-shadow(0 0 8px currentColor);
}

.gauge-center {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  text-align: center;
}

.gauge-value {
  font-size: 2rem;
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
  font-size: 1.25rem;
  margin-top: 0.25rem;
}

/* Distribution Section */
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
  color: #9ca3af;
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
  border-left: 2px solid #ef4444;
}

.modifier-item.positive {
  border-left: 2px solid var(--color-theme-primary);
}

.modifier-icon {
  font-size: 1.25rem;
}

.modifier-name {
  color: #e5e7eb;
}

/* Actions Section */
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
  .gauge-container {
    width: 140px;
    height: 140px;
  }

  .gauge-value {
    font-size: 1.75rem;
  }

  .actions-grid {
    grid-template-columns: 1fr;
  }

  .dashboard-content {
    gap: 1rem;
  }
}
</style>
