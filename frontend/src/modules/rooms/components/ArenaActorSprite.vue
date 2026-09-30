<script setup lang="ts">
import { computed } from 'vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { getStaticImageUrl } from '@/core/utils/image'
import type { components } from '@/core/types/api.generated'

type ArenaActor = components['schemas']['ArenaActor']
type ArenaActorLayer = components['schemas']['ArenaActorLayer']

interface Props {
  actor: ArenaActor | null
  portraitUrl?: string | null
  alt: string
}

const props = withDefaults(defineProps<Props>(), { portraitUrl: null })

const hasLayers = computed(() => Boolean(props.actor && props.actor.layers.length > 0))

// The sprite box keeps the actor canvas' intrinsic aspect ratio so layer
// percentages map 1:1 onto the rendered box.
const boxStyle = computed(() => {
  if (!props.actor) return {}
  return { aspectRatio: `${props.actor.canvas_width} / ${props.actor.canvas_height}` }
})

// Layers are anchored in the canvas' intrinsic pixel space; convert each to
// box percentages and sort by z so DOM order matches stacking order.
const layers = computed(() => {
  if (!props.actor) return []
  const { canvas_width, canvas_height } = props.actor
  return props.actor.layers
    .map((layer) => ({
      ...layer,
      src: getStaticImageUrl(layer.url) ?? '',
      style: {
        left: `${(layer.anchor_x / canvas_width) * 100}%`,
        top: `${(layer.anchor_y / canvas_height) * 100}%`,
        width: `${(layer.width / canvas_width) * 100}%`,
        height: `${(layer.height / canvas_height) * 100}%`,
        zIndex: layer.z,
      },
    }))
    .sort((a, b) => a.z - b.z)
})

// The variant is a full-canvas pose overlay with no geometry of its own: it
// sits one step above the base (lowest) layer and below any equipment layers.
const variant = computed(() => {
  if (!props.actor?.variant_url) return null
  const baseZ = Math.min(...props.actor.layers.map((layer) => layer.z))
  return {
    src: getStaticImageUrl(props.actor.variant_url) ?? '',
    zIndex: baseZ + 1,
  }
})
</script>

<template>
  <div
    v-if="hasLayers && actor"
    class="arena-actor-sprite actor-idle"
    :style="boxStyle"
    role="img"
    :aria-label="alt"
  >
    <img
      v-if="variant"
      :src="variant.src"
      :alt="`${alt} variant`"
      class="actor-layer actor-layer--variant"
      :style="{ zIndex: variant.zIndex }"
    />
    <img
      v-for="layer in layers"
      :key="`${layer.slot}-${layer.z}`"
      :src="layer.src"
      :alt="`${alt} ${layer.slot}`"
      class="actor-layer"
      :style="layer.style"
    />
  </div>
  <div v-else class="arena-actor-sprite arena-actor-sprite--fallback actor-idle">
    <DwellerPortrait
      :image-url="portraitUrl"
      :alt="alt"
      image-class="portrait-image"
      fallback-class="portrait-icon"
    />
  </div>
</template>

<style scoped>
.arena-actor-sprite {
  position: relative;
  width: 100%;
  aspect-ratio: 3 / 5;
  overflow: hidden;
}

.arena-actor-sprite--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
}

.portrait-image {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.portrait-icon {
  color: var(--color-theme-primary);
}

.actor-layer {
  position: absolute;
  object-fit: contain;
}

.actor-layer--variant {
  inset: 0;
  width: 100%;
  height: 100%;
}

.actor-idle {
  animation: actor-idle 3s ease-in-out infinite;
}

@keyframes actor-idle {
  0%,
  100% {
    translate: 0 0;
  }
  50% {
    translate: 0 -3px;
  }
}

@media (prefers-reduced-motion: reduce) {
  .actor-idle {
    animation: none;
  }
}
</style>