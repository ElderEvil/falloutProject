<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { useVaultStore } from '@/stores/vault'
import { useRoute } from 'vue-router'
import type { Room } from '@/models/room'

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

const isLocked = computed(() => {
  const popRequired = props.room.population_required
  if (!popRequired) return false
  const currentPop = currentVault.value?.dweller_count ?? 0
  return currentPop < popRequired
})

const getCategoryIcon = (category: string) => {
  const icons: Record<string, string> = {
    'Production': 'mdi:lightning-bolt',
    'Capacity': 'mdi:home',
    'Training': 'mdi:school',
    'Misc.': 'mdi:hammer-wrench'
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
          v-if="room.image_url"
          :icon="getCategoryIcon(room.category)"
          class="category-icon"
        />
        <div v-else class="category-icon-placeholder">
          <Icon :icon="getCategoryIcon(room.category)" class="w-12 h-12" />
        </div>
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

        <div v-if="room.population_required" class="room-population">
          <Icon icon="mdi:account-group" class="w-4 h-4" />
          <span>{{ room.population_required }} dwellers</span>
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
  min-width: 200px;
  padding: 1rem;
  background: rgba(30, 30, 30, 0.9);
  border: 2px solid #555;
  border-radius: 8px;
  cursor: pointer;
  transition: all 0.2s;
  font-family: 'Courier New', monospace;
}

.room-menu-item.affordable {
  border-color: #00ff00;
}

.room-menu-item.affordable:hover {
  background: rgba(0, 80, 0, 0.5);
  border-color: #00ff00;
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 255, 0, 0.3);
}

.room-menu-item.expensive {
  border-color: #ff9900;
}

.room-menu-item.expensive:hover {
  background: rgba(80, 40, 0, 0.5);
}

.room-menu-item.locked {
  border-color: #666;
  opacity: 0.6;
  cursor: not-allowed;
}

.room-item-content {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.room-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.room-name {
  color: #00ff00;
  font-size: 1.1rem;
  font-weight: bold;
}

.lock-icon {
  width: 20px;
  height: 20px;
  color: #ff0000;
}

.room-icon {
  display: flex;
  justify-content: center;
  align-items: center;
  height: 60px;
}

.category-icon {
  width: 48px;
  height: 48px;
  color: #00ff00;
}

.category-icon-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 255, 0, 0.1);
  border-radius: 50%;
  padding: 0.5rem;
}

.room-details {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
  font-size: 0.875rem;
}

.room-category,
.room-cost,
.room-population,
.room-size {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  color: #aaa;
}

.room-cost {
  color: #fbbf24;
  font-weight: bold;
}
</style>
