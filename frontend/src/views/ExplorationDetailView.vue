<script setup lang="ts">
import { ref, computed, onMounted, onUnmounted, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import { useExplorationStore } from '@/stores/exploration'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { Icon } from '@iconify/vue'
import ExplorationRewardsModal from '@/components/exploration/ExplorationRewardsModal.vue'
import type { RewardsSummary } from '@/stores/exploration'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()
const dwellerStore = useDwellerStore()
const explorationStore = useExplorationStore()
const vaultStore = useVaultStore()

const vaultId = computed(() => route.params.id as string)
const explorationId = computed(() => route.params.explorationId as string)

// Rewards modal state
const showRewardsModal = ref(false)
const completedExplorationRewards = ref<RewardsSummary | null>(null)
const completedDwellerName = ref('')

// Current exploration and dweller
const exploration = computed(() => {
  return explorationStore.activeExplorations[explorationId.value]
})

const dweller = computed(() => {
  if (!exploration.value) return null
  return dwellerStore.dwellers.find((d) => d.id === exploration.value.dweller_id)
})

const dwellerName = computed(() => {
  if (!dweller.value) return 'Unknown'
  return `${dweller.value.first_name} ${dweller.value.last_name}`
})

// Navigation between explorers
const allExplorations = computed(() => {
  return Object.values(explorationStore.activeExplorations)
})

const currentIndex = computed(() => {
  return allExplorations.value.findIndex((e) => e.id === explorationId.value)
})

const hasPrevious = computed(() => currentIndex.value > 0)
const hasNext = computed(() => currentIndex.value < allExplorations.value.length - 1)

const navigatePrevious = () => {
  if (hasPrevious.value) {
    const prevExploration = allExplorations.value[currentIndex.value - 1]
    router.push(`/vault/${vaultId.value}/exploration/${prevExploration.id}`)
  }
}

const navigateNext = () => {
  if (hasNext.value) {
    const nextExploration = allExplorations.value[currentIndex.value + 1]
    router.push(`/vault/${vaultId.value}/exploration/${nextExploration.id}`)
  }
}

const goBack = () => {
  router.push(`/vault/${vaultId.value}/exploration`)
}

// Progress calculation
const progressPercentage = computed(() => {
  if (!exploration.value) return 0
  const now = Date.now()
  let startTimeStr = exploration.value.start_time
  if (!startTimeStr.endsWith('Z')) {
    startTimeStr = startTimeStr.replace(' ', 'T') + 'Z'
  }
  const start = new Date(startTimeStr).getTime()
  const duration = exploration.value.duration * 3600 * 1000
  const elapsed = now - start
  return Math.min(100, (elapsed / duration) * 100)
})

const timeRemaining = computed(() => {
  if (!exploration.value) return ''
  const progress = progressPercentage.value
  if (progress >= 100) return 'Complete!'

  const totalDuration = exploration.value.duration * 3600
  const remaining = totalDuration * (1 - progress / 100)

  const hours = Math.floor(remaining / 3600)
  const minutes = Math.floor((remaining % 3600) / 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m remaining`
  }
  return `${minutes}m remaining`
})

// Events sorted by timestamp (most recent first)
const sortedEvents = computed(() => {
  if (!exploration.value?.events || exploration.value.events.length === 0) {
    return []
  }
  return [...exploration.value.events].reverse()
})

const getEventIcon = (eventType: string): string => {
  const iconMap: Record<string, string> = {
    combat: 'mdi:sword-cross',
    loot: 'mdi:treasure-chest',
    exploration: 'mdi:map-marker',
    discovery: 'mdi:eye',
    encounter: 'mdi:account-alert',
    danger: 'mdi:alert',
    rest: 'mdi:sleep',
    default: 'mdi:circle-medium'
  }
  return iconMap[eventType] || iconMap.default
}

const getEventColor = (eventType: string): string => {
  const colorMap: Record<string, string> = {
    combat: '#ff4444',
    loot: '#FFD700',
    exploration: 'var(--color-theme-primary)',
    discovery: '#4169E1',
    encounter: '#ff9900',
    danger: '#ff0000',
    rest: '#00ced1',
    default: 'var(--color-theme-primary)'
  }
  return colorMap[eventType] || colorMap.default
}

const formatEventTime = (hours: number): string => {
  const h = Math.floor(hours)
  const m = Math.floor((hours - h) * 60)
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}`
}

// Actions
const handleCompleteExploration = async () => {
  if (!authStore.token || !exploration.value) return

  try {
    const result = await explorationStore.completeExploration(exploration.value.id, authStore.token)

    if (result?.rewards_summary) {
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = dwellerName.value
      showRewardsModal.value = true
    }

    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }

    // Navigate back to exploration list
    setTimeout(() => {
      goBack()
    }, 500)
  } catch (error) {
    console.error('Failed to complete exploration:', error)
  }
}

const handleRecallExploration = async () => {
  if (!authStore.token || !exploration.value) return

  try {
    const result = await explorationStore.recallDweller(exploration.value.id, authStore.token)

    if (result?.rewards_summary) {
      completedExplorationRewards.value = result.rewards_summary
      completedDwellerName.value = dwellerName.value
      showRewardsModal.value = true
    }

    if (vaultId.value) {
      await vaultStore.refreshVault(vaultId.value, authStore.token)
      await dwellerStore.fetchDwellersByVault(vaultId.value, authStore.token)
    }

    // Navigate back to exploration list
    setTimeout(() => {
      goBack()
    }, 500)
  } catch (error) {
    console.error('Failed to recall dweller:', error)
  }
}

const closeRewardsModal = () => {
  showRewardsModal.value = false
  completedExplorationRewards.value = null
  completedDwellerName.value = ''
}

// Auto-refresh every 10 seconds
let pollInterval: ReturnType<typeof setInterval> | null = null
onMounted(async () => {
  if (vaultId.value && authStore.token) {
    await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)
  }

  pollInterval = setInterval(async () => {
    if (vaultId.value && authStore.token) {
      await explorationStore.fetchExplorationsByVault(vaultId.value, authStore.token)
    }
  }, 10000)
})

onUnmounted(() => {
  if (pollInterval) {
    clearInterval(pollInterval)
  }
})

// Watch for exploration completion
watch(() => progressPercentage.value, (newProgress) => {
  if (newProgress >= 100 && exploration.value?.status === 'active') {
    // Auto-complete when progress reaches 100%
    handleCompleteExploration()
  }
})
</script>

<template>
  <div class="exploration-detail-view">
    <!-- Navigation Bar -->
    <div class="nav-bar">
      <button @click="goBack" class="nav-btn back-btn">
        <Icon icon="mdi:arrow-left" />
        Back
      </button>
      <div class="explorer-counter">
        {{ currentIndex + 1 }} / {{ allExplorations.length }}
      </div>
      <div class="nav-arrows">
        <button
          @click="navigatePrevious"
          class="nav-btn arrow-btn"
          :disabled="!hasPrevious"
          :class="{ disabled: !hasPrevious }"
        >
          <Icon icon="mdi:chevron-left" />
        </button>
        <button
          @click="navigateNext"
          class="nav-btn arrow-btn"
          :disabled="!hasNext"
          :class="{ disabled: !hasNext }"
        >
          <Icon icon="mdi:chevron-right" />
        </button>
      </div>
    </div>

    <!-- Main Content -->
    <div v-if="exploration && dweller" class="detail-content">
      <!-- Top Section: Dweller Info & Progress -->
      <div class="top-section">
        <!-- Dweller Portrait Card -->
        <div class="dweller-card">
          <div class="dweller-portrait">
            <Icon icon="mdi:account" class="portrait-icon" />
            <div class="dweller-level">LVL {{ dweller.level }}</div>
          </div>
          <div class="dweller-info">
            <h2 class="dweller-name">{{ dwellerName }}</h2>
            <div class="dweller-stats">
              <div class="stat-bar">
                <span class="stat-label">Health</span>
                <div class="stat-bar-bg">
                  <div
                    class="stat-bar-fill health"
                    :style="{ width: `${(dweller.health / dweller.max_health) * 100}%` }"
                  ></div>
                </div>
                <span class="stat-value">{{ dweller.health }}/{{ dweller.max_health }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Progress Section -->
        <div class="progress-section">
          <h3 class="section-title">
            <Icon icon="mdi:compass" class="mr-2" />
            Exploring Wasteland - {{ exploration.duration }}h
          </h3>
          <div class="progress-bar-large">
            <div
              class="progress-fill"
              :style="{ width: `${progressPercentage}%` }"
            ></div>
          </div>
          <div class="progress-info">
            <span class="progress-text">{{ Math.round(progressPercentage) }}% Complete</span>
            <span class="progress-time">{{ timeRemaining }}</span>
          </div>
        </div>

        <!-- Stats Grid -->
        <div class="stats-grid">
          <div class="stat-box">
            <Icon icon="mdi:map-marker-distance" class="stat-icon" />
            <div class="stat-content">
              <div class="stat-number">{{ exploration.total_distance }}</div>
              <div class="stat-label">Miles</div>
            </div>
          </div>
          <div class="stat-box">
            <Icon icon="mdi:treasure-chest" class="stat-icon" />
            <div class="stat-content">
              <div class="stat-number">{{ exploration.loot_collected?.length || 0 }}</div>
              <div class="stat-label">Items</div>
            </div>
          </div>
          <div class="stat-box">
            <Icon icon="mdi:currency-usd" class="stat-icon gold" />
            <div class="stat-content">
              <div class="stat-number">{{ exploration.total_caps_found }}</div>
              <div class="stat-label">Caps</div>
            </div>
          </div>
          <div class="stat-box">
            <Icon icon="mdi:skull" class="stat-icon danger" />
            <div class="stat-content">
              <div class="stat-number">{{ exploration.enemies_encountered }}</div>
              <div class="stat-label">Enemies</div>
            </div>
          </div>
        </div>
      </div>

      <!-- Event Log Section -->
      <div class="event-log-section">
        <h3 class="section-title">
          <Icon icon="mdi:timeline-text" class="mr-2" />
          Event Log
        </h3>
        <div class="event-log">
          <div v-if="sortedEvents.length === 0" class="no-events">
            <Icon icon="mdi:clock-outline" class="no-events-icon" />
            <p>No events yet. Adventure is just beginning...</p>
          </div>
          <div v-else class="event-list">
            <div
              v-for="(event, index) in sortedEvents"
              :key="index"
              class="event-row"
              :style="{ borderLeftColor: getEventColor(event.type) }"
            >
              <span class="event-time">{{ formatEventTime(event.time_elapsed_hours) }}</span>
              <Icon
                :icon="getEventIcon(event.type)"
                class="event-icon"
                :style="{ color: getEventColor(event.type) }"
              />
              <div class="event-content-wrapper">
                <div class="event-header-inline">
                  <span
                    class="event-type-badge"
                    :style="{
                      backgroundColor: getEventColor(event.type) + '20',
                      borderColor: getEventColor(event.type),
                      color: getEventColor(event.type)
                    }"
                  >
                    {{ event.type.toUpperCase() }}
                  </span>
                </div>
                <span class="event-text">{{ event.description }}</span>
              </div>
            </div>
          </div>
        </div>
      </div>

      <!-- Equipment Section (Bottom) -->
      <div class="equipment-section">
        <div class="equipment-slot">
          <Icon icon="mdi:hanger" class="equipment-icon" />
          <span class="equipment-label">{{ dweller.outfit?.name || 'No Outfit' }}</span>
        </div>
      </div>

      <!-- Action Buttons -->
      <div class="action-buttons">
        <button
          v-if="progressPercentage >= 100"
          @click="handleCompleteExploration"
          class="action-btn complete-btn"
        >
          <Icon icon="mdi:check-circle" class="btn-icon" />
          Complete Exploration
        </button>
        <button
          @click="handleRecallExploration"
          class="action-btn recall-btn"
        >
          <Icon icon="mdi:arrow-u-left-top" class="btn-icon" />
          Recall Dweller
        </button>
      </div>
    </div>

    <!-- Loading/Error State -->
    <div v-else class="loading-state">
      <Icon icon="mdi:loading" class="loading-icon spin" />
      <p>Loading exploration data...</p>
    </div>

    <!-- Rewards Modal -->
    <ExplorationRewardsModal
      :show="showRewardsModal"
      :rewards="completedExplorationRewards"
      :dweller-name="completedDwellerName"
      @close="closeRewardsModal"
    />
  </div>
</template>

<style scoped>
.exploration-detail-view {
  min-height: 100vh;
  background: #000;
  font-family: 'Courier New', monospace;
  padding-bottom: 2rem;
}

.nav-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  background: rgba(0, 0, 0, 0.95);
  border-bottom: 3px solid var(--color-theme-primary);
  box-shadow: 0 2px 20px var(--color-theme-glow);
  position: sticky;
  top: 64px;
  z-index: 50;
}

