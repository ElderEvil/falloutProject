<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoute } from 'vue-router'
import { getRoomImageUrl } from '@/core/utils/image'
import UProgressBar from '@/core/components/ui/UProgressBar.vue'
import type { RoomTemplate } from '../models/room'

const props = defineProps<{
  room: RoomTemplate
}>()

const emit = defineEmits<{
  (e: 'select', room: RoomTemplate): void
}>()

const route = useRoute()
const vaultStore = useVaultStore()
const showRoomImage = ref(true)

const categoryIcons: Record<string, string> = {
  production: 'mdi:lightning-bolt',
  capacity: 'mdi:home',
  training: 'mdi:school',
  'misc.': 'mdi:hammer-wrench',
  quests: 'mdi:book-open',
  crafting: 'mdi:hammer',
  theme: 'mdi:palette',
  arena: 'mdi:sword-cross',
}

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
const categoryIcon = computed(() => categoryIcons[props.room.category.toLowerCase()] ?? 'mdi:cube')
</script>

<template>
  <li
    @click="!isLocked && emit('select', room)"
    role="button"
    tabindex="0"
    @keydown.enter.prevent="!isLocked && emit('select', room)"
    @keydown.space.prevent="!isLocked && emit('select', room)"
    class="room-menu-item"
    :class="{
      locked: isLocked,
      affordable: !isLocked && canAfford,
      expensive: !isLocked && !canAfford,
    }"
  >
    <div class="room-item-content">
      <div class="room-header">
        <div class="room-name">{{ room.name }}</div>
        <Icon v-if="isLocked" icon="mdi:lock" class="lock-icon" />
      </div>

      <div class="room-icon">
        <img
          v-if="room.image_url && showRoomImage"
          :src="getRoomImageUrl(room.image_url) ?? undefined"
          :alt="`${room.name} preview`"
          class="room-preview"
          @error="showRoomImage = false"
        />
        <Icon v-else :icon="categoryIcon" class="category-icon" />
      </div>

      <div class="room-details">
        <div class="room-category">
          <Icon :icon="categoryIcon" class="w-4 h-4" />
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
          <UProgressBar
            v-if="isLocked"
            :model-value="populationProgress"
            :height="4"
            :glow="false"
            color="var(--color-info)"
            ariaLabel="Population requirement progress"
            class="population-progress"
          />
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
  background: var(--color-surface);
  border: 2px solid var(--color-surface-hover);
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.25s ease;
  font-family: 'Courier New', monospace;
  position: relative;
  overflow: hidden;
}

.room-menu-item.affordable {
  border-color: var(--color-theme-primary);
  background: var(--color-surface-raised);
}

.room-menu-item.affordable:hover {
  border-color: var(--color-theme-primary);
  transform: translateY(-3px);
  box-shadow: 0 6px 16px var(--color-theme-glow);
  background: var(--color-surface-hover);
}

.room-menu-item.expensive {
  border-color: var(--color-warning);
  background: var(--color-surface);
}

.room-menu-item.expensive:hover {
  border-color: var(--color-warning);
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(255, 153, 0, 0.2);
}

.room-menu-item.locked {
  border-color: var(--color-gray-600);
  opacity: 0.5;
  cursor: not-allowed;
  background: var(--color-surface-sunken);
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
  border-bottom: 1px solid var(--color-surface-hover);
}

.room-name {
  color: var(--color-theme-primary);
  font-size: 0.95rem;
  font-weight: bold;
  letter-spacing: 0.025em;
}

.lock-icon {
  width: 18px;
  height: 18px;
  color: var(--color-danger);
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
  transition: transform 0.25s ease;
}

.room-preview {
  width: 100%;
  height: 64px;
  object-fit: contain;
  transition: transform 0.25s ease;
}

.room-menu-item:hover .category-icon,
.room-menu-item:hover .room-preview {
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
  color: var(--color-gray-400);
}

.room-cost {
  color: var(--color-warning);
  font-weight: bold;
}

.room-population-section {
  display: flex;
  flex-direction: column;
  gap: 0.25rem;
}

.room-population {
  color: var(--color-info);
}

.population-progress {
  border: 0;
  border-radius: 2px;
  background: rgb(136 204 255 / 0.2);
  box-shadow: none;
}

.population-progress :deep(.u-progress-bar__fill) {
  border-radius: 2px;
  box-shadow: 0 0 4px rgba(136, 204, 255, 0.5);
}
</style>
