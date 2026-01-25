<script setup lang="ts">
import { computed } from 'vue'
import { useRoomStore } from '../stores/room'
import RoomMenuItem from './RoomMenuItem.vue'
import type { RoomTemplate } from '../models/room'

const roomStore = useRoomStore()
const availableRooms = computed(() => Array.isArray(roomStore.availableRooms) ? roomStore.availableRooms : [])

const emit = defineEmits<{
  (e: 'roomSelected', room: RoomTemplate): void
  (e: 'close'): void
}>()

const selectRoom = (room: RoomTemplate) => {
  emit('roomSelected', room)
  roomStore.selectRoom(room)
}

const closeModal = () => {
  emit('close')
}
</script>

<template>
  <div class="modal-overlay" @click.self="closeModal">
    <div class="modal-content">
      <div class="modal-header">
        <h2 class="text-xl font-bold text-terminalGreen">Room to Build</h2>
        <button @click="closeModal" class="close-btn" aria-label="Close">×</button>
      </div>
      <div class="rooms-scroll-container">
        <ul class="rooms-grid">
          <RoomMenuItem
            v-for="room in availableRooms"
            :key="`${room.name}-${room.category}`"
            :room="room"
            @select="selectRoom"
          />
        </ul>
      </div>
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
  background: rgba(0, 0, 0, 0.85);
  display: flex;
  justify-content: center;
  align-items: center;
  z-index: 1000;
  padding: 1rem;
}

.modal-content {
  background: rgba(17, 17, 17, 0.95);
  border: 2px solid var(--color-theme-primary);
  border-radius: 4px;
  box-shadow: 0 0 20px var(--color-theme-glow);
  max-width: 1200px;
  width: 100%;
  max-height: 80vh;
  display: flex;
  flex-direction: column;
  overflow: hidden;
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 1rem 1.5rem;
  border-bottom: 1px solid var(--color-theme-primary);
  flex-shrink: 0;
}

.close-btn {
  background: none;
  border: none;
  color: var(--color-theme-primary);
  font-size: 2rem;
  line-height: 1;
  cursor: pointer;
  padding: 0;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.2s;
}

.close-btn:hover {
  color: #fff;
  text-shadow: 0 0 8px var(--color-theme-glow);
}

.rooms-scroll-container {
  overflow-y: auto;
  overflow-x: hidden;
  padding: 1.5rem;
  flex: 1;
}

.rooms-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 1rem;
  list-style: none;
  margin: 0;
  padding: 0;
}

@media (max-width: 768px) {
  .rooms-grid {
    grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
  }
}
</style>
