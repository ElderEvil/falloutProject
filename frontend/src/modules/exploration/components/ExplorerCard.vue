<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import type { Exploration } from '@/stores/exploration'
import type { Dweller } from '@/stores/dweller'

interface Props {
  exploration: Exploration
  dweller: Dweller | undefined
  selected?: boolean
}

const props = defineProps<Props>()
const router = useRouter()
const route = useRoute()

const emit = defineEmits<{
  select: []
  complete: [explorationId: string]
  recall: [explorationId: string]
}>()

const vaultId = computed(() => route.params.id as string)

const openDetailView = () => {
  router.push(`/vault/${vaultId.value}/exploration/${props.exploration.id}`)
}

const dwellerName = computed(() => {
  if (!props.dweller) return 'Unknown Dweller'
  return `${props.dweller.first_name} ${props.dweller.last_name}`
})

const progressPercentage = computed(() => {
  const now = Date.now()
  let startTimeStr = props.exploration.start_time
  if (!startTimeStr.endsWith('Z')) {
    startTimeStr = startTimeStr.replace(' ', 'T') + 'Z'
  }
  const start = new Date(startTimeStr).getTime()
  const duration = props.exploration.duration * 3600 * 1000
  const elapsed = now - start

  return Math.min(100, (elapsed / duration) * 100)
})

const timeRemaining = computed(() => {
  const progress = progressPercentage.value
  if (progress >= 100) return 'Complete!'

  const totalDuration = props.exploration.duration * 3600
  const remaining = totalDuration * (1 - progress / 100)

  const hours = Math.floor(remaining / 3600)
  const minutes = Math.floor((remaining % 3600) / 60)

  if (hours > 0) {
    return `${hours}h ${minutes}m remaining`
  }
  return `${minutes}m remaining`
})

const statusColor = computed(() => {
  const progress = progressPercentage.value
  if (progress >= 100) return '#FFD700' // Gold for complete
  if (progress >= 75) return 'var(--color-theme-accent)' // Accent for near complete
  return 'var(--color-theme-primary)' // Primary for in progress
})

const recentEvents = computed(() => {
  if (!props.exploration.events || props.exploration.events.length === 0) return []
  return props.exploration.events.slice(-3).reverse()
})
</script>

<template>
  <div class="explorer-card" :class="{ selected }" @click="openDetailView">
    <!-- Header -->
    <div class="card-header">
      <div class="dweller-info">
        <Icon icon="mdi:account" class="dweller-icon" />
        <div>
          <div class="dweller-name">{{ dwellerName }}</div>
          <div class="exploration-duration">{{ exploration.duration }}h expedition</div>
        </div>
      </div>
      <button v-if="selected" class="expand-indicator" title="Event timeline open">
        <Icon icon="mdi:timeline-text" />
      </button>
    </div>

    <!-- Progress Bar -->
    <div class="progress-section">
      <div class="progress-bar-container">
        <div
          class="progress-bar"
          :style="{
            width: `${progressPercentage}%`,
            background: statusColor,
          }"
        ></div>
      </div>
      <div class="progress-info">
        <span class="progress-percentage">{{ Math.round(progressPercentage) }}%</span>
        <span class="progress-time">{{ timeRemaining }}</span>
      </div>
    </div>

    <!-- Stats Grid -->
    <div class="stats-grid">
      <div class="stat-item">
        <Icon icon="mdi:map-marker-distance" class="stat-icon" />
        <div class="stat-content">
          <div class="stat-label">Distance</div>
          <div class="stat-value">{{ exploration.total_distance }} mi</div>
        </div>
      </div>

      <div class="stat-item">
        <Icon icon="mdi:treasure-chest" class="stat-icon" />
        <div class="stat-content">
          <div class="stat-label">Items</div>
          <div class="stat-value">{{ exploration.loot_collected?.length || 0 }}</div>
        </div>
      </div>

      <div class="stat-item">
        <Icon icon="mdi:currency-usd" class="stat-icon" />
        <div class="stat-content">
          <div class="stat-label">Caps</div>
          <div class="stat-value">{{ exploration.total_caps_found }}</div>
        </div>
      </div>

      <!-- Medical Supplies -->
      <div class="stat-item medical">
        <Icon icon="mdi:medical-bag" class="stat-icon stimpaks" />
        <div class="stat-content">
          <div class="stat-label">Stimpaks</div>
          <div class="stat-value">{{ exploration.stimpaks || 0 }}</div>
        </div>
      </div>

      <div class="stat-item medical">
        <Icon icon="mdi:pill" class="stat-icon radaways" />
        <div class="stat-content">
          <div class="stat-label">RadAway</div>
          <div class="stat-value">{{ exploration.radaways || 0 }}</div>
        </div>
      </div>

      <div class="stat-item">
        <Icon icon="mdi:skull" class="stat-icon enemies" />
        <div class="stat-content">
          <div class="stat-label">Enemies</div>
          <div class="stat-value">{{ exploration.enemies_encountered }}</div>
        </div>
      </div>
    </div>

    <!-- Equipment Slots -->
    <div class="equipment-section">
      <div class="equipment-slot">
        <Icon icon="mdi:sword" class="equip-icon" />
        <span class="equip-name">{{ dweller?.weapon?.name || 'Unarmed' }}</span>
      </div>
      <div class="equipment-slot">
        <Icon icon="mdi:tshirt-crew" class="equip-icon" />
        <span class="equip-name">{{ dweller?.outfit?.name || 'Vault Suit' }}</span>
      </div>
    </div>

    <!-- Recent Events Preview -->
    <div v-if="recentEvents.length > 0" class="recent-events">
      <div class="recent-events-header">
        <Icon icon="mdi:history" class="mr-1" />
        Recent Activity
      </div>
      <div class="event-list">
        <div v-for="(event, idx) in recentEvents" :key="idx" class="event-item">
          <Icon
            :icon="
              event.type === 'combat'
                ? 'mdi:sword-cross'
                : event.type === 'loot'
                  ? 'mdi:treasure-chest'
                  : 'mdi:map-marker'
            "
            class="event-icon"
          />
          <span class="event-text">{{ event.description }}</span>
        </div>
      </div>
    </div>

    <!-- Actions -->
    <div class="card-actions">
      <button
        v-if="progressPercentage >= 100"
        @click.stop="emit('complete', exploration.id)"
        class="action-btn complete-btn"
      >
        <Icon icon="mdi:check-circle" />
        Complete
      </button>
      <button @click.stop="emit('recall', exploration.id)" class="action-btn recall-btn">
        <Icon icon="mdi:arrow-u-left-top" />
        Recall Early
      </button>
    </div>
  </div>
