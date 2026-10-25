<script setup lang="ts">
import { computed, ref } from 'vue'
import { Icon } from '@iconify/vue'
import { PersonStanding } from '@lucide/vue'
import {
  getAbilityConfig,
  getDwellerPortraitScale,
  isApprentice,
  orderRoomDwellers,
  type DwellerShort,
} from '@/modules/dwellers/models/dweller'
import { getRoomImageUrl, getStaticImageUrl } from '@/core/utils/image'
import DwellerNameBadge from '@/modules/dwellers/components/DwellerNameBadge.vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { useFallbackImage } from '../composables/useFallbackImage'
import { RESPONSE_DETAIL_SCENES } from '../models/roomScenes'
import type { RoomStyleValue } from '../models/room'
import RoomThemeSelector from './RoomThemeSelector.vue'

interface Props {
  roomName: string
  imageUrl: string | null
  roomImageUrl: string | null
  roomUnits?: number
  dwellerCapacity: number
  assignedDwellers: DwellerShort[]
  showApprenticeSlot?: boolean
  assignEnabled?: boolean
  roomStyle?: RoomStyleValue | null
  availableThemes?: RoomStyleValue[]
  roomTier?: number
  isApplyingStyle?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  showApprenticeSlot: false,
  roomUnits: 3,
  assignEnabled: true,
  availableThemes: () => [],
  roomTier: 1,
})
const emit = defineEmits<{
  activate: [dwellerId: string]
  unassign: [dwellerId: string]
  assignWorker: []
  assignApprentice: []
  applyStyle: [style: RoomStyleValue]
}>()

const { url: sceneImageUrl, onError: imageFailed } = useFallbackImage(() => [
  props.roomImageUrl,
  getRoomImageUrl(props.imageUrl),
])
const sceneSizeClass = computed(() => {
  if (props.roomUnits <= 1) return 'room-scene--compact'
  if (props.roomUnits <= 3) return 'room-scene--small'
  if (props.roomUnits >= 6) {
    // The size-6 Response Station bay ships as a 2:1 scene while the wide frame is
    // 3:1, so cropping to the frame would cut off its floor and equipment. Let that
    // scene set its own frame height instead of cropping it.
    return props.roomImageUrl === RESPONSE_DETAIL_SCENES[6]
      ? 'room-scene--wide-native'
      : 'room-scene--wide'
  }
  return null
})
const orderedDwellers = computed(() => orderRoomDwellers(props.assignedDwellers))
const workerDwellers = computed(() =>
  orderedDwellers.value.filter((dweller) => !isApprentice(dweller))
)
const apprentice = computed(() => orderedDwellers.value.find(isApprentice))
const apprenticeStatLabel = computed(
  () =>
    getAbilityConfig(apprentice.value?.apprentice_stat)?.letter ??
    apprentice.value?.apprentice_stat?.charAt(0).toUpperCase() ??
    ''
)
const emptyDwellerSilhouetteUrl = getStaticImageUrl(
  '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp'
)
const emptyApprenticeSilhouetteUrl = getStaticImageUrl(
  '/static/dweller_images/variants/teen/FOS_Dw_Default_Human_Teen_Male_SkinBrown_HairBrown.webp'
)
const dwellerName = (dweller: DwellerShort) =>
  `${dweller.first_name} ${dweller.last_name ?? ''}`.trim()
const imageAspect = ref(1.53)

function rememberImageAspect(event: Event) {
  const image = event.target as HTMLImageElement
  if (image.naturalWidth > 0 && image.naturalHeight > 0) {
    imageAspect.value = image.naturalWidth / image.naturalHeight
  }
}
</script>

