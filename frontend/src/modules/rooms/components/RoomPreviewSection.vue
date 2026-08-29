<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

interface Props {
  roomName: string
  imageUrl: string | null
  roomImageUrl: string | null
  dwellerCapacity: number
  assignedDwellers: DwellerShort[]
  /** Only rooms whose policy allows apprentices (production) render the slot. */
  showApprenticeSlot?: boolean
}

const props = withDefaults(defineProps<Props>(), { showApprenticeSlot: false })

const workerDwellers = computed(() => props.assignedDwellers.filter((dweller) => !dweller.apprentice_stat))
const apprentice = computed(() => props.assignedDwellers.find((dweller) => dweller.apprentice_stat))
</script>

<template>
  <div class="section room-preview-section">
    <h3 class="section-title">
      <Icon icon="mdi:image-outline" class="h-5 w-5" />
      Room Preview
    </h3>
    <div class="preview-container">
      <div class="room-image-container">
        <img v-if="roomImageUrl" :src="roomImageUrl" :alt="roomName || 'Room'" class="room-image" />
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
                'slot-filled': workerDwellers[slot - 1],
              }"
            >
              <template v-if="workerDwellers[slot - 1]">
                <div class="placeholder-dweller">
                  <span class="dweller-initial">{{ workerDwellers[slot - 1]?.first_name[0] }}</span>
                </div>
              </template>
              <template v-else>
                <div class="placeholder-dweller empty">
                  <Icon icon="mdi:account-outline" class="h-6 w-6 opacity-30" />
                </div>
              </template>
            </div>
            <div v-if="showApprenticeSlot" class="dweller-sprite-slot apprentice-slot" :class="{ 'slot-filled': apprentice }">
              <div class="placeholder-dweller">
                <span v-if="apprentice" class="dweller-initial">{{ apprentice.first_name[0] }}</span>
                <Icon v-else icon="mdi:school-outline" class="h-6 w-6 opacity-30" />
                <span
                  class="apprentice-marker"
                  :aria-label="
                    apprentice?.apprentice_stat ? `Apprentice training ${apprentice.apprentice_stat}` : 'Apprentice slot'
                  "
                  role="img"
                >
                  <Icon icon="mdi:school-outline" />
                  {{ apprentice?.apprentice_stat?.charAt(0).toUpperCase() ?? '+' }}
                </span>
              </div>
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
  gap: 0.5rem;
}

.section-title {
  display: flex;
  align-items: center;
  gap: 0.4rem;
  font-size: 0.875rem;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--color-theme-primary);
  margin: 0;
}

.section-title :deep(svg) {
  width: 0.875rem;
  height: 0.875rem;
}

.room-preview-section {
  background: var(--color-surface);
  padding: 0.5rem;
  border-radius: 8px;
  border: 1px solid var(--color-theme-glow);
}

.preview-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.room-image-container {
  position: relative;
  min-height: 180px;
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
  max-height: 260px;
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
  background: var(--color-surface-sunken);
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
  color: var(--color-gray-500);
  font-style: italic;
}

.dweller-sprites-overlay {
  position: absolute;
  bottom: 0.5rem;
  left: 0.5rem;
  right: 0.5rem;
  display: flex;
  justify-content: space-evenly;
  z-index: 10;
}

.dweller-sprite-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
}

.placeholder-dweller {
  position: relative;
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-surface-sunken);
  border: 2px dashed var(--color-theme-glow);
  border-radius: 8px;
  transition: all 0.3s;
}

.placeholder-dweller.empty {
  background: rgba(128, 128, 128, 0.05);
  border-color: rgba(128, 128, 128, 0.2);
}

.slot-filled .placeholder-dweller {
  background: var(--color-surface-raised);
  border: 2px solid var(--color-theme-primary);
  animation: glow-pulse 2s ease-in-out infinite;
}

.apprentice-slot .placeholder-dweller {
  border-color: var(--color-warning);
}


.apprentice-marker {
  position: absolute;
  top: -0.35rem;
  right: -0.35rem;
  display: inline-flex;
  align-items: center;
  gap: 0.1rem;
  padding: 0.1rem 0.2rem;
  border: 1px solid var(--color-warning);
  border-radius: 999px;
  background: var(--color-surface-sunken);
  color: var(--color-warning);
  font-size: 0.625rem;
  font-weight: 700;
  box-shadow: 0 0 8px var(--color-warning);
}

.apprentice-marker :deep(svg) {
  width: 0.75rem;
  height: 0.75rem;
  filter: drop-shadow(0 0 3px var(--color-warning));
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