</template>

<style scoped>
.explorer-card {
  background: rgba(0, 0, 0, 0.7);
  border: 2px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 8px;
  padding: 1.25rem;
  cursor: pointer;
  transition: all 0.3s ease;
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.explorer-card:hover {
  border-color: var(--color-theme-primary);
  background: rgba(0, 0, 0, 0.85);
  box-shadow: 0 0 20px var(--color-theme-glow);
  transform: translateY(-2px);
}

.explorer-card.selected {
  border-color: var(--color-theme-primary);
  border-width: 3px;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.05);
  box-shadow: 0 0 30px var(--color-theme-glow);
}

.card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.dweller-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.dweller-icon {
  width: 2.5rem;
  height: 2.5rem;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 6px var(--color-theme-glow));
}

.dweller-name {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.exploration-duration {
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
}

.expand-indicator {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
  padding: 0.5rem;
  border-radius: 4px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 1.25rem;
  animation: pulse 2s ease-in-out infinite;
}

@keyframes pulse {
  0%,
  100% {
    opacity: 1;
  }
  50% {
    opacity: 0.6;
  }
}

.progress-section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.progress-bar-container {
  width: 100%;
  height: 12px;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.3);
  border-radius: 6px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  border-radius: 6px;
  transition:
    width 0.5s ease,
    background 0.3s ease;
  box-shadow: 0 0 10px currentColor;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
}

.progress-percentage {
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.progress-time {
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.05);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  border-radius: 4px;
}

.stat-icon {
  width: 1.5rem;
  height: 1.5rem;
  color: var(--color-theme-primary);
  flex-shrink: 0;
}

.stat-icon.enemies {
  color: #ff4444;
}

.stat-icon.stimpaks {
  color: #4caf50;
}

.stat-icon.radaways {
  color: #ffeb3b;
}

.stat-item.medical {
  border-color: rgba(205, 133, 63, 0.4);
}

.equipment-section {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
  margin-top: 0.25rem;
}

.equipment-slot {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.5rem;
  background: rgba(0, 0, 0, 0.4);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.15);
  border-radius: 4px;
}

.equip-icon {
  width: 1.25rem;
  height: 1.25rem;
  color: var(--color-theme-secondary);
}

.equip-name {
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.9);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.stat-content {
  display: flex;
  flex-direction: column;
  gap: 0.125rem;
}

.stat-label {
  font-size: 0.625rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.6);
  text-transform: uppercase;
  letter-spacing: 0.05em;
}

.stat-value {
  font-size: 0.875rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.recent-events {
  padding: 0.75rem;
  background: rgba(0, 0, 0, 0.5);
  border: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  border-radius: 4px;
}

.recent-events-header {
  display: flex;
  align-items: center;
  font-size: 0.75rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.05em;
  margin-bottom: 0.5rem;
}

.event-list {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.event-item {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.8);
}

.event-icon {
  width: 1rem;
  height: 1rem;
  flex-shrink: 0;
  margin-top: 0.125rem;
}

.event-text {
  flex: 1;
  line-height: 1.3;
}

.card-actions {
  display: flex;
  gap: 0.5rem;
  padding-top: 0.5rem;
  border-top: 1px solid rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
}

.action-btn {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 0.5rem;
  padding: 0.75rem;
  border-radius: 4px;
  font-size: 0.875rem;
  font-weight: 700;
  cursor: pointer;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
  border: 2px solid;
}

.complete-btn {
  background: rgba(255, 215, 0, 0.1);
  border-color: #ffd700;
  color: #ffd700;
}

.complete-btn:hover {
  background: rgba(255, 215, 0, 0.2);
  box-shadow: 0 0 15px rgba(255, 215, 0, 0.4);
  transform: scale(1.02);
}

.recall-btn {
  background: rgba(205, 133, 63, 0.1);
  border-color: rgba(205, 133, 63, 0.5);
  color: rgba(205, 133, 63, 1);
}

.recall-btn:hover {
  background: rgba(205, 133, 63, 0.2);
  border-color: rgba(205, 133, 63, 0.8);
  transform: scale(1.02);
}
</style>
