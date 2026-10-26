<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import CombatPet from '@/modules/combat/components/CombatPet.vue'
import type { components } from '@/core/types/api.generated'
import { useFallbackImage } from '@/modules/rooms/composables/useFallbackImage'
import {
  WASTELAND_SCENES,
  widestSceneImage,
  type WastelandSceneId,
  type WastelandSceneRole,
} from '../models/wastelandScenes'

const props = withDefaults(
  defineProps<{
    scene?: WastelandSceneId | null
    variant?: WastelandSceneRole
    heading: string
    description?: string
    dwellerName?: string
    imageUrl?: string | null
    thumbnailUrl?: string | null
    compact?: boolean
    pet?: components['schemas']['CombatPet'] | null
  }>(),
  {
    variant: 'landscape',
    description: '',
    dwellerName: '',
    imageUrl: null,
    thumbnailUrl: null,
    compact: false,
    scene: null,
  }
)

const artwork = computed(() => (props.scene ? WASTELAND_SCENES[props.scene] : null))
const variants = computed(() => artwork.value?.[props.variant].variants ?? [])
const fullImage = computed(() => widestSceneImage(variants.value))
const srcset = computed(() =>
  variants.value.map((image) => `${image.src} ${image.width}w`).join(', ')
)
const { url: sceneImage, onError: imageFailed } = useFallbackImage(() => [fullImage.value?.src])
</script>

<template>
  <figure
    class="overflow-hidden rounded-lg border border-theme-primary/30 bg-surface-sunken"
    :aria-label="heading"
  >
    <div
      class="relative overflow-hidden bg-surface-sunken"
      :class="variant === 'battleback' ? 'aspect-[50/37]' : 'aspect-video'"
    >
      <img
        v-if="fullImage && sceneImage"
        :src="sceneImage"
        :srcset="srcset"
        :sizes="
          compact
            ? '(max-width: 640px) calc(100vw - 64px), 600px'
            : '(max-width: 768px) calc(100vw - 32px), 960px'
        "
        :width="fullImage.width"
        :height="fullImage.height"
        :alt="artwork?.label ?? heading"
        class="absolute inset-0 h-full w-full object-contain"
        decoding="async"
        @error="imageFailed"
      />
      <div
        v-else
        class="absolute inset-0 flex items-center justify-center text-theme-primary/60"
        role="img"
        :aria-label="artwork?.label ?? heading"
      >
        <Icon icon="mdi:compass-outline" class="h-12 w-12" />
      </div>
      <div
        v-if="dwellerName"
        class="actor-ground-shadow absolute bottom-[8%] left-1/2 h-[44%] aspect-[1/2] -translate-x-1/2"
        :aria-label="`${dwellerName} on expedition`"
        role="group"
      >
        <DwellerPortrait
          :image-url="imageUrl"
          :thumbnail-url="thumbnailUrl"
          :alt="dwellerName"
          prefer-thumbnail
          :zoom="false"
          class="block h-full w-full drop-shadow-[0_4px_3px_rgba(0,0,0,0.6)]"
          image-class="h-full w-full object-contain"
          fallback-class="h-full w-full text-theme-primary"
          fallback-icon="mdi:account"
        />
        <CombatPet v-if="pet" :pet="pet" :owner-name="dwellerName" facing="right" />
      </div>
    </div>
    <figcaption
      class="flex items-start gap-3 border-t border-theme-primary/20 bg-surface-sunken px-4 py-3"
    >
      <Icon icon="mdi:compass-outline" class="mt-0.5 h-4 w-4 shrink-0 text-theme-primary" />
      <div class="min-w-0">
        <p class="text-sm font-semibold text-theme-primary">{{ heading }}</p>
        <p v-if="description" class="mt-1 text-xs leading-relaxed text-theme-primary/80">
          {{ description }}
        </p>
      </div>
    </figcaption>
  </figure>
</template>
