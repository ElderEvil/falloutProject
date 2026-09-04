<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { Dweller } from '@/modules/dwellers/models/dweller'
import { useExplorationProgress } from '@/modules/exploration/composables/useExplorationProgress'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerIdentitySignal from '@/modules/dwellers/components/DwellerIdentitySignal.vue'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import { UCard, UProgressBar } from '@/core/components/ui'
import ExplorerActions from './ExplorerActions.vue'

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

const openDetailView = () =>
  router.push(`/vault/${route.params.id}/exploration/${props.exploration.id}`)

const dwellerName = computed(() =>
  props.dweller ? `${props.dweller.first_name} ${props.dweller.last_name}` : 'Unknown Dweller'
)

const { progress: progressPercentage, timeRemaining } = useExplorationProgress(() => props.exploration)

const recentEvents = computed(() => props.exploration.events?.slice(-3).reverse() ?? [])
</script>

<template>
  <UCard padding="md" surface="raised" class="explorer-card" :class="{ selected }" @click="openDetailView">
    <!-- Header -->
    <div class="card-header">
      <div class="dweller-info">
        <DwellerPortrait
          :image-url="dweller?.image_url"
          :thumbnail-url="dweller?.thumbnail_url"
          prefer-thumbnail
          :alt="`${dwellerName} portrait`"
          image-class="dweller-icon dweller-portrait rounded-full border border-theme-primary object-cover"
          fallback-class="dweller-icon"
        />
        <div>
          <div class="dweller-name">{{ dwellerName }}</div>
          <div class="exploration-duration">{{ exploration.duration }}h expedition</div>
          <DwellerIdentitySignal :visual-attributes="dweller?.visual_attributes" compact class="mt-1" />
        </div>
      </div>
      <button v-if="selected" class="expand-indicator" title="Event timeline open">
        <Icon icon="mdi:timeline-text" />
      </button>
    </div>

    <!-- Progress Bar -->
    <div class="progress-section">
      <div class="progress-info">
        <span>Mission progress</span>
        <span class="progress-percentage">{{ Math.round(progressPercentage) }}%</span>
      </div>
      <UProgressBar :model-value="progressPercentage" :height="8" :glow="false" />
      <span class="progress-time">{{ timeRemaining }}</span>
    </div>

    <!-- Stats Grid -->
    <div class="stats-grid">
      <TerminalMetric icon="mdi:map-marker-distance" label="Distance" :value="`${exploration.total_distance} mi`" />
      <TerminalMetric icon="mdi:treasure-chest" label="Items" :value="exploration.loot_collected?.length || 0" />
      <TerminalMetric icon="mdi:currency-usd" label="Caps" :value="exploration.total_caps_found" tone="caps" />
      <TerminalMetric icon="mdi:medical-bag" label="Stimpaks" :value="exploration.stimpaks || 0" />
      <TerminalMetric icon="mdi:pill" label="RadAway" :value="exploration.radaways || 0" tone="caps" />
      <TerminalMetric icon="mdi:skull" label="Enemies" :value="exploration.enemies_encountered" tone="danger" />
    </div>

    <!-- Equipment Slots -->
    <div class="equipment-section">
      <div class="equipment-slot min-w-0">
        <Icon icon="mdi:sword" class="equip-icon" />
        <span class="equip-name min-w-0">{{ dweller?.weapon?.name || 'Unarmed' }}</span>
      </div>
      <div class="equipment-slot min-w-0">
        <Icon icon="mdi:tshirt-crew" class="equip-icon" />
        <span class="equip-name min-w-0">{{ dweller?.outfit?.name || 'Vault Suit' }}</span>
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
    <ExplorerActions
      compact
      :can-complete="progressPercentage >= 100"
      @complete="emit('complete', exploration.id)"
      @recall="emit('recall', exploration.id)"
    />
  </UCard>
</template>

<style scoped>
.explorer-card {
  cursor: pointer;
  transition: all 0.3s ease;
  display: grid;
  gap: 14px;
}

.explorer-card:hover {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 16px var(--color-theme-glow);
  transform: translateY(-2px);
}

.explorer-card.selected {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 16px var(--color-theme-glow);
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
  display: grid;
  gap: 6px;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 0.75rem;
  color: var(--color-theme-primary);
  letter-spacing: 0.06em;
  opacity: 0.8;
  text-transform: uppercase;
}

.progress-percentage {
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.progress-time {
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
  font-size: 0.75rem;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 0.75rem;
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
  background: rgb(from var(--color-surface-sunken) r g b / 0.8);
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


.recent-events {
  padding: 0.75rem;
  background: var(--color-surface-sunken);
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

</style>