.nav-btn {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.75rem 1.5rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
  font-size: 1rem;
  font-weight: 700;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.nav-btn:hover:not(.disabled) {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  box-shadow: 0 0 15px var(--color-theme-glow);
  transform: scale(1.05);
}

.nav-btn.disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

.explorer-counter {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
}

.nav-arrows {
  display: flex;
  gap: 0.5rem;
}

.arrow-btn {
  padding: 0.75rem 1rem;
  font-size: 1.5rem;
}

.detail-content {
  max-width: 1200px;
  margin: 0 auto;
  padding: 1rem;
}

.top-section {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.03);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.dweller-card {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
}

.dweller-portrait {
  position: relative;
  width: 70px;
  height: 70px;
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid var(--color-theme-primary);
  border-radius: 6px;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 0 15px var(--color-theme-glow);
  flex-shrink: 0;
}

.portrait-icon {
  width: 45px;
  height: 45px;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 8px var(--color-theme-glow));
}

.dweller-level {
  position: absolute;
  bottom: -6px;
  right: -6px;
  background: var(--color-theme-primary);
  color: #000;
  padding: 0.25rem 0.5rem;
  border-radius: 3px;
  font-size: 0.75rem;
  font-weight: 700;
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.dweller-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.dweller-name {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 10px var(--color-theme-glow);
  margin-bottom: 0.5rem;
}

.dweller-stats {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.stat-bar {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.stat-label {
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.8);
  min-width: 50px;
}

.stat-bar-bg {
  flex: 1;
  height: 16px;
  background: rgba(0, 0, 0, 0.7);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.4);
  border-radius: 3px;
  overflow: hidden;
}

.stat-bar-fill {
  height: 100%;
  transition: width 0.3s ease;
}

.stat-bar-fill.health {
  background: linear-gradient(90deg, var(--color-theme-primary), var(--color-theme-accent));
  box-shadow: 0 0 12px var(--color-theme-glow);
}

.stat-value {
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  min-width: 60px;
  text-align: right;
}

.progress-section {
  margin-bottom: 1rem;
}

.section-title {
  display: flex;
  align-items: center;
  font-size: 1rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
  margin-bottom: 0.5rem;
}

.progress-bar-large {
  height: 28px;
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid var(--color-theme-primary);
  border-radius: 6px;
  overflow: hidden;
  margin-bottom: 0.5rem;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, var(--color-theme-primary), var(--color-theme-accent));
  box-shadow: 0 0 15px var(--color-theme-glow);
  transition: width 0.5s ease;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  font-size: 0.875rem;
  font-weight: 700;
}

