<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { UBadge } from '@/core/components/ui'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { Dweller, DetailedDweller } from '@/modules/dwellers/models/dweller'
import { getProgressPercentage } from '@/modules/exploration/composables/useExplorationProgress'
import ExplorerActions from './ExplorerActions.vue'

interface Props {
  explorations: Exploration[]
  dwellers: Dweller[]
  detailedDwellers: Record<string, DetailedDweller>
  vaultId: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  recall: [explorationId: string]
  complete: [explorationId: string]
}>()

const getDwellerById = (dwellerId: string) => {
  return props.dwellers.find((d) => d.id === dwellerId)
}

const getDetailedDweller = (dwellerId: string) => {
  return props.detailedDwellers[dwellerId] || null
}

const getDwellerWeapon = (dwellerId: string) => {
  const detailed = getDetailedDweller(dwellerId)
  if (detailed?.weapon) return detailed.weapon
  return null
}

const getDwellerOutfit = (dwellerId: string) => {
  const detailed = getDetailedDweller(dwellerId)
  if (detailed?.outfit) return detailed.outfit
  return null
}

// Ready-to-collect first, then highest progress — keeps the actionable cards on top.
const sortedExplorations = computed(() =>
  [...props.explorations].sort((a, b) => getProgressPercentage(b) - getProgressPercentage(a))
)

const isReady = (exploration: Exploration) => getProgressPercentage(exploration) >= 100

// Low HP (<=30%) or heavy radiation (>=50% of max) based on live dweller vitals.
const isAtRisk = (dwellerId: string) => {
  const detailed = getDetailedDweller(dwellerId)
  if (!detailed || !detailed.max_health) return false
  return (
    detailed.health / detailed.max_health <= 0.3 ||
    detailed.radiation / detailed.max_health >= 0.5
  )
}

const riskTitle = (dwellerId: string) => {
  const detailed = getDetailedDweller(dwellerId)
  if (!detailed) return ''
  return `Health ${detailed.health}/${detailed.max_health}, radiation ${detailed.radiation}`
}
</script>

