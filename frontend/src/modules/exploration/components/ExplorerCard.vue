<script setup lang="ts">
import { computed } from 'vue'
import { RouterLink, useRoute, useRouter } from 'vue-router'
import { Icon } from '@iconify/vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import {
  getDwellerDisplayName,
  type Dweller,
  type DwellerShort,
} from '@/modules/dwellers/models/dweller'
import { useExplorationProgress } from '@/modules/exploration/composables/useExplorationProgress'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import DwellerIdentitySignal from '@/modules/dwellers/components/DwellerIdentitySignal.vue'
import DwellerAgeBadge from '@/modules/dwellers/components/DwellerAgeBadge.vue'
import DwellerGenderBadge from '@/modules/dwellers/components/DwellerGenderBadge.vue'
import DwellerRarityBadge from '@/modules/dwellers/components/DwellerRarityBadge.vue'
import TerminalMetric from '@/core/components/common/TerminalMetric.vue'
import { Card } from '@/core/components/ui/card'
import { Progress } from '@/core/components/ui/progress'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import { getItemIcon } from '@/core/models/items'
import ExplorationStatusBadges from './ExplorationStatusBadges.vue'
import ExplorerActions from './ExplorerActions.vue'
import PartyRoster from './PartyRoster.vue'

interface Props {
  exploration: Exploration
  dweller: Dweller | undefined
  partyMembers?: DwellerShort[]
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

const dwellerName = computed(() => getDwellerDisplayName(props.dweller) || 'Unknown Dweller')

const {
  progress: progressPercentage,
  timeRemaining,
  isReturning,
  isReady,
  canRecall,
} = useExplorationProgress(() => props.exploration)

const recentEvents = computed(() => props.exploration.events?.slice(-3).reverse() ?? [])

const isParty = computed(
  () => !!props.exploration.target_location_id || (props.partyMembers?.length ?? 0) > 1
)
const party = computed<(DwellerShort | Dweller)[]>(() => {
  const members = props.partyMembers ?? []
  const anchor =
    members.find((member) => member.id === props.exploration.dweller_id) ?? props.dweller
  return anchor
    ? [
        { ...anchor, id: props.exploration.dweller_id },
        ...members.filter((member) => member.id !== props.exploration.dweller_id),
      ]
    : members
})
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
      <div v-if="isParty" class="grid min-w-0 gap-2">
        <div
          class="flex items-center gap-2 text-xs font-bold uppercase tracking-wide text-theme-primary"
        >
          <Icon icon="mdi:account-group" class="size-4 text-theme-accent" />
          Expedition party
        </div>
        <RouterLink
          class="expedition-heading text-lg font-bold text-theme-primary"
          :to="`/vault/${route.params.id}/exploration/${exploration.id}`"
          @click.stop
        >
          {{ exploration.duration }}h expedition
          <Icon icon="mdi:chevron-right" :ariaHidden="true" />
        </RouterLink>
      </div>
      <div v-else class="dweller-info">
        <RouterLink
          class="dweller-portrait-link"
          :to="`/vault/${route.params.id}/dwellers/${exploration.dweller_id}`"
          :aria-label="`Open ${dwellerName}'s dweller page`"
          @click.stop
        >
          <DwellerPortrait
            :image-url="dweller?.image_url"
            :thumbnail-url="dweller?.thumbnail_url"
            prefer-thumbnail
            :alt="`${dwellerName} portrait`"
            image-class="dweller-portrait h-12 w-12 rounded-md object-cover"
            fallback-class="h-12 w-12 text-theme-primary drop-shadow-[0_0_6px_var(--color-theme-glow)]"
          />
        </RouterLink>
        <div class="dweller-meta">
          <TooltipProvider :delay-duration="200">
            <Tooltip>
              <TooltipTrigger as-child>
                <RouterLink
                  class="dweller-name-link"
                  :to="`/vault/${route.params.id}/dwellers/${exploration.dweller_id}`"
                  :aria-label="`Open ${dwellerName}'s dweller page`"
                  @click.stop
                >
                  <span class="dweller-name">{{ dwellerName }}</span>
                  <Icon
                    icon="mdi:account-arrow-right"
                    class="dweller-link-icon"
                    :ariaHidden="true"
                  />
                </RouterLink>
              </TooltipTrigger>
              <TooltipContent>Open dweller page</TooltipContent>
            </Tooltip>
          </TooltipProvider>
          <RouterLink
            class="expedition-link"
            :to="`/vault/${route.params.id}/exploration/${exploration.id}`"
            @click.stop
          >
            {{ exploration.duration }}h expedition
            <Icon icon="mdi:chevron-right" :ariaHidden="true" />
          </RouterLink>
          <div class="flex flex-wrap items-center gap-1.5">
            <DwellerIdentitySignal :visual-attributes="dweller?.visual_attributes" compact />
            <DwellerAgeBadge :age-group="dweller?.age_group" size="sm" />
            <DwellerGenderBadge :gender="dweller?.gender" size="sm" />
            <DwellerRarityBadge :rarity="dweller?.rarity" size="sm" />
          </div>
        </div>
      </div>
      <div class="card-status">
        <ExplorationStatusBadges :exploration="exploration" :dweller="dweller ?? null" />
        <TooltipProvider v-if="selected" :delay-duration="200">
          <Tooltip>
            <TooltipTrigger as-child>
              <button class="expand-indicator" aria-label="Event timeline open">
                <Icon icon="mdi:timeline-text" />
              </button>
            </TooltipTrigger>
            <TooltipContent>Event timeline open</TooltipContent>
          </Tooltip>
        </TooltipProvider>
      </div>
    </div>