.progress-text {
  color: var(--color-theme-primary);
  text-shadow: 0 0 5px var(--color-theme-glow);
}

.progress-time {
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.8);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.5rem;
}

.stat-box {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 6px;
  transition: all 0.2s ease;
}

.stat-box:hover {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 12px var(--color-theme-glow);
  transform: translateY(-1px);
}

.stat-icon {
  width: 1.75rem;
  height: 1.75rem;
  color: var(--color-theme-primary);
  margin-bottom: 0.25rem;
  filter: drop-shadow(0 0 6px var(--color-theme-glow));
}

.stat-icon.gold {
  color: #FFD700;
}

.stat-icon.danger {
  color: #ff4444;
}

.stat-content {
  text-align: center;
}

.stat-number {
  font-size: 1.25rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.stat-box .stat-label {
  font-size: 0.625rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.event-log-section {
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid var(--color-theme-primary);
  border-radius: 8px;
  padding: 1rem;
  margin-bottom: 1rem;
  box-shadow: 0 0 20px var(--color-theme-glow);
}

.event-log {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.05);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 6px;
  padding: 1rem;
  max-height: 250px;
  overflow-y: auto;
}

.event-log::-webkit-scrollbar {
  width: 8px;
}

.event-log::-webkit-scrollbar-track {
  background: rgba(0, 0, 0, 0.5);
  border-radius: 4px;
}

.event-log::-webkit-scrollbar-thumb {
  background: var(--color-theme-primary);
  border-radius: 4px;
}

.no-events {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.5rem;
  padding: 2rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.5);
}

