<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoute } from 'vue-router'
import type { Room } from '../models/room'

const props = defineProps<{
  room: Room
}>()

const emit = defineEmits<{
  (e: 'select', room: Room): void
}>()

const route = useRoute()
const vaultStore = useVaultStore()

const vaultId = computed(() => route.params.id as string)
const currentVault = computed(() => {
  return vaultId.value ? vaultStore.loadedVaults[vaultId.value] : null
})

const roomCost = computed(() => props.room.base_cost)
const canAfford = computed(() => {
  const caps = currentVault.value?.bottle_caps ?? 0
  return caps >= roomCost.value
})

const currentPopulation = computed(() => currentVault.value?.dweller_count ?? 0)

const isLocked = computed(() => {
  const popRequired = props.room.population_required
  if (!popRequired) return false
  return currentPopulation.value < popRequired
})

const populationProgress = computed(() => {
  const popRequired = props.room.population_required
  if (!popRequired) return 100
  return Math.min(100, Math.round((currentPopulation.value / popRequired) * 100))
})

const getCategoryIcon = (category: string) => {
  const icons: Record<string, string> = {
    'Production': 'mdi:lightning-bolt',
    'Capacity': 'mdi:home',
    'Training': 'mdi:school',
    'Misc.': 'mdi:hammer-wrench',
    'Quests': 'mdi:book-open',
    'Crafting': 'mdi:hammer',
    'Theme': 'mdi:palette'
  }
  return icons[category] || 'mdi:cube'
}
</script>

<template>
  <li
    @click="!isLocked && emit('select', room)"
    class="room-menu-item"
    :class="{
      'locked': isLocked,
      'affordable': !isLocked && canAfford,
      'expensive': !isLocked && !canAfford
    }"
  >
    <div class="room-item-content">
      <div class="room-header">
        <div class="room-name">{{ room.name }}</div>
        <Icon v-if="isLocked" icon="mdi:lock" class="lock-icon" />
      </div>

      <div class="room-icon">
        <Icon
          :icon="getCategoryIcon(room.category)"
          class="category-icon"
        />
      </div>

      <div class="room-details">
        <div class="room-category">
          <Icon :icon="getCategoryIcon(room.category)" class="w-4 h-4" />
          <span>{{ room.category }}</span>
        </div>

        <div class="room-cost">
          <Icon icon="mdi:currency-usd" class="w-4 h-4" />
          <span>{{ roomCost }}</span>
        </div>

        <div v-if="room.population_required" class="room-population-section">
          <div class="room-population">
            <Icon icon="mdi:account-group" class="w-4 h-4" />
            <span>{{ currentPopulation }}/{{ room.population_required }}</span>
          </div>
          <div v-if="isLocked" class="population-progress">
            <div class="progress-bar" :style="{ width: `${populationProgress}%` }"></div>
          </div>
        </div>

        <div class="room-size">
          <Icon icon="mdi:resize" class="w-4 h-4" />
          <span>{{ room.size_min }}-{{ room.size_max }} cells</span>
        </div>
      </div>
    </div>
  </li>
</template>

<style scoped>
.room-menu-item {
  padding: 1rem;
  background: rgba(20, 20, 20, 0.95);
  border: 2px solid #444;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-family: 'Courier New', monospace;
  position: relative;
  overflow: hidden;
}

.room-menu-item::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(135deg, transparent 0%, rgba(0, 255, 0, 0.05) 100%);
  opacity: 0;
  transition: opacity 0.25s ease;
}

.room-menu-item.affordable {
  border-color: var(--color-theme-primary);
  background: rgba(25, 25, 25, 0.95);
}

.room-menu-item.affordable::before {
  opacity: 1;
}

.room-menu-item.affordable:hover {
  border-color: var(--color-theme-primary);
  transform: translateY(-3px);
  box-shadow: 0 6px 16px rgba(0, 255, 0, 0.2), 0 0 12px var(--color-theme-glow);
  background: rgba(30, 30, 30, 0.95);
}

.room-menu-item.expensive {
  border-color: #ff9900;
  background: rgba(30, 25, 20, 0.95);
}

.room-menu-item.expensive:hover {
  border-color: #ffaa33;
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 153, 0, 0.2);
}

.room-menu-item.locked {
  border-color: #555;
  opacity: 0.5;
  cursor: not-allowed;
  background: rgba(15, 15, 15, 0.95);
}

.room-item-content {
  display: flex;
  flex-direction: column;
  gap: 0.875rem;
  position: relative;
  z-index: 1;
}

.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding-bottom: 0.5rem;
  border-bottom: 1px solid rgba(0, 255, 0, 0.2);
}

.room-name {
  color: var(--color-theme-primary);
  font-size: 0.95rem;
  font-weight: bold;
  letter-spacing: 0.025em;
  text-shadow: 0 0 4px var(--color-theme-glow);
}

.lock-icon {
  width: 18px;
  height: 18px;
  color: #ff4444;
}

.room-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 64px;
  margin: 0.25rem 0;
}

.category-icon {
  width: 56px;
  height: 56px;
  color: var(--color-theme-primary);
  filter: drop-shadow(0 0 6px var(--color-theme-glow));
  transition: transform 0.25s ease;
}

.room-menu-item:hover .category-icon {
  transform: scale(1.1);
}

.room-details {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  font-size: 0.8rem;
}

.room-category,
.room-cost,
.room-population,
.room-size {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #999;
}

.room-cost {
  color: #fbbf24;
  font-weight: bold;
}

.room-population-section {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.room-population {
  color: #88ccff;
}

.population-progress {
  height: 4px;
  background: rgba(136, 204, 255, 0.2);
  border-radius: 2px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background: linear-gradient(90deg, #88ccff 0%, #44aaff 100%);
  border-radius: 2px;
  transition: width 0.3s ease;
  box-shadow: 0 0 4px rgba(136, 204, 255, 0.5);
}
</style>