<template>
  <section
    class="section room-preview-section room-scene"
    :class="sceneSizeClass"
    :aria-label="`${roomName} room preview`"
  >
    <div class="preview-header">
      <h3 class="section-title">
        <Icon icon="mdi:image-outline" class="h-5 w-5" />
        Room Preview
      </h3>
      <RoomThemeSelector
        v-if="roomStyle"
        :model-value="roomStyle"
        :themes="availableThemes"
        :tier="roomTier"
        :disabled="isApplyingStyle"
        @update:model-value="emit('applyStyle', $event)"
      />
    </div>
    <div class="preview-container">
      <div class="room-image-container">
        <div
          class="room-image-frame"
          :class="{ 'has-image': sceneImageUrl }"
          :style="{ '--room-image-aspect': imageAspect }"
        >
          <img
            v-if="sceneImageUrl"
            :src="sceneImageUrl"
            :alt="roomName || 'Room'"
            class="room-image"
            @load="rememberImageAspect"
            @error="imageFailed"
          />
          <div class="room-image-placeholder" :class="{ 'has-image': sceneImageUrl }">
            <template v-if="!sceneImageUrl">
              <Icon icon="mdi:home-variant-outline" class="h-16 w-16 opacity-30" />
              <p class="placeholder-text">Room Sprite</p>
              <p class="placeholder-subtext">No Image Available</p>
            </template>

            <div
              class="dweller-sprites-overlay"
              :style="{
                '--dweller-silhouette': emptyDwellerSilhouetteUrl
                  ? `url('${emptyDwellerSilhouetteUrl}')`
                  : 'none',
              }"
            >
              <slot name="occupants">
                <div
                  v-for="slot in dwellerCapacity"
                  :key="`slot-${slot}`"
                  class="dweller-sprite-slot dweller-sprite-slot-lg"
                  :class="{ 'slot-filled': workerDwellers[slot - 1] }"
                >
                  <template v-if="workerDwellers[slot - 1]">
                    <div class="scene-occupant">
                      <DwellerNameBadge
                        :name="workerDwellers[slot - 1]!.first_name"
                        :full-name="dwellerName(workerDwellers[slot - 1]!)"
                      />
                      <button
                        type="button"
                        class="placeholder-dweller scene-dweller"
                        :style="{
                          '--dweller-body-scale': getDwellerPortraitScale(
                            workerDwellers[slot - 1]!
                          ),
                        }"
                        :aria-label="`Open ${workerDwellers[slot - 1]?.first_name} ${workerDwellers[slot - 1]?.last_name ?? ''}`"
                        @click="emit('activate', workerDwellers[slot - 1]!.id)"
                      >
                        <DwellerPortrait
                          :thumbnail-url="workerDwellers[slot - 1]?.thumbnail_url"
                          :alt="`${workerDwellers[slot - 1]?.first_name} ${workerDwellers[slot - 1]?.last_name ?? ''}`"
                          image-class="scene-dweller-portrait h-full w-full"
                          prefer-thumbnail
                          :zoom="false"
                        >
                          <template #fallback>
                            <PersonStanding
                              class="scene-dweller-icon text-theme-primary"
                              aria-hidden="true"
                            />
                          </template>
                        </DwellerPortrait>
                      </button>
                      <button
                        v-if="assignEnabled"
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
                    v-else-if="assignEnabled"
                    type="button"
                    class="placeholder-dweller empty scene-empty-slot scene-empty-worker"
                    aria-label="Assign worker"
                    @click="emit('assignWorker')"
                  >
                    <span class="empty-dweller-silhouette" aria-hidden="true" />
                    <span class="empty-dweller-plus" aria-hidden="true">
                      <Icon icon="mdi:plus" />
                    </span>
                  </button>
                  <div v-else class="placeholder-dweller empty scene-empty-slot" aria-hidden="true">
                    <span class="empty-dweller-silhouette" aria-hidden="true" />
                  </div>
                </div>
                <div
                  v-if="showApprenticeSlot"
                  class="dweller-sprite-slot dweller-sprite-slot-lg apprentice-slot"
                  :class="{ 'slot-filled': apprentice }"
                >
                  <template v-if="apprentice">
                    <div class="scene-occupant">
                      <DwellerNameBadge
                        :name="apprentice.first_name"
                        :full-name="dwellerName(apprentice)"
                      />
                      <button
                        type="button"
                        class="placeholder-dweller scene-dweller"
                        :style="{ '--dweller-body-scale': getDwellerPortraitScale(apprentice) }"
                        :aria-label="`Open ${apprentice.first_name} ${apprentice.last_name ?? ''}`"
                        @click="emit('activate', apprentice.id)"
                      >
                        <DwellerPortrait
                          :thumbnail-url="apprentice.thumbnail_url"
                          :alt="`${apprentice.first_name} ${apprentice.last_name ?? ''}`"
                          image-class="scene-dweller-portrait h-full w-full"
                          prefer-thumbnail
                          :zoom="false"
                        >
                          <template #fallback>
                            <PersonStanding
                              class="scene-dweller-icon text-theme-primary"
                              aria-hidden="true"
                            />
                          </template>
                        </DwellerPortrait>
                        <span
                          class="apprentice-marker"
                          :aria-label="`Apprentice training ${apprentice.apprentice_stat}`"
                          role="img"
                        >
                          <Icon icon="mdi:school-outline" />
                          {{ apprenticeStatLabel }}
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
                    <span
                      class="empty-dweller-silhouette empty-dweller-silhouette--apprentice"
                      :style="{
                        '--dweller-silhouette': emptyApprenticeSilhouetteUrl
                          ? `url('${emptyApprenticeSilhouetteUrl}')`
                          : 'none',
                      }"
                      aria-hidden="true"
                    />
                    <span class="apprentice-marker" aria-label="Apprentice slot" role="img">
                      <Icon icon="mdi:school-outline" />+
                    </span>
                  </button>
                </div>
              </slot>
            </div>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<style scoped>
