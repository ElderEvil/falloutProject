<script setup lang="ts">
import { ref, watch } from 'vue'
import { useRoomStore } from '@/stores/room'

const roomStore = useRoomStore()
const rooms = ref(roomStore.rooms)


watch(() => roomStore.rooms, (newRooms) => {
  rooms.value = newRooms
})

</script>

<template>
  <div class="room-grid">
    <div
      v-for="room in rooms"
      :key="room.id"
      :style="{ gridRow: room.coordinate_y + 1, gridColumn: room.coordinate_x + 1 }"
      class="room"
    >
      <div class="room-content">
        <h3 class="room-name">{{ room.name }}</h3>
        <p class="room-category">{{ room.category }}</p>
      </div>
    </div>
    <div
      v-for="n in 25 * 8 - rooms.length"
      :key="'empty-' + n"
      class="room empty"
    ></div>
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
  transition: transform 0.3s, background-color 0.3s;
}

.room:hover {
  transform: scale(1.05);
  background-color: rgba(0, 0, 0, 0.7);
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
</style>