    <!-- Progress Bar -->
    <div class="progress-section">
      <div class="progress-info">
        <span>{{ isReturning ? 'Return progress' : 'Mission progress' }}</span>
        <span class="progress-percentage">{{ Math.round(progressPercentage) }}%</span>
      </div>
      <Progress :model-value="progressPercentage" class="h-2" />
      <span class="progress-time">{{ timeRemaining }}</span>
    </div>

    <!-- Stats Grid -->
    <div class="stats-grid">
      <TerminalMetric
        v-if="!isParty"
        icon="mdi:map-marker-distance"
        label="Distance"
        :value="`${exploration.total_distance} mi`"
      />
      <TerminalMetric
        icon="mdi:treasure-chest"
        label="Items"
        :value="exploration.loot_collected?.length || 0"
      />
      <TerminalMetric icon="mdi:coins" label="Caps" :value="exploration.total_caps_found" />
      <TerminalMetric
        v-if="!isParty"
        icon="mdi:medical-bag"
        label="Stimpaks"
        :value="exploration.stimpaks || 0"
      />
      <TerminalMetric
        v-if="!isParty"
        icon="mdi:pill"
        label="RadAway"
        :value="exploration.radaways || 0"
      />
      <TerminalMetric
        v-if="!isParty"
        icon="mdi:skull"
        label="Enemies"
        :value="exploration.enemies_encountered"
      />
    </div>

    <!-- Equipment Slots -->
    <div v-if="!isParty" class="equipment-section">
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

    <PartyRoster v-if="isParty" :members="party" />

    <!-- Recent Events Preview -->
    <div v-if="!isParty && recentEvents.length > 0" class="recent-events">
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

    <a
      class="view-on-map inline-flex w-fit items-center gap-1 text-sm text-theme-primary underline-offset-4 hover:underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-theme-primary"
      :href="`/vault/${route.params.id}/map${exploration.target_location_id ? `?place=${encodeURIComponent(exploration.target_location_id)}` : ''}`"
      @click.stop
    >
      <Icon icon="mdi:map-marker-radius" :ariaHidden="true" />
      View on Map
    </a>

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
  min-width: 0;
}

.dweller-meta {
  display: grid;
  gap: 0.25rem;
  min-width: 0;
}

.dweller-portrait-link,
.dweller-name-link,
.expedition-link,
.expedition-heading {
  background: none;
  border: none;
  padding: 0;
  cursor: pointer;
}

.dweller-portrait-link {
  display: block;
  border-radius: 4px;
}

.dweller-name-link {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
  width: fit-content;
  text-align: left;
  text-decoration: none;
}

.dweller-portrait-link:focus-visible,
.dweller-name-link:focus-visible,
.expedition-link:focus-visible,
.expedition-heading:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.dweller-name-link:hover .dweller-name,
.dweller-name-link:focus-visible .dweller-name {
  text-decoration: underline;
  text-underline-offset: 4px;
}

.dweller-link-icon {
  opacity: 0.5;
}

.dweller-name-link:hover .dweller-link-icon,
.dweller-name-link:focus-visible .dweller-link-icon {
  opacity: 1;
}

.dweller-name {
  font-size: 1.125rem;
  font-weight: 700;
  color: var(--color-theme-primary);
  text-shadow: 0 0 6px var(--color-theme-glow);
}

.expedition-link,
.expedition-heading {
  display: inline-flex;
  align-items: center;
  gap: 0.125rem;
  width: fit-content;
  text-align: left;
}

.expedition-heading {
  text-decoration: none;
}

.expedition-link {
  font-size: 0.75rem;
  color: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.7);
  text-decoration: underline;
  text-underline-offset: 3px;
}

.expedition-link:hover,
.expedition-heading:hover {
  text-decoration: underline;
  text-underline-offset: 3px;
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