.section {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.preview-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-wrap: wrap;
  gap: 0.75rem;
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
  min-width: 0;
}

.preview-container {
  width: 100%;
}

.room-image-container {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 180px;
  overflow: hidden;
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.8);
}

.room-image-frame {
  position: relative;
  display: flex;
  width: min(100%, calc(260px * var(--room-image-aspect, 1.53)));
  aspect-ratio: var(--room-image-aspect, 1.53);
  margin: 0 auto;
  overflow: hidden;
  /* Dweller sprites size against this frame, so a taller wide scene keeps the
     same occupant-to-room proportion as a standard preview. */
  container-type: size;
}

.room-image-frame:not(.has-image) {
  width: 100%;
  height: 180px;
  aspect-ratio: auto;
}

.room-scene--compact .room-image-frame:not(.has-image) {
  height: 130px;
}

.room-scene--wide .room-image-frame {
  width: 100%;
  aspect-ratio: 3 / 1;
}

.room-scene--wide-native .room-image-frame {
  width: 100%;
  aspect-ratio: 2 / 1;
}

.room-scene--compact .room-image-container {
  min-height: 130px;
}

.room-scene--small .dweller-sprites-overlay {
  right: 0.25rem;
  left: 0.25rem;
  justify-content: space-evenly;
  gap: 0;
}

.room-scene--wide .room-image-container {
  min-height: 0;
  aspect-ratio: 3 / 1;
}

.room-scene--wide .room-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  max-height: none;
  object-fit: cover;
}

/* A wide scene that is not 3:1 (the 2:1 size-6 Response Station bay) sets its own
   frame height and is contained, so its floor and equipment stay inside the frame. */
.room-scene--wide-native .room-image-container {
  min-height: 0;
  aspect-ratio: 2 / 1;
}

.room-scene--wide-native .room-image {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  max-height: none;
  object-fit: contain;
}

.room-image {
  position: absolute;
  inset: 0;
  display: block;
  width: 100%;
  height: 100%;
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
  bottom: calc(0.5rem + 7%);
  left: 0.5rem;
  z-index: 10;
  display: flex;
  align-items: flex-end;
  justify-content: space-evenly;
  /* 10px at the standard 260px frame; scales up with taller wide scenes. */
  --dweller-name-size: clamp(0.625rem, 3.85cqh, 1rem);
}

.dweller-sprite-slot,
.scene-occupant {
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.dweller-sprite-slot {
  align-items: flex-end;
}

.scene-occupant {
  flex-direction: column;
  justify-content: flex-end;
  width: 29.8cqh;
  gap: 0.1rem;
}

/* Keep worker and apprentice portraits the same size. */
.dweller-sprite-slot-lg .placeholder-dweller {
  width: 29.8cqh;
  height: calc(44.6cqh * var(--dweller-body-scale, 1));
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
  border-color: transparent;
  background: transparent;
}

.scene-empty-slot,
.scene-dweller {
  color: inherit;
  cursor: pointer;
}

.scene-empty-slot:hover,
.scene-empty-slot:focus-visible {
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 3px;
}

.scene-empty-slot:hover .empty-dweller-silhouette,
.scene-empty-slot:focus-visible .empty-dweller-silhouette {
  background-color: var(--color-theme-primary);
  opacity: 1;
  filter: drop-shadow(0 0 9px color-mix(in srgb, var(--color-theme-primary) 65%, transparent));
}

.slot-filled .placeholder-dweller {
  border-style: solid;
  border-color: var(--color-theme-primary);
  background: var(--color-surface-raised);
}

.slot-filled .placeholder-dweller.scene-dweller {
  border: 0;
  background: transparent;
}

.scene-dweller:hover,
.scene-dweller:focus-visible {
  box-shadow: 0 0 8px var(--color-theme-glow);
  outline: none;
}

.scene-unassign {
  position: absolute;
  right: -0.45rem;
  bottom: -0.4rem;
  z-index: 3;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.75rem;
  height: 1.75rem;
  padding: 0;
  border: 1px solid color-mix(in srgb, var(--color-danger) 70%, transparent);
  border-radius: 5px;
  background: color-mix(in srgb, var(--color-surface-sunken) 92%, black);
  color: var(--color-danger);
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--color-danger) 18%, transparent),
    0 2px 8px rgb(0 0 0 / 0.65);
  cursor: pointer;
  opacity: 0;
  pointer-events: none;
  transition:
    opacity 150ms ease,
    background 150ms ease,
    border-color 150ms ease,
    box-shadow 150ms ease;
}

