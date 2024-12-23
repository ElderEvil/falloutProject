<script setup lang="ts">
import { ref } from 'vue'
import { NButton, NSelect, NSpace, NModal, useMessage } from 'naive-ui'
import { useVaultStore } from '@/stores/vault'
import type { Room } from '@/types/vault'

const vaultStore = useVaultStore()
const message = useMessage()
const showNewRoomModal = ref(false)
const selectedRoomType = ref<Room['type']>('power')

const roomTypes = [
  { label: 'POWER GENERATOR', value: 'power' },
  { label: 'WATER TREATMENT', value: 'water' },
  { label: 'FOOD PRODUCTION', value: 'food' },
  { label: 'LIVING QUARTERS', value: 'living' }
]

const handleAddRoom = () => {
  if (vaultStore.addRoom(selectedRoomType.value)) {
    showNewRoomModal.value = false
    message.success('Room constructed successfully')
  } else {
    message.error('Cannot construct more rooms')
  }
}
</script>

<template>
  <div class="room-management">
    <NSpace justify="end">
      <NButton @click="showNewRoomModal = true" class="construct-button">
        CONSTRUCT NEW ROOM
      </NButton>
    </NSpace>

    <NModal
      v-model:show="showNewRoomModal"
      preset="dialog"
      title="CONSTRUCT NEW ROOM"
      positive-text="CONSTRUCT"
      negative-text="CANCEL"
      @positive-click="handleAddRoom"
    >
      <NSpace vertical>
        <div>SELECT ROOM TYPE:</div>
        <NSelect v-model:value="selectedRoomType" :options="roomTypes" class="room-type-select" />
      </NSpace>
    </NModal>
  </div>
</template>

<style scoped>
.room-management {
  margin-bottom: 16px;
}

.construct-button {
  border: 2px solid #00ff00;
}

:deep(.room-type-select) {
  min-width: 200px;
}
</style>
