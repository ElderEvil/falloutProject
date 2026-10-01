<script setup lang="ts">
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Icon } from '@iconify/vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import { getDwellerDisplayName, type Dweller } from '@/modules/dwellers/models/dweller'
import { useExplorationProgress } from '@/modules/exploration/composables/useExplorationProgress'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerIdentitySignal from '@/modules/dwellers/components/DwellerIdentitySignal.vue'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerGenderBadge from '@/modules/dwellers/components/DwellerGenderBadge.vue'
import DwellerRarityBadge from '@/modules/dwellers/components/DwellerRarityBadge.vue'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import { Card } from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from '@/core/components/ui/tooltip'
import { getItemIcon } from '@/core/models/items'
import ExplorationStatusBadges from './ExplorationStatusBadges.vue'
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

const openDwellerDetail = () =>
  router.push(`/vault/${route.params.id}/dwellers/${props.exploration.dweller_id}`)

const dwellerName = computed(() => getDwellerDisplayName(props.dweller) || 'Unknown Dweller')

const {
  progress: progressPercentage,
  timeRemaining,
  isReturning,
  isReady,
  canRecall,
} = useExplorationProgress(() => props.exploration)

const recentEvents = computed(() => props.exploration.events?.slice(-3).reverse() ?? [])
</script>

<template>
  <!-- @vue-ignore -->
  <Card
    class="explorer-card gap-0 rounded-lg border-2 border-theme-primary/20 bg-surface-raised p-6 ring-0"
    :class="{ selected }"
    @click="openDetailView"
  >
    <!-- Header: identity left, status top-right -->
    <div class="card-header">
      <TooltipProvider :delay-duration="200">
        <Tooltip>
          <TooltipTrigger as-child>
            <button type="button" class="dweller-info dweller-link" @click.stop="openDwellerDetail">
              <DwellerPortrait
                :image-url="dweller?.image_url"
                :thumbnail-url="dweller?.thumbnail_url"
                prefer-thumbnail
                :alt="`${dwellerName} portrait`"
                image-class="dweller-portrait h-12 w-12 rounded-full border border-theme-primary object-cover"
                fallback-class="h-12 w-12 text-theme-primary drop-shadow-[0_0_6px_var(--color-theme-glow)]"
              />
              <div>
                <div class="dweller-name">{{ dwellerName }}</div>
                <div class="exploration-duration">{{ exploration.duration }}h expedition</div>
                <div class="mt-1 flex flex-wrap items-center gap-1.5">
                  <DwellerIdentitySignal :visual-attributes="dweller?.visual_attributes" compact />
                  <DwellerAgeBadge :age-group="dweller?.age_group" size="sm" />
                  <DwellerGenderBadge :gender="dweller?.gender" size="sm" />
                  <DwellerRarityBadge :rarity="dweller?.rarity" size="sm" />
                </div>
              </div>
            </button>
          </TooltipTrigger>
          <TooltipContent>Open dweller detail page</TooltipContent>
        </Tooltip>
      </TooltipProvider>
      <div class="card-status">
        <ExplorationStatusBadges :exploration="exploration" :dweller="dweller ?? null" />
        <TooltipProvider v-if="selected" :delay-duration="200">
          <Tooltip>
            <TooltipTrigger as-child>
              <button class="expand-indicator" aria-label="Event timeline open"><Icon icon="mdi:timeline-text" /></button>
            </TooltipTrigger>
            <TooltipContent>Event timeline open</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="progress-section">
      <div class="progress-info">
        <span>Mission progress</span>
        <span class="progress-percentage">{{ Math.round(progressPercentage) }}%</span>
      </div>
      <Progress :model-value="progressPercentage" class="h-2" />
      <span class="progress-time">{{ timeRemaining }}</span>
    </div>

    <!-- Stats Grid -->
    <div class="stats-grid">
      <TerminalMetric icon="mdi:map-marker-distance" label="Distance" :value="`${exploration.total_distance} mi`" />
      <TerminalMetric icon="mdi:treasure-chest" label="Items" :value="exploration.loot_collected?.length || 0" />
      <TerminalMetric icon="mdi:currency-usd" label="Caps" :value="exploration.total_caps_found" />
      <TerminalMetric icon="mdi:medical-bag" label="Stimpaks" :value="exploration.stimpaks || 0" />
      <TerminalMetric icon="mdi:pill" label="RadAway" :value="exploration.radaways || 0" />
      <TerminalMetric icon="mdi:skull" label="Enemies" :value="exploration.enemies_encountered" />
    </div>

    <!-- Equipment Slots -->
    <div class="equipment-section">
      <div class="equipment-slot min-w-0">
        <Icon :icon="getItemIcon('weapon', dweller?.weapon ?? {})" class="equip-icon" />
        <span class="equip-name min-w-0">{{ dweller?.weapon?.name || 'Unarmed' }}</span>
      </div>
      <div class="equipment-slot min-w-0">
        <Icon :icon="getItemIcon('outfit', dweller?.outfit ?? {})" class="equip-icon" />
        <span class="equip-name min-w-0">{{ dweller?.outfit?.name || 'Vault Suit' }}</span>
      </div>
      <div class="equipment-slot min-w-0">
        <Icon :icon="getItemIcon('pet', dweller?.pet ?? {})" class="equip-icon" />
        <span class="equip-name min-w-0">{{ dweller?.pet?.name || 'No Pet' }}</span>
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
      :can-complete="isReady"
      :can-recall="canRecall"
      :is-returning="isReturning"
      @complete="emit('complete', exploration.id)"
      @recall="emit('recall', exploration.id)"
    />
  </Card>
</template>

<style scoped>
.explorer-card {
  cursor: pointer;
  transition: all 0.3s ease;
  display: grid;
  gap: 10px;
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
  align-items: flex-start;
  gap: 0.75rem;
}

.card-status {
  display: flex;
  align-items: flex-start;
  gap: 0.5rem;
  flex-shrink: 0;
}

.dweller-info {
  display: flex;
  align-items: center;
  gap: 0.75rem;
}

.dweller-link {
  background: none;
  border: none;
  padding: 0;
  font: inherit;
  color: inherit;
  text-align: left;
  cursor: pointer;
  text-decoration: none;
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
  gap: 0.375rem;
}

.equipment-section {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.375rem;
  margin-top: 0.125rem;
}

.equipment-slot {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  padding: 0.375rem;
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
