<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { ARENA_SCENE_POC, anchorToPercent } from '../models/arenaScenePoc'

export interface StageActor {
  id: string
  name: string
  portraitUrl: string | null
  outfitUrl: string | null
  weaponUrl: string | null
}

interface Props {
  sceneUrl: string | null
  sceneFallbackUrl?: string | null
  actors: StageActor[]
}

const props = withDefaults(defineProps<Props>(), { sceneFallbackUrl: null })

const sceneImageUrl = computed(() => props.sceneUrl ?? props.sceneFallbackUrl)

// Stage renders at the scene's intrinsic aspect ratio, derived from the PoC
// descriptor so the manifest stays the single source of truth.
const stageStyle = computed(() => ({
  aspectRatio: `${ARENA_SCENE_POC.intrinsicWidth} / ${ARENA_SCENE_POC.intrinsicHeight}`,
}))

const anchors = computed(() =>
  ARENA_SCENE_POC.anchors.map((anchor, index) => ({
    ...anchor,
    position: anchorToPercent(anchor),
    actor: props.actors[index] ?? null,
  }))
)

// Per-layer anchor: the weapon is positioned at the hand rather than stretched
// across the whole actor box, so it reads as held instead of a waist overlay.
const weaponStyle = computed(() => ({
  width: `${ARENA_SCENE_POC.weaponLayer.widthPercent}%`,
  right: `${ARENA_SCENE_POC.weaponLayer.rightPercent}%`,
  bottom: `${ARENA_SCENE_POC.weaponLayer.bottomPercent}%`,
}))
</script>

<template>
  <section class="arena-actor-stage" :style="stageStyle" aria-label="Arena scene stage">
    <img v-if="sceneImageUrl" :src="sceneImageUrl" alt="Arena" class="stage-scene" />
    <div v-else class="stage-placeholder">
      <Icon icon="mdi:home-variant-outline" class="h-16 w-16 opacity-30" />
      <p class="placeholder-text">Room Sprite</p>
      <p class="placeholder-subtext">No Image Available</p>
    </div>

    <div
      v-for="anchor in anchors"
      :key="anchor.id"
      class="actor-wrapper actor-idle"
      :style="{
        left: anchor.position.left,
        top: anchor.position.top,
        width: `${ARENA_SCENE_POC.actorWidthPercent}%`,
      }"
    >
      <template v-if="anchor.actor && anchor.actor.portraitUrl">
        <DwellerPortrait
          :thumbnail-url="anchor.actor.portraitUrl"
          :alt="anchor.actor.name"
          image-class="actor-layer actor-layer--base"
          fallback-class="actor-layer actor-layer--base actor-layer--fallback"
          prefer-thumbnail
        />
        <img
          v-if="anchor.actor.outfitUrl"
          :src="anchor.actor.outfitUrl"
          :alt="`${anchor.actor.name} outfit`"
          class="actor-layer actor-layer--outfit"
        />
          <img
            v-if="anchor.actor.weaponUrl"
            :src="anchor.actor.weaponUrl"
            :alt="`${anchor.actor.name} weapon`"
            class="actor-layer actor-layer--weapon"
            :style="weaponStyle"
          />
      </template>
      <div v-else-if="anchor.actor" class="actor-no-portrait" role="img" :aria-label="anchor.actor.name">
        <Icon icon="mdi:account-outline" class="h-6 w-6" />
      </div>
      <div v-else class="actor-missing" role="img" aria-label="No dweller assigned">
        <Icon icon="mdi:account-outline" class="h-6 w-6 opacity-30" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.arena-actor-stage {
  position: relative;
  width: 100%;
  overflow: hidden;
  border: 1px solid var(--color-theme-glow);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.8);
}

.stage-scene {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.stage-placeholder {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 1.25rem;
  background: var(--color-surface-sunken);
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

.actor-wrapper {
  position: absolute;
  aspect-ratio: 3 / 5;
  transform: translate(-50%, -100%);
}

.actor-idle {
  animation: actor-idle 3s ease-in-out infinite;
}

.actor-layer {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.actor-layer--base {
  z-index: 10;
}

.actor-layer--outfit {
  z-index: 20;
}

.actor-layer--weapon {
  inset: auto;
  height: auto;
  z-index: 30;
}

.actor-layer--fallback {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--color-theme-primary);
}

.actor-missing {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  border: 2px dashed color-mix(in srgb, var(--color-gray-500) 20%, transparent);
  border-radius: 8px;
  background: color-mix(in srgb, var(--color-gray-500) 5%, transparent);
  color: var(--color-gray-500);
}

.actor-no-portrait {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
  border: 2px dashed color-mix(in srgb, var(--color-theme-primary) 40%, transparent);
  border-radius: 8px;
  background: rgba(0, 0, 0, 0.45);
  color: var(--color-theme-primary);
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