<template>
  <div v-if="explorations.length > 0" class="exploring-dwellers">
    <div class="explorers-header">
      <h4 class="text-sm font-bold text-wasteland">
        <Icon icon="mdi:account-search" class="inline h-5 w-5" />
        Active Explorers ({{ explorations.length }})
      </h4>
      <router-link
        :to="`/vault/${vaultId}/exploration`"
        class="view-all-btn"
        title="View full exploration dashboard"
      >
        <Icon icon="mdi:arrow-right" class="h-4 w-4" />
        View All
      </router-link>
    </div>
    <div class="explorer-list">
      <div
        v-for="exploration in sortedExplorations"
        :key="exploration.id"
        class="explorer-card"
      >
        <div class="explorer-info">
          <div class="flex items-center justify-between gap-2">
            <div class="flex min-w-0 items-center gap-1.5">
              <Icon icon="mdi:account" class="h-4 w-4 shrink-0 text-wasteland" />
              <span class="truncate text-xs font-bold text-wasteland"
                >{{ getDwellerById(exploration.dweller_id)?.first_name }}
                {{ getDwellerById(exploration.dweller_id)?.last_name }}</span
              >
              <span v-if="isAtRisk(exploration.dweller_id)" :title="riskTitle(exploration.dweller_id)" aria-label="Dweller at risk">
                <UBadge size="sm" variant="warning">
                  <Icon icon="mdi:heart-pulse" class="h-3 w-3" />
                  AT RISK
                </UBadge>
              </span>
            </div>
            <span class="flex shrink-0 items-center gap-1">
              <span v-if="isReady(exploration)" title="Expedition finished — ready to collect">
                <UBadge size="sm" variant="primary">READY</UBadge>
              </span>
              <span class="whitespace-nowrap rounded-full border border-[rgba(205,133,63,0.35)] bg-[rgba(205,133,63,0.1)] px-1.5 py-0.5 font-mono text-[0.65rem] font-bold text-wasteland"
                >{{ Math.round(getProgressPercentage(exploration)) }}%</span
              >
            </span>
          </div>
          <UProgressBar
            :model-value="getProgressPercentage(exploration)"
            :height="6"
            :glow="false"
            color="linear-gradient(90deg, rgb(205 133 63 / 0.6), rgb(205 133 63))"
            :ariaLabel="`Exploration progress for ${getDwellerById(exploration.dweller_id)?.first_name ?? 'dweller'}`"
          />
          <div class="explorer-stats">
            <div class="stat-item">
              <Icon icon="mdi:map-marker-distance" class="h-3.5 w-3.5" />
              <span>{{ exploration.total_distance || 0 }}mi</span>
            </div>
            <span class="text-[rgba(205,133,63,0.4)] text-[0.65rem]">•</span>
            <div class="stat-item">
              <Icon icon="mdi:treasure-chest" class="h-3.5 w-3.5" />
              <span>{{ exploration.loot_collected?.length || 0 }}</span>
            </div>
            <span class="text-[rgba(205,133,63,0.4)] text-[0.65rem]">•</span>
            <div class="stat-item">
              <Icon icon="mdi:currency-usd" class="h-3.5 w-3.5" />
              <span>{{ exploration.total_caps_found || 0 }}</span>
            </div>
            <span class="text-[rgba(205,133,63,0.4)] text-[0.65rem]">•</span>
            <div class="stat-item" :title="`${exploration.enemies_encountered || 0} enemies encountered`">
              <Icon icon="mdi:skull" class="h-3.5 w-3.5" />
              <span>{{ exploration.enemies_encountered || 0 }}</span>
            </div>
          </div>
          <div
            v-if="
              getDwellerWeapon(exploration.dweller_id) || getDwellerOutfit(exploration.dweller_id)
            "
            class="flex min-w-0 flex-col gap-0.5 text-[0.7rem] leading-tight"
          >
            <span
              v-if="getDwellerWeapon(exploration.dweller_id)"
              class="stat-item min-w-0 text-amber-400"
              :title="getDwellerWeapon(exploration.dweller_id)?.name"
            >
              <Icon icon="mdi:sword" class="h-3 w-3 shrink-0" />
              <span class="min-w-0 flex-1 truncate">{{
                getDwellerWeapon(exploration.dweller_id)?.name
              }}</span>
            </span>
            <span
              v-if="getDwellerOutfit(exploration.dweller_id)"
              class="stat-item min-w-0 text-blue-400"
              :title="getDwellerOutfit(exploration.dweller_id)?.name"
            >
              <Icon icon="mdi:tshirt-crew" class="h-3 w-3 shrink-0" />
              <span class="min-w-0 flex-1 truncate">{{
                getDwellerOutfit(exploration.dweller_id)?.name
              }}</span>
            </span>
          </div>
        </div>
        <ExplorerActions
          compact
          class="explorer-actions"
          :can-complete="getProgressPercentage(exploration) >= 100"
          @complete="emit('complete', exploration.id)"
          @recall="emit('recall', exploration.id)"
        />
      </div>
    </div>
  </div>
  <div v-else class="exploring-dwellers">
    <p class="text-xs text-gray-500">
      <Icon icon="mdi:information" class="inline h-4 w-4" />
      No active explorers. Drag dwellers here to send them to the wasteland!
    </p>
  </div>
</template>

<style scoped>
.text-wasteland {
  color: rgba(205, 133, 63, 1);
}

.exploring-dwellers {
  margin-top: 1rem;
  padding-top: 1rem;
  border-top: 1px solid rgba(205, 133, 63, 0.3);
}

.explorers-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.5rem;
}

.view-all-btn {
  display: flex;
  align-items: center;
  gap: 0.25rem;
  padding: 0.375rem 0.75rem;
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.1);
  border: 1px solid var(--color-theme-primary);
  border-radius: 4px;
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  font-weight: 700;
  text-decoration: none;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.view-all-btn:hover {
  background: rgba(var(--color-theme-primary-rgb, 0, 255, 0), 0.2);
  box-shadow: 0 0 10px var(--color-theme-glow);
  transform: translateX(2px);
}

.explorer-list {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 0.75rem;
}

.explorer-card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(205, 133, 63, 0.3);
  border-radius: 6px;
  padding: 0.5rem 0.625rem;
  display: flex;
  flex-direction: column;
  gap: 0.375rem;
  transition: all 0.2s ease;
}

.explorer-card:hover {
  border-color: rgba(205, 133, 63, 0.6);
  background: rgba(0, 0, 0, 0.4);
}

.explorer-info {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.explorer-stats {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 0.35rem;
  font-size: 0.72rem;
  color: rgba(205, 133, 63, 0.8);
}

.stat-item {
  display: inline-flex;
  align-items: center;
  gap: 0.15rem;
}

.explorer-actions {
  display: flex;
  flex-direction: row;
  gap: 0.375rem;
  margin-top: auto;
  padding-top: 0.125rem;
}

.explorer-actions :deep(button) {
  flex: 1;
  font-size: 0.7rem;
  padding: 0.25rem 0.5rem;
}

@media (max-width: 639px) {
  .explorer-list {
    grid-template-columns: 1fr;
  }
}
</style>
