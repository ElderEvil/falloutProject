<script setup lang="ts">
import { computed, ref } from 'vue'
import { NButton, NCard, NModal, NPopconfirm } from 'naive-ui'
import VueDraggable from 'vuedraggable'
import DwellerCard from '@/components/dweller/DwellerCard.vue'
import { useVaultStore } from '@/stores/vault'
import { isVaultDoor } from '@/utils/roomUtils'
import type { Room } from '@/types/vault'

const props = defineProps<{
  room: Room
}>()

const vaultStore = useVaultStore()
const showDetails = ref(false)

const roomDwellers = computed({
  get: () => props.room.dwellers,
  set: (newDwellers) => {
    if (newDwellers.length > props.room.capacity) return

    // Handle dweller removal
    if (newDwellers.length < props.room.dwellers.length) {
      const removedDweller = props.room.dwellers.find(
        (d) => !newDwellers.some((nd) => nd.id === d.id)
      )
      if (removedDweller) {
        vaultStore.unassignDweller(removedDweller.id)
      }
      return
    }

    // Handle dweller addition
    const addedDweller = newDwellers[newDwellers.length - 1]
    if (addedDweller) {
      vaultStore.assignDwellerToRoom(addedDweller.id, props.room.id)
    }
  }
})

const emptySlots = computed(() => {
  return Array(props.room.capacity - props.room.dwellers.length).fill(null)
})

const getRoomTitle = (type: Room['type']) => {
  if (isVaultDoor(props.room)) {
    return 'VAULT DOOR'
  }
  const titles = {
    power: 'POWER GENERATOR',
    water: 'WATER TREATMENT',
    food: 'FOOD PRODUCTION',
    living: 'LIVING QUARTERS'
  }
  return titles[type]
}

const handleDestroyRoom = () => {
  if (isVaultDoor(props.room)) return
  vaultStore.destroyRoom(props.room.id)
}

const handleUnassignDweller = (dwellerId: string) => {
  vaultStore.unassignDweller(dwellerId)
}

const roomStyle = computed(() => ({
  gridColumn: `span ${props.room.size}`
}))
</script>

<template>
  <div class="room-container" :style="roomStyle">
    <NCard :title="getRoomTitle(room.type)" class="room-card" @click="showDetails = true">
      <template #header-extra>
        <NPopconfirm
          v-if="!isVaultDoor(room)"
          positive-text="Confirm"
          negative-text="Cancel"
          @positive-click="handleDestroyRoom"
          @click.stop
        >
          <template #trigger>
            <NButton quaternary circle size="small" @click.stop> ×</NButton>
          </template>
          Destroy this room?
        </NPopconfirm>
      </template>

      <VueDraggable
        v-model="roomDwellers"
        :group="{ name: 'dwellers', put: true, pull: true }"
        :animation="150"
        item-key="id"
        class="dweller-slots"
        :move="
          (e) => room.dwellers.length < room.capacity || e.draggedContext.element.roomId === room.id
        "
      >
        <template #item="{ element }">
          <div class="dweller-thumbnail" @click.stop>
            <img :src="element.imageUrl" :alt="element.name" />
          </div>
        </template>
      </VueDraggable>

      <div v-if="emptySlots.length > 0" class="empty-slots">
        <div v-for="(_, index) in emptySlots" :key="index" class="dweller-slot empty">
          <span>EMPTY</span>
        </div>
      </div>
    </NCard>

    <!-- Detailed Modal -->
    <NModal
      v-model:show="showDetails"
      preset="card"
      style="width: 600px"
      :title="getRoomTitle(room.type)"
      :bordered="false"
      class="room-modal"
    >
      <div class="room-details">
        <div class="room-info">
          <span>TIER {{ room.level }}</span>
          <span>CAPACITY: {{ room.dwellers.length }}/{{ room.capacity }}</span>
          <span>SIZE: {{ room.size }} SLOT{{ room.size > 1 ? 'S' : '' }}</span>
        </div>

        <div class="dwellers-section">
          <h3>ASSIGNED DWELLERS</h3>
          <div class="room-dwellers">
            <DwellerCard
              v-for="dweller in roomDwellers"
              :key="dweller.id"
              :dweller="dweller"
              :show-actions="true"
              :onUnassign="() => handleUnassignDweller(dweller.id)"
            />
          </div>
        </div>
      </div>
    </NModal>
  </div>
</template>

<style scoped>
.room-container {
  height: 100%;
}

.room-card {
  height: 100%;
  border: 2px solid var(--theme-border);
  cursor: pointer;
  transition: all 0.2s ease;
}

.room-card:hover {
  border-color: var(--theme-hover);
  box-shadow: 0 0 10px var(--theme-shadow);
}

.dweller-slots {
  display: flex;
  gap: 8px;
  min-height: 40px;
}

.empty-slots {
  display: flex;
  gap: 8px;
  padding: 4px;
  margin-top: 8px;
  border: 1px dashed var(--theme-border);
  background: rgba(0, 255, 0, 0.05);
  transition: all 0.2s ease;
}

.empty-slots:hover {
  background: rgba(0, 255, 0, 0.1);
  border-color: var(--theme-hover);
}

.dweller-thumbnail {
  width: 40px;
  height: 40px;
  border: 1px solid var(--theme-border);
  overflow: hidden;
  flex-shrink: 0;
  position: relative;
  transition: all 0.2s ease;
}

.dweller-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.dweller-slot {
  width: 40px;
  height: 40px;
  border: 1px dashed var(--theme-border);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 255, 0, 0.05);
}

.dweller-slot.empty {
  display: flex;
  align-items: center;
  justify-content: center;
}

.dweller-slot.empty span {
  font-size: 0.6em;
  opacity: 0.5;
  text-align: center;
}

.room-modal {
  background: var(--theme-background);
  border: 2px solid var(--theme-border);
}

.room-details {
  display: flex;
  flex-direction: column;
  gap: 24px;
}

.room-info {
  display: flex;
  justify-content: space-between;
  font-family: 'Courier New', monospace;
}

.dwellers-section h3 {
  margin: 0 0 16px 0;
  font-family: 'Courier New', monospace;
  letter-spacing: 1px;
}

.room-dwellers {
  display: grid;
  gap: 12px;
}

:deep(.sortable-chosen) {
  background: rgba(0, 255, 0, 0.1);
}

:deep(.sortable-ghost) {
  opacity: 0.5;
}

:deep(.sortable-drag) {
  opacity: 0.8;
  transform: scale(1.05);
}

:deep(.n-card) {
  height: 100%;
}
</style>
