<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { Dweller, DetailedDweller } from '@/modules/dwellers/types'

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

const getProgressPercentage = (exploration: Exploration) => {
  const now = Date.now()
  let startTimeStr = exploration.start_time
  if (!startTimeStr.endsWith('Z')) {
    startTimeStr = startTimeStr.replace(' ', 'T') + 'Z'
  }
  const start = new Date(startTimeStr).getTime()
  const duration = exploration.duration * 3600 * 1000
  const elapsed = now - start
  return Math.min(100, (elapsed / duration) * 100)
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
      <div v-for="exploration in explorations" :key="exploration.id" class="explorer-card">
        <div class="explorer-info">
          <div class="flex items-center gap-2 mb-1">
            <Icon icon="mdi:account" class="h-5 w-5 text-wasteland" />
            <span class="font-bold text-sm"
              >{{ getDwellerById(exploration.dweller_id)?.first_name }}
              {{ getDwellerById(exploration.dweller_id)?.last_name }}</span
            >
          </div>
          <div class="explorer-stats">
            <div class="stat-item">
              <Icon icon="mdi:map-marker-distance" class="h-4 w-4" />
              <span>{{ exploration.total_distance || 0 }} miles</span>
            </div>
            <div class="stat-item">
              <Icon icon="mdi:treasure-chest" class="h-4 w-4" />
              <span>{{ exploration.loot_collected?.length || 0 }} items</span>
            </div>
            <div class="stat-item">
              <Icon icon="mdi:currency-usd" class="h-4 w-4" />
              <span>{{ exploration.total_caps_found || 0 }} caps</span>
            </div>
          </div>
          <!-- Equipped Items -->
          <div
            v-if="
              getDwellerWeapon(exploration.dweller_id) || getDwellerOutfit(exploration.dweller_id)
            "
            class="equipped-items mt-2"
          >
            <div v-if="getDwellerWeapon(exploration.dweller_id)" class="stat-item text-amber-400">
              <Icon icon="mdi:sword" class="h-4 w-4" />
              <span class="text-xs">{{ getDwellerWeapon(exploration.dweller_id)?.name }}</span>
            </div>
            <div v-if="getDwellerOutfit(exploration.dweller_id)" class="stat-item text-blue-400">
              <Icon icon="mdi:tshirt-crew" class="h-4 w-4" />
              <span class="text-xs">{{ getDwellerOutfit(exploration.dweller_id)?.name }}</span>
            </div>
          </div>
          <!-- Progress Bar -->
          <div class="progress-bar-container">
            <div
              class="progress-bar"
              :style="{
                width: `${getProgressPercentage(exploration)}%`,
              }"
            ></div>
          </div>
          <div class="text-xs text-wasteland-dim mt-1">
            {{ Math.round(getProgressPercentage(exploration)) }}% complete
          </div>
        </div>
        <div class="explorer-actions">
          <button
            v-if="getProgressPercentage(exploration) >= 100"
            @click="emit('complete', exploration.id)"
            class="complete-button"
            title="Complete Exploration"
          >
            <Icon icon="mdi:check-circle" class="h-5 w-5" />
            Complete
          </button>
          <button
            @click="emit('recall', exploration.id)"
            class="recall-button"
            title="Recall Dweller"
          >
            <Icon icon="mdi:arrow-u-left-top" class="h-5 w-5" />
            Recall
          </button>
        </div>
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

.text-wasteland-dim {
  color: rgba(205, 133, 63, 0.7);
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
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.explorer-card {
  background: rgba(0, 0, 0, 0.3);
  border: 1px solid rgba(205, 133, 63, 0.3);
  border-radius: 6px;
  padding: 0.75rem;
  display: flex;
  justify-content: space-between;
  align-items: center;
  transition: all 0.2s ease;
}

.explorer-card:hover {
  border-color: rgba(205, 133, 63, 0.6);
  background: rgba(0, 0, 0, 0.4);
}

.explorer-info {
  flex: 1;
}

.explorer-stats {
  display: flex;
  gap: 1rem;
  margin-top: 0.5rem;
  font-size: 0.75rem;
  color: rgba(205, 133, 63, 0.8);
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 0.25rem;
}

.progress-bar-container {
  width: 100%;
  height: 8px;
  background: rgba(0, 0, 0, 0.5);
  border-radius: 4px;
  overflow: hidden;
  margin-top: 0.5rem;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, rgba(205, 133, 63, 0.6), rgba(205, 133, 63, 1));
  border-radius: 4px;
  transition: width 0.3s ease;
}

.explorer-actions {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.complete-button {
  background: rgba(0, 180, 0, 0.2);
  border: 2px solid var(--color-theme-primary);
  color: var(--color-theme-primary);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
  font-weight: bold;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.complete-button:hover {
  background: rgba(0, 220, 0, 0.3);
  border-color: var(--color-theme-primary);
  transform: scale(1.05);
  box-shadow: 0 0 10px var(--color-theme-glow);
}

.recall-button {
  background: rgba(205, 133, 63, 0.2);
  border: 1px solid rgba(205, 133, 63, 0.5);
  color: rgba(205, 133, 63, 1);
  padding: 0.5rem 0.75rem;
  border-radius: 4px;
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 0.25rem;
  font-size: 0.875rem;
  font-weight: bold;
  transition: all 0.2s ease;
  font-family: 'Courier New', monospace;
}

.recall-button:hover {
  background: rgba(205, 133, 63, 0.3);
  border-color: rgba(205, 133, 63, 0.8);
  transform: scale(1.05);
}
</style>
