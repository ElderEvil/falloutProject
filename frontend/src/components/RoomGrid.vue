<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoomStore } from '@/stores/room'
import { useAuthStore } from '@/stores/auth'
import DestroyIcon from '@/components/icons/DestroyButton.vue'

const roomStore = useRoomStore()
const authStore = useAuthStore()
const rooms = ref(roomStore.rooms)
const selectedRoomId = ref<string | null>(null)

watch(
  () => roomStore.rooms,
  (newRooms) => {
    rooms.value = newRooms
  }
)

const toggleRoomSelection = (roomId: string) => {
  selectedRoomId.value = selectedRoomId.value === roomId ? null : roomId
}

const destroyRoom = async (roomId: string, event: Event) => {
  event.stopPropagation() // Prevent the room from being deselected
  if (confirm('Are you sure you want to destroy this room?')) {
    await roomStore.destroyRoom(roomId, authStore.token as string)
    selectedRoomId.value = null
  }
}
</script>

<template>
  <div class="room-grid">
    <div
      v-for="room in rooms"
      :key="room.id"
      :style="{
        gridRow: room.coordinate_y + 1,
        gridColumn: `${room.coordinate_x + 1} / span ${Math.ceil(room.size / 3)}`
      }"
      class="room"
      :class="{ selected: selectedRoomId === room.id }"
      @click="toggleRoomSelection(room.id)"
    >
      <div class="room-content">
        <h3 class="room-name">{{ room.name }}</h3>
        <p class="room-category">{{ room.category }}</p>
        <button
          v-if="selectedRoomId === room.id"
          @click="destroyRoom(room.id, $event)"
          class="destroy-button"
          title="Destroy Room"
        >
          <DestroyIcon />
        </button>
      </div>
    </div>
    <div v-for="n in 25 * 8 - rooms.length" :key="'empty-' + n" class="room empty"></div>
  </div>
</template>

<style scoped>
.room-grid {
  display: grid;
  grid-template-columns: repeat(8, 1fr);
  grid-template-rows: repeat(25, 1fr);
  gap: 2px;
  position: relative;
  max-width: 100%;
}

.room {
  border: 1px solid #00ff00;
  background-color: rgba(0, 0, 0, 0.5);
  text-align: center;
  transition:
    transform 0.3s,
    background-color 0.3s;
  cursor: pointer;
}

.room:hover {
  transform: scale(1.05);
}

.room.selected {
  background-color: rgba(0, 128, 0, 0.7);
}

.room-content {
  padding: 8px;
}

.room-name {
  font-size: 1.2em;
  font-weight: bold;
}

.room-category {
  font-size: 0.9em;
}

.empty {
  border: 1px dashed #555;
  background-color: rgba(0, 0, 0, 0.3);
}

.room-grid::before {
  content: '';
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  border: 2px solid #00ff00;
  pointer-events: none;
  box-sizing: border-box;
}

.destroy-button {
  position: absolute;
  bottom: 4px;
  right: 4px;
  background-color: rgba(255, 0, 0, 0.7);
  color: white;
  border: none;
  border-radius: 50%;
  width: 24px;
  height: 24px;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  transition: background-color 0.3s;
}

.destroy-button:hover {
  background-color: rgba(255, 0, 0, 0.9);
}
</style>
