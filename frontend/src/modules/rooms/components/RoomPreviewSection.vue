<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import {
  isApprentice,
  orderRoomDwellers,
  type DwellerShort,
} from '@/modules/dwellers/models/dweller'
import { getRoomImageUrl, getStaticImageUrl } from '@/core/utils/image'
import { useFallbackImage } from '../composables/useFallbackImage'
import { RESPONSE_DETAIL_SCENES } from '../models/roomScenes'
import type { RoomStyleValue } from '../models/room'
import RoomThemeSelector from './RoomThemeSelector.vue'
import RoomDwellerSlot from './RoomDwellerSlot.vue'

interface Props {
  roomName: string
  imageUrl: string | null
  roomImageUrl: string | null
  roomUnits?: number
  dwellerCapacity: number
  assignedDwellers: DwellerShort[]
  showApprenticeSlot?: boolean
  clientSlot?: DwellerShort | null
  selectionMode?: boolean
  slotIdPrefix?: string
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
  assignClient: []
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
const emptyDwellerSilhouetteUrl = getStaticImageUrl(
  '/static/dweller_images/base/FOS_Dw_Default_Human_Male.webp'
)
const imageAspect = ref(1.53)
// Hold the sprite overlay until the real image aspect is known; rendering at
// the 1.53 placeholder height first made every sprite snap smaller once the
// room image loaded. Reopening a room reuses the measured aspect so the
// preview is stable immediately.
const imageAspects = new Map<string, number>()
const imageReady = ref(false)
const previewReady = computed(() => !sceneImageUrl.value || imageReady.value)
const sceneImage = ref<HTMLImageElement | null>(null)

function primeImage(url = sceneImageUrl.value) {
  const cachedAspect = url ? imageAspects.get(url) : undefined
  imageAspect.value = cachedAspect ?? 1.53
  imageReady.value = !url || cachedAspect !== undefined
}

primeImage()
watch(sceneImageUrl, (url) => primeImage(url))

function applyImageAspect(image: HTMLImageElement) {
  if (image.naturalWidth > 0 && image.naturalHeight > 0) {
    const aspect = image.naturalWidth / image.naturalHeight
    imageAspect.value = aspect
    if (sceneImageUrl.value) imageAspects.set(sceneImageUrl.value, aspect)
  }
  imageReady.value = true
}

function rememberImageAspect(event: Event) {
  applyImageAspect(event.target as HTMLImageElement)
}

onMounted(() => {
  const image = sceneImage.value
  // Cached images can finish before the load listener is attached.
  if (image?.complete && image.naturalWidth > 0) applyImageAspect(image)
})
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
          :class="{ 'has-image': imageReady }"
          :style="{ '--room-image-aspect': imageAspect }"
        >
          <img
            v-if="sceneImageUrl"
            v-show="imageReady"
            ref="sceneImage"
            :src="sceneImageUrl"
            :alt="roomName || 'Room'"
            class="room-image"
            @load="rememberImageAspect"
            @error="imageFailed"
          />
          <div class="room-image-placeholder" :class="{ 'has-image': imageReady }">
            <template v-if="!sceneImageUrl">
              <Icon icon="mdi:home-variant-outline" class="h-16 w-16 opacity-30" />
              <p class="placeholder-text">Room Sprite</p>
              <p class="placeholder-subtext">No Image Available</p>
            </template>

            <div
              v-if="previewReady"
              class="dweller-sprites-overlay"
              :style="{
                '--dweller-silhouette': emptyDwellerSilhouetteUrl
                  ? `url('${emptyDwellerSilhouetteUrl}')`
                  : 'none',
              }"
            >
              <RoomDwellerSlot
                v-for="slot in dwellerCapacity"
                :key="`worker-${slot}`"
                :dweller="workerDwellers[slot - 1] ?? null"
                :assign-enabled="assignEnabled"
                :selection-mode="selectionMode"
                :room-name="roomName"
                :slot-id="slotIdPrefix ? `${slotIdPrefix}-worker-${slot}` : undefined"
                @activate="emit('activate', $event)"
                @unassign="emit('unassign', $event)"
                @assign="emit('assignWorker')"
              />
              <RoomDwellerSlot
                v-if="showApprenticeSlot"
                kind="apprentice"
                :dweller="apprentice ?? null"
                :assign-enabled="assignEnabled"
                @activate="emit('activate', $event)"
                @unassign="emit('unassign', $event)"
                @assign="emit('assignApprentice')"
              />
              <RoomDwellerSlot
                v-if="clientSlot !== undefined"
                kind="client"
                :dweller="clientSlot"
                :assign-enabled="assignEnabled"
                :selection-mode="selectionMode"
                :room-name="roomName"
                :slot-id="slotIdPrefix ? `${slotIdPrefix}-client` : undefined"
                @activate="emit('activate', $event)"
                @unassign="emit('unassign', $event)"
                @assign="emit('assignClient')"
              />
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
  /* Dweller slots size from this frame's height, so a taller wide scene keeps
     the same occupant-to-room proportion as a standard preview. Percentages
     keep it layout-driven: Firefox resolves container-query height units
     against the viewport until the frame is laid out, which flashed oversized
     sprites when the modal opened. */
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
  height: 44.6%;
  align-items: flex-end;
  justify-content: space-evenly;
}
</style>