.no-events-icon {
  width: 2.5rem;
  height: 2.5rem;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.event-row {
  display: grid;
  grid-template-columns: 55px 28px 1fr;
  align-items: start;
  gap: 0.5rem;
  padding: 0.625rem;
  background: rgba(0, 0, 0, 0.5);
  border-left: 3px solid var(--color-theme-primary);
  border-radius: 4px;
  transition: all 0.2s ease;
}

.event-row:hover {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.08);
  transform: translateX(3px);
  box-shadow: 0 0 12px rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
}

.event-time {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 5px var(--color-theme-glow);
  font-variant-numeric: tabular-nums;
  padding-top: 0.125rem;
}

.event-icon {
  width: 1.25rem;
  height: 1.25rem;
  margin-top: 0.125rem;
  filter: drop-shadow(0 0 3px currentColor);
}

.event-content-wrapper {
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
}

.event-header-inline {
  display: flex;
  align-items: center;
  gap: 0.375rem;
}

.event-type-badge {
  display: inline-block;
  padding: 0.125rem 0.375rem;
  border: 1px solid;
  border-radius: 3px;
  font-size: 0.5625rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  text-shadow: 0 0 5px currentColor;
}

.event-text {
  font-size: 0.8125rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.9);
  line-height: 1.4;
}

