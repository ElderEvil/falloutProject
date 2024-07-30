<script setup lang="ts">
import { computed } from 'vue'
import { useRoomStore } from '@/stores/room'
import RoomMenuItem from './RoomMenuItem.vue'

const roomStore = useRoomStore()
const availableRooms = computed(() => roomStore.availableRooms)

const emit = defineEmits<{
  (e: 'roomSelected', room: Room): void
  (e: 'close'): void
}>()

const selectRoom = (room: RoomReadShort) => {
  console.log('Selecting room:', room)
  emit('roomSelected', room)
  roomStore.selectRoom(room)
  console.log('Store state after selection:', roomStore.selectedRoom, roomStore.isPlacingRoom)
}

const closeModal = () => {
  emit('close')
}
</script>

<template>
  <div class="modal-overlay" @click.self="closeModal">
    <div class="modal-content">
      <h2 class="mb-4 text-2xl">Select a Room to Build</h2>
      <ul class="flex space-x-4 overflow-x-auto">
        <RoomMenuItem
          v-for="room in availableRooms"
          :key="room.id"
          :room="room"
          @select="selectRoom"
        />
      </ul>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background: rgba(0, 0, 0, 0.8);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
}

.modal-content {
  background: #222;
  border: 1px solid #00ff00;
  padding: 20px;
  max-width: 90%;
  max-height: 90%;
  overflow-y: auto;
}

.modal-content ul {
  display: flex;
  overflow-x: auto;
}

.modal-content li {
  flex-shrink: 0;
  min-width: 150px;
  text-align: center;
}
</style>
