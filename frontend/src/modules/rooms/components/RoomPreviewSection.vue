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
const emit = defineEmits<{
  activate: [dwellerId: string]
}>()

const sceneImageUrl = computed(() => props.roomImageUrl ?? props.imageUrl)
const workerDwellers = computed(() => props.assignedDwellers.filter((dweller) => !dweller.apprentice_stat))
const apprentice = computed(() => props.assignedDwellers.find((dweller) => dweller.apprentice_stat))
</script>

<template>
  <section class="room-preview-section room-scene" :aria-label="`${roomName} room scene`">
    <div class="preview-container">
      <div class="room-image-container">
        <img v-if="sceneImageUrl" :src="sceneImageUrl" :alt="roomName || 'Room'" class="room-image" />
        <div class="room-image-placeholder" :class="{ 'has-image': sceneImageUrl }">
          <template v-if="!sceneImageUrl">
            <Icon icon="mdi:home-variant-outline" class="h-16 w-16 opacity-30" />
            <p class="placeholder-text">Room Scene</p>
            <p class="placeholder-subtext">Visual feed unavailable</p>
          </template>

          <div class="scene-readout">
            <span class="scene-label"><Icon icon="mdi:movie-open-outline" /> Live room scene</span>
            <span class="scene-status"><Icon icon="mdi:account-hard-hat-outline" /> {{ workerDwellers.length }}/{{ dwellerCapacity }} workers</span>
            <span v-if="showApprenticeSlot" class="scene-status apprentice-status">
              <Icon icon="mdi:school-outline" /> {{ apprentice ? 1 : 0 }}/1 apprentice
            </span>
          </div>

          <div class="dweller-sprites-overlay">
            <div
              v-for="slot in dwellerCapacity"
              :key="`slot-${slot}`"
              class="dweller-sprite-slot"
              :class="{
                'slot-filled': workerDwellers[slot - 1],
              }"
            >
              <button
                v-if="workerDwellers[slot - 1]"
                type="button"
                class="placeholder-dweller scene-dweller"
                :aria-label="`Open ${workerDwellers[slot - 1]?.first_name} ${workerDwellers[slot - 1]?.last_name ?? ''}`"
                @click="emit('activate', workerDwellers[slot - 1]!.id)"
              >
                <span class="dweller-initial">{{ workerDwellers[slot - 1]?.first_name[0] }}</span>
              </button>
              <div v-else class="placeholder-dweller empty">
                <Icon icon="mdi:account-outline" class="h-6 w-6 opacity-30" />
              </div>
            </div>
            <div v-if="showApprenticeSlot" class="dweller-sprite-slot apprentice-slot" :class="{ 'slot-filled': apprentice }">
              <button
                v-if="apprentice"
                type="button"
                class="placeholder-dweller scene-dweller"
                :aria-label="`Open ${apprentice.first_name} ${apprentice.last_name ?? ''}`"
                @click="emit('activate', apprentice.id)"
              >
                <span v-if="apprentice" class="dweller-initial">{{ apprentice.first_name[0] }}</span>
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
              </button>
              <div v-else class="placeholder-dweller">
                <Icon icon="mdi:school-outline" class="h-6 w-6 opacity-30" />
                <span class="apprentice-marker" aria-label="Apprentice slot" role="img">
                  <Icon icon="mdi:school-outline" />+
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.room-preview-section {
  position: relative;
  overflow: hidden;
  background: var(--color-surface-sunken);
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 42%, transparent);
  box-shadow: inset 0 0 2rem color-mix(in srgb, var(--color-theme-primary) 5%, transparent);
}

.preview-container {
  height: clamp(13rem, 31vw, 22rem);
  min-height: clamp(13rem, 31vw, 22rem);
}

.room-image-container {
  position: relative;
  height: 100%;
  min-height: 0;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  background:
    linear-gradient(90deg, color-mix(in srgb, var(--color-theme-primary) 9%, transparent), transparent 28%),
    rgba(0, 0, 0, 0.8);
}

.room-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
  background: rgba(0, 0, 0, 0.7);
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
  background: linear-gradient(135deg, var(--color-surface-sunken), color-mix(in srgb, var(--color-theme-primary) 8%, transparent));
  padding: 0.75rem;
}

.room-image-placeholder.has-image {
  background: transparent;
}

.room-image-container::after {
  position: absolute;
  inset: 0;
  pointer-events: none;
  content: '';
  background: repeating-linear-gradient(
    to bottom,
    color-mix(in srgb, var(--color-theme-primary) 7%, transparent) 0,
    color-mix(in srgb, var(--color-theme-primary) 7%, transparent) 1px,
    transparent 1px,
    transparent 4px
  );
}

.placeholder-text {
  margin: 0.5rem 0 0.15rem;
  font-size: 0.875rem;
  font-weight: 600;
  color: var(--color-theme-primary);
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

.placeholder-subtext {
  font-size: 0.6875rem;
  color: var(--color-gray-500);
  font-style: italic;
}

.scene-readout {
  position: absolute;
  top: 0.6rem;
  left: 0.7rem;
  right: 0.7rem;
  z-index: 1;
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 0.35rem 0.75rem;
  color: color-mix(in srgb, var(--color-theme-primary) 76%, transparent);
  font-size: 0.625rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  text-shadow: 0 1px 3px #000;
}

.scene-label,
.scene-status {
  display: inline-flex;
  align-items: center;
  gap: 0.25rem;
}

.scene-label {
  color: var(--color-theme-primary);
}

.scene-label :deep(svg),
.scene-status :deep(svg) {
  width: 0.8rem;
  height: 0.8rem;
}

.apprentice-status {
  color: var(--color-warning);
}

.dweller-sprites-overlay {
  position: absolute;
  bottom: 0.75rem;
  left: 0.75rem;
  right: 0.75rem;
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
  width: 34px;
  height: 34px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: color-mix(in srgb, var(--color-surface-sunken) 80%, #000);
  border: 1px dashed var(--color-theme-glow);
  border-radius: 3px;
}

.scene-dweller {
  color: inherit;
  cursor: pointer;
}

.scene-dweller:hover,
.scene-dweller:focus-visible {
  border-color: var(--color-theme-primary);
  box-shadow: 0 0 0.55rem var(--color-theme-glow);
  outline: none;
  transform: translateY(-0.15rem);
}

.apprentice-slot .scene-dweller:hover,
.apprentice-slot .scene-dweller:focus-visible {
  border-color: var(--color-warning);
  box-shadow: 0 0 0.55rem color-mix(in srgb, var(--color-warning) 45%, transparent);
}

.placeholder-dweller.empty {
  background: rgba(128, 128, 128, 0.05);
  border-color: rgba(128, 128, 128, 0.2);
}

.slot-filled .placeholder-dweller {
  background: var(--color-surface-raised);
  border: 1px solid var(--color-theme-primary);
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
}

.apprentice-marker :deep(svg) {
  width: 0.75rem;
  height: 0.75rem;
  filter: drop-shadow(0 0 3px var(--color-warning));
}

.dweller-initial {
  font-size: 1rem;
  font-weight: bold;
  color: var(--color-theme-primary);
  text-shadow: 0 0 4px var(--color-theme-glow);
}
</style>