.equipment-section {
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 6px;
  padding: 0.625rem;
  margin-bottom: 1rem;
}

.equipment-slot {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.05);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 4px;
}

.equipment-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-theme-primary);
}

.equipment-label {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 5px var(--color-theme-glow);
}

.action-buttons {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.action-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.875rem;
  font-size: 1rem;
  font-weight: 700;
  border-radius: 6px;
  cursor: pointer;
  transition: all 0.3s ease;
  font-family: 'Courier New', monospace;
  border: 2px solid;
}

.btn-icon {
  width: 1.5rem;
  height: 1.5rem;
}

.complete-btn {
  background: rgba(255, 215, 0, 0.1);
  border-color: #FFD700;
  color: #FFD700;
  text-shadow: 0 0 10px rgba(255, 215, 0, 0.6);
}

.complete-btn:hover {
  background: rgba(255, 215, 0, 0.2);
  box-shadow: 0 0 30px rgba(255, 215, 0, 0.5);
  transform: scale(1.05);
}

.recall-btn {
  background: rgba(255, 68, 68, 0.1);
  border-color: #ff4444;
  color: #ff4444;
  text-shadow: 0 0 10px rgba(255, 68, 68, 0.6);
}

.recall-btn:hover {
  background: rgba(255, 68, 68, 0.2);
  box-shadow: 0 0 30px rgba(255, 68, 68, 0.5);
  transform: scale(1.05);
}

.loading-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  min-height: 60vh;
  gap: 1.5rem;
  color: var(--color-theme-primary);
}

.loading-icon {
  width: 5rem;
  height: 5rem;
}

.spin {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  from {
    transform: rotate(0deg);
  }
  to {
    transform: rotate(360deg);
  }
}

/* Responsive */
@media (max-width: 1024px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .action-buttons {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .detail-content {
    padding: 1rem;
  }

  .top-section {
    padding: 1rem;
  }

  .dweller-card {
    flex-direction: column;
    align-items: center;
    text-align: center;
  }

  .dweller-name {
    font-size: 1.5rem;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .event-row {
    grid-template-columns: 60px 30px 1fr;
    gap: 0.5rem;
    padding: 0.75rem;
  }

  .nav-bar {
    padding: 0.75rem;
  }

  .explorer-counter {
    font-size: 1rem;
  }
}
</style>