.scene-occupant:hover .scene-unassign,
.scene-unassign:focus-visible {
  opacity: 1;
  pointer-events: auto;
}

@media (hover: none) {
  .scene-unassign {
    opacity: 1;
    pointer-events: auto;
  }
}

.scene-unassign:focus-visible,
.scene-unassign:hover {
  border-color: var(--color-danger);
  background: color-mix(in srgb, var(--color-danger) 18%, var(--color-surface-sunken));
  box-shadow:
    0 0 0 1px color-mix(in srgb, var(--color-danger) 45%, transparent),
    0 0 10px color-mix(in srgb, var(--color-danger) 45%, transparent);
  outline: 2px solid var(--color-theme-primary);
  outline-offset: 2px;
}

.scene-unassign :deep(svg) {
  width: 0.875rem;
  height: 0.875rem;
}

.scene-dweller :deep(.scene-dweller-portrait),
.scene-dweller :deep(.scene-dweller-icon) {
  width: 100%;
  height: 100%;
}

:deep(.empty-dweller-silhouette) {
  display: block;
  width: 100%;
  height: 100%;
  background-color: var(--color-surface-sunken);
  -webkit-mask-image: var(--dweller-silhouette);
  mask-image: var(--dweller-silhouette);
  -webkit-mask-repeat: no-repeat;
  mask-repeat: no-repeat;
  -webkit-mask-position: center bottom;
  mask-position: center bottom;
  -webkit-mask-size: contain;
  mask-size: contain;
  -webkit-mask-mode: alpha;
  mask-mode: alpha;
  opacity: 0.78;
  filter: drop-shadow(0 0 4px color-mix(in srgb, var(--color-theme-primary) 30%, transparent));
  transition:
    background-color 150ms ease,
    opacity 150ms ease,
    filter 150ms ease;
}

.empty-dweller-silhouette--apprentice {
  opacity: 0.82;
  filter: drop-shadow(0 0 5px color-mix(in srgb, var(--badge-age-teen) 35%, transparent));
}

.scene-empty-apprentice:hover .empty-dweller-silhouette,
.scene-empty-apprentice:focus-visible .empty-dweller-silhouette {
  background-color: var(--badge-age-teen);
  opacity: 1;
  filter: drop-shadow(0 0 10px color-mix(in srgb, var(--badge-age-teen) 70%, transparent));
}

.empty-dweller-plus {
  position: absolute;
  right: 0.1rem;
  bottom: 0.1rem;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.15rem;
  height: 1.15rem;
  border: 1px solid var(--color-theme-primary);
  border-radius: 999px;
  background: var(--color-surface-sunken);
  color: var(--color-theme-primary);
  line-height: 0;
  pointer-events: none;
}

.empty-dweller-plus :deep(svg) {
  width: 0.7rem;
  height: 0.7rem;
}

.scene-dweller :deep(.scene-dweller-portrait) {
  width: 100%;
  height: 100%;
  max-width: 100%;
  object-fit: contain;
  object-position: center bottom;
}

.scene-dweller :deep([role='img']) {
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.apprentice-slot .placeholder-dweller,
.apprentice-slot .slot-filled .placeholder-dweller.scene-dweller {
  border: 0;
  background: transparent;
  box-shadow: none;
}

.apprentice-marker :deep(svg) {
  width: 0.75rem;
  height: 0.75rem;
}

.apprentice-marker {
  position: absolute;
  top: -0.35rem;
  right: -0.35rem;
  display: inline-flex;
  align-items: center;
  gap: 0.1rem;
  padding: 0.1rem 0.2rem;
  border: 1px solid var(--badge-age-teen);
  border-radius: 999px;
  background: var(--color-surface-sunken);
  color: var(--badge-age-teen);
  font-size: 0.625rem;
  font-weight: 700;
}
</style>
