<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'

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
  unassign: [dwellerId: string]
  assignWorker: []
  assignApprentice: []
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

          <div class="dweller-sprites-overlay" :class="`slot-count-${dwellerCapacity}`">
            <div
              v-for="slot in dwellerCapacity"
              :key="`slot-${slot}`"
              class="dweller-sprite-slot"
              :class="{
                'slot-filled': workerDwellers[slot - 1],
              }"
            >
              <div v-if="workerDwellers[slot - 1]" class="scene-occupant">
                <button
                  type="button"
                  class="placeholder-dweller scene-dweller"
                  :aria-label="`Open ${workerDwellers[slot - 1]?.first_name} ${workerDwellers[slot - 1]?.last_name ?? ''}`"
                  @click="emit('activate', workerDwellers[slot - 1]!.id)"
                >
                  <DwellerPortrait
                    :thumbnail-url="workerDwellers[slot - 1]?.thumbnail_url"
                    :alt="`${workerDwellers[slot - 1]?.first_name} ${workerDwellers[slot - 1]?.last_name ?? ''}`"
                    image-class="scene-dweller-portrait"
                    fallback-class="scene-dweller-icon"
                    prefer-thumbnail
                  />
                </button>
                <button
                  type="button"
                  class="scene-unassign"
                  :aria-label="`Unassign ${workerDwellers[slot - 1]?.first_name} ${workerDwellers[slot - 1]?.last_name ?? ''}`"
                  @click="emit('unassign', workerDwellers[slot - 1]!.id)"
                >
                  <Icon icon="mdi:account-minus-outline" />
                </button>
              </div>
              <button
                v-else
                type="button"
                class="placeholder-dweller empty scene-empty-slot scene-empty-worker"
                aria-label="Assign worker to this slot"
                @click="emit('assignWorker')"
              >
                <Icon icon="mdi:account-outline" class="h-6 w-6 opacity-30" />
                <span class="worker-marker" aria-label="Assign worker" role="img">
                  <Icon icon="mdi:account-plus-outline" />+
                </span>
              </button>
            </div>
            <div v-if="showApprenticeSlot" class="dweller-sprite-slot apprentice-slot" :class="{ 'slot-filled': apprentice }">
              <div v-if="apprentice" class="scene-occupant">
                <button
                  type="button"
                  class="placeholder-dweller scene-dweller"
                  :aria-label="`Open ${apprentice.first_name} ${apprentice.last_name ?? ''}`"
                  @click="emit('activate', apprentice.id)"
                >
                  <DwellerPortrait
                    :thumbnail-url="apprentice.thumbnail_url"
                    :alt="`${apprentice.first_name} ${apprentice.last_name ?? ''}`"
                    image-class="scene-dweller-portrait"
                    fallback-class="scene-dweller-icon"
                    prefer-thumbnail
                  />
                  <span
                    class="apprentice-marker"
                    :aria-label="`Apprentice training ${apprentice.apprentice_stat}`"
                    role="img"
                  >
                    <Icon icon="mdi:school-outline" />
                    {{ apprentice.apprentice_stat?.charAt(0).toUpperCase() ?? '+' }}
                  </span>
                </button>
                <button
                  type="button"
                  class="scene-unassign"
                  :aria-label="`Unassign ${apprentice.first_name} ${apprentice.last_name ?? ''}`"
                  @click="emit('unassign', apprentice.id)"
                >
                  <Icon icon="mdi:account-minus-outline" />
                </button>
              </div>
              <button
                v-else
                type="button"
                class="placeholder-dweller scene-empty-slot scene-empty-apprentice"
                aria-label="Assign child or teen apprentice to this slot"
                @click="emit('assignApprentice')"
              >
                <Icon icon="mdi:school-outline" class="h-6 w-6 opacity-30" />
                <span class="apprentice-marker" aria-label="Apprentice slot" role="img">
                  <Icon icon="mdi:school-outline" />+
                </span>
              </button>
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
  --scene-dweller-size: 3.5rem;
  position: absolute;
  bottom: 0.75rem;
  left: 0.75rem;
  right: 0.75rem;
  display: flex;
  justify-content: space-evenly;
  z-index: 10;
}

.slot-count-2 {
  --scene-dweller-size: 4.75rem;
  justify-content: space-around;
}

.slot-count-4 {
  --scene-dweller-size: 4rem;
}

.slot-count-6 {
  --scene-dweller-size: 3.25rem;
}

.dweller-sprite-slot {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 0.15rem;
}

.scene-occupant {
  position: relative;
}

.placeholder-dweller {
  position: relative;
  width: var(--scene-dweller-size);
  height: var(--scene-dweller-size);
  padding: 0;
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

.scene-unassign {
  position: absolute;
  top: -0.3rem;
  right: -0.3rem;
  z-index: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--color-danger) 60%, transparent);
  border-radius: 999px;
  background: var(--color-surface-sunken);
  color: var(--color-danger);
  cursor: pointer;
  opacity: 0;
}

.scene-occupant:hover .scene-unassign,
.scene-occupant:focus-within .scene-unassign {
  opacity: 1;
}

.scene-unassign:hover,
.scene-unassign:focus-visible {
  background: color-mix(in srgb, var(--color-danger) 20%, transparent);
  outline: none;
}

.scene-unassign :deep(svg) {
  width: 0.8rem;
  height: 0.8rem;
}

.scene-empty-slot {
  color: var(--color-theme-primary);
  cursor: pointer;
}

.scene-empty-slot:hover,
.scene-empty-slot:focus-visible {
  border-color: var(--color-theme-primary);
  background: color-mix(in srgb, var(--color-theme-primary) 12%, transparent);
  outline: none;
}

.scene-empty-apprentice {
  border-color: color-mix(in srgb, var(--color-warning) 60%, transparent);
  color: var(--color-warning);
}

.scene-empty-apprentice:hover,
.scene-empty-apprentice:focus-visible {
  border-color: var(--color-warning);
  background: color-mix(in srgb, var(--color-warning) 12%, transparent);
}

.worker-marker,
.apprentice-marker {
  position: absolute;
  top: -0.35rem;
  right: -0.35rem;
  display: inline-flex;
  align-items: center;
  gap: 0.1rem;
  padding: 0.1rem 0.2rem;
  border: 1px solid var(--color-theme-primary);
  border-radius: 999px;
  background: var(--color-surface-sunken);
  color: var(--color-theme-primary);
  font-size: 0.625rem;
  font-weight: 700;
}

.worker-marker :deep(svg) {
  width: 0.75rem;
  height: 0.75rem;
  filter: drop-shadow(0 0 3px var(--color-theme-glow));
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
  border: 1px solid var(--color-warning);
  color: var(--color-warning);
}

.apprentice-marker :deep(svg) {
  width: 0.75rem;
  height: 0.75rem;
  filter: drop-shadow(0 0 3px var(--color-warning));
}

.scene-dweller :deep(.scene-dweller-portrait) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.scene-dweller :deep([role='img']) {
  display: inline-flex;
  width: 74%;
  height: 74%;
  align-items: center;
  justify-content: center;
}

.scene-dweller :deep(.scene-dweller-icon) {
  width: 100%;
  height: 100%;
  color: var(--color-theme-primary);
}
</style>
