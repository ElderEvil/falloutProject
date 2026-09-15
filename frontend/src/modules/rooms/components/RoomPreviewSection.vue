<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'

interface Props {
  roomName: string
  imageUrl: string | null
  roomImageUrl: string | null
  roomUnits: number
  dwellerCapacity: number
  assignedDwellers: DwellerShort[]
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
const sceneSizeClass = computed(() => {
  if (props.roomUnits <= 1) return 'room-scene--compact'
  if (props.roomUnits <= 3) return 'room-scene--standard'
  if (props.roomUnits <= 6) return 'room-scene--wide'
  return 'room-scene--panoramic'
})
</script>

<template>
  <div class="section room-preview-section room-scene" :class="sceneSizeClass">
    <h3 class="section-title">
      <Icon icon="mdi:image-outline" class="h-5 w-5" />
      Room Preview
    </h3>
    <div class="preview-container">
      <div class="room-image-container">
        <img v-if="sceneImageUrl" :src="sceneImageUrl" :alt="roomName || 'Room'" class="room-image" />
        <div class="room-image-placeholder" :class="{ 'has-image': sceneImageUrl }">
          <template v-if="!sceneImageUrl">
            <Icon icon="mdi:home-variant-outline" class="h-16 w-16 opacity-30" />
            <p class="placeholder-text">Room Sprite</p>
            <p class="placeholder-subtext">No Image Available</p>
          </template>

          <div class="dweller-sprites-overlay">
            <div
              v-for="slot in dwellerCapacity"
              :key="`slot-${slot}`"
              class="dweller-sprite-slot"
              :class="{ 'slot-filled': workerDwellers[slot - 1] }"
            >
              <template v-if="workerDwellers[slot - 1]">
                <div class="scene-occupant">
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
              </template>
              <button
                v-else
                type="button"
                class="placeholder-dweller empty scene-empty-slot scene-empty-worker"
                aria-label="Assign worker"
                @click="emit('assignWorker')"
              >
                <Icon icon="mdi:account-outline" class="h-6 w-6 opacity-30" />
              </button>
            </div>
            <div v-if="showApprenticeSlot" class="dweller-sprite-slot apprentice-slot" :class="{ 'slot-filled': apprentice }">
              <template v-if="apprentice">
                <div class="scene-occupant">
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
                    <span class="apprentice-marker" :aria-label="`Apprentice training ${apprentice.apprentice_stat}`" role="img">
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
              </template>
              <button
                v-else
                type="button"
                class="placeholder-dweller empty scene-empty-slot scene-empty-apprentice"
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
  margin: 0;
  color: var(--color-theme-primary);
  font-size: 0.875rem;
  font-weight: 600;
  letter-spacing: 0.05em;
  text-transform: uppercase;
}

.section-title :deep(svg) {
  width: 0.875rem;
  height: 0.875rem;
}

.room-preview-section {
  padding: 0.5rem;
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  background: var(--color-surface);
}

.preview-container {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.room-image-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  overflow: hidden;
  border: 2px solid var(--color-theme-glow);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.8);
}

.room-scene--compact .room-image-container {
  min-height: 130px;
}

.room-scene--standard .room-image-container {
  min-height: 160px;
}

.room-scene--wide .room-image-container {
  min-height: 210px;
}

.room-scene--panoramic .room-image-container {
  min-height: 250px;
}

.room-image {
  display: block;
  width: 100%;
  height: auto;
  max-height: 260px;
  object-fit: contain;
  background: rgba(0, 0, 0, 0.8);
}

.room-image-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
  background: var(--color-surface-sunken);
}

.room-image-placeholder.has-image {
  background: transparent;
}

.placeholder-text {
  margin: 1rem 0 0.25rem;
  color: var(--color-theme-primary);
  font-size: 1.125rem;
  font-weight: 600;
  letter-spacing: 0.1em;
  text-transform: uppercase;
}

.placeholder-subtext {
  color: var(--color-gray-500);
  font-size: 0.875rem;
  font-style: italic;
}

.dweller-sprites-overlay {
  position: absolute;
  right: 0.5rem;
  bottom: 0.5rem;
  left: 0.5rem;
  z-index: 10;
  display: flex;
  justify-content: space-evenly;
}

.dweller-sprite-slot,
.scene-occupant {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.placeholder-dweller {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 48px;
  height: 48px;
  padding: 0;
  border: 2px dashed var(--color-theme-glow);
  border-radius: 8px;
  background: var(--color-surface-sunken);
}

.placeholder-dweller.empty {
  border-color: rgba(128, 128, 128, 0.2);
  background: rgba(128, 128, 128, 0.05);
}

.scene-empty-slot,
.scene-dweller {
  color: inherit;
  cursor: pointer;
}

.scene-empty-slot:hover,
.scene-empty-slot:focus-visible {
  border-color: var(--color-theme-primary);
  background: var(--color-surface-hover);
  outline: none;
}

.slot-filled .placeholder-dweller {
  border-style: solid;
  border-color: var(--color-theme-primary);
  background: var(--color-surface-raised);
}

.scene-dweller:hover,
.scene-dweller:focus-visible {
  box-shadow: 0 0 8px var(--color-theme-glow);
  outline: none;
}

.scene-unassign {
  position: absolute;
  top: -0.35rem;
  right: -0.35rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.35rem;
  height: 1.35rem;
  padding: 0;
  border: 1px solid var(--color-danger);
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

.scene-unassign:focus-visible,
.scene-unassign:hover {
  background: color-mix(in srgb, var(--color-danger) 15%, transparent);
  outline: none;
}

.scene-unassign :deep(svg) {
  width: 0.75rem;
  height: 0.75rem;
}

.scene-dweller :deep(.scene-dweller-portrait),
.scene-dweller :deep(.scene-dweller-icon) {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.scene-dweller :deep([role='img']) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
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
}
</style>
