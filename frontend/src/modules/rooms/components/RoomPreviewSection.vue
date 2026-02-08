<script setup lang="ts">
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

interface Props {
  roomName: string
  imageUrl: string | null
  roomImageUrl: string | null
  dwellerCapacity: number
  assignedDwellers: DwellerShort[]
}

defineProps<Props>()
</script>

<template>
  <div class="section room-preview-section">
    <h3 class="section-title">
      <Icon icon="mdi:image-outline" class="h-5 w-5" />
      Room Preview
    </h3>
    <div class="preview-container">
      <div class="room-image-container">
            <img
              v-if="roomImageUrl"
              :src="roomImageUrl"
              :alt="roomName || 'Room'"
              class="room-image"
            />
        <div class="room-image-placeholder" :class="{ 'has-image': imageUrl }">
          <template v-if="!imageUrl">
            <Icon icon="mdi:home-variant-outline" class="h-16 w-16 opacity-30" />
            <p class="placeholder-text">Room Sprite</p>
            <p class="placeholder-subtext">No Image Available</p>
          </template>

          <div class="dweller-sprites-overlay">
            <div
              v-for="slot in dwellerCapacity"
              :key="`slot-${slot}`"
              class="dweller-sprite-slot"
              :class="{
                'slot-filled': assignedDwellers[slot - 1],
              }"
            >
              <template v-if="assignedDwellers[slot - 1]">
                <div class="placeholder-dweller">
                  <span class="dweller-initial">{{
                    assignedDwellers[slot - 1]?.first_name[0]
                  }}</span>
                </div>
              </template>
              <template v-else>
                <div class="placeholder-dweller empty">
                  <Icon icon="mdi:account-outline" class="h-6 w-6 opacity-30" />
                </div>
              </template>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  margin: 0;
}

.room-preview-section {
  background: rgba(0, 0, 0, 0.2);
  padding: 0.75rem;
  border-radius: 8px;
  border: 1px solid var(--color-theme-glow);
}

.preview-container {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}

.room-image-container {
  position: relative;
  min-height: 150px;
  border-radius: 8px;
  overflow: hidden;
  border: 2px solid var(--color-theme-glow);
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.8);
}

.room-image {
  width: 100%;
  height: auto;
  max-height: 300px;
  object-fit: contain;
  background: rgba(0, 0, 0, 0.8);
  display: block;
}

.room-image-placeholder {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  padding: 1.25rem;
}

.room-image-placeholder.has-image {
  background: transparent;
  pointer-events: none;
}

.placeholder-text {
  margin: 1rem 0 0.25rem;
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.placeholder-subtext {
  font-size: 0.875rem;
  color: #888;
  font-style: italic;
}

.dweller-sprites-overlay {
  position: absolute;
  bottom: 1rem;
  left: 1rem;
  right: 1rem;
  display: flex;
  justify-content: space-evenly;
  z-index: 10;
}

.dweller-sprite-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.25rem;
}

.placeholder-dweller {
  width: 64px;
  height: 64px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 0, 0, 0.3);
  border: 2px dashed var(--color-theme-glow);
  border-radius: 8px;
  transition: all 0.3s;
}

.placeholder-dweller.empty {
  background: rgba(128, 128, 128, 0.05);
  border-color: rgba(128, 128, 128, 0.2);
}

.slot-filled .placeholder-dweller {
  background: rgba(0, 0, 0, 0.4);
  border: 2px solid var(--color-theme-primary);
  animation: glow-pulse 2s ease-in-out infinite;
}

@keyframes glow-pulse {
  0%,
  100% {
    box-shadow: 0 0 8px var(--color-theme-glow);
  }
  50% {
    box-shadow: 0 0 16px var(--color-theme-primary);
  }
}

.dweller-initial {
  font-size: 1.5rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  text-shadow: 0 0 8px var(--color-theme-glow);
}
</style>
