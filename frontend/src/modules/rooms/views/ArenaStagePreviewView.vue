<script setup lang="ts">
// TEMPORARY PoC preview view (issues 818 and 819) — dev-only, delete after review.
// Compares image models (gpt-image-1 / gpt-image-2 / gpt-image-2.5 / a
// style-matched 2.5) and actor poses without a backend or auth.
import { computed, ref } from 'vue'
import ArenaActorStage, { type StageActor } from '@/modules/rooms/components/ArenaActorStage.vue'
import { getStaticImageUrl } from '@/core/utils/image'

type Version = 'v1' | 'v2' | 'v2.5' | 'v2.5-match'
const VERSIONS: Version[] = ['v1', 'v2', 'v2.5', 'v2.5-match']

const SCENES: Record<Version, string> = {
  v1: '/static/room_images/arena_empty_poc.png',
  v2: '/static/poc_v2/arena_empty.png',
  'v2.5': '/static/poc_v25/arena_empty.png',
  'v2.5-match': '/static/poc_v25match/arena_stylematch.png',
}

// v1/v2 share the gpt-image-1 equipment layers; v2 has no transparent actor art
// (the model rejects transparent backgrounds), so it reuses the v1 body.
const V1_BASE = '/static/actor_poc/actor_base_vault_suit.png'
const V1_LAYERS = {
  outfit: '/static/actor_poc/outfit_layer_overcoat.png',
  weapon: '/static/actor_poc/weapon_layer_rifle.png',
}
const V25_LAYERS = {
  outfit: '/static/poc_v25/outfit_layer_overcoat.png',
  weapon: '/static/poc_v25/weapon_layer_rifle.png',
}

const POSES = ['pose_idle', 'pose_guard', 'pose_ready', 'pose_relaxed'] as const
type Pose = (typeof POSES)[number]

const version = ref<Version>('v2.5-match')
const pose = ref<Pose>('pose_guard')
const dressed = ref(false)

const sceneUrl = computed(() => getStaticImageUrl(SCENES[version.value]))
const baseUrl = computed(() => {
  if (version.value === 'v1' || version.value === 'v2') return getStaticImageUrl(V1_BASE)
  if (version.value === 'v2.5-match') return getStaticImageUrl('/static/poc_v25match/actor_stylematch.png')
  return getStaticImageUrl(`/static/poc_v25/${pose.value}.png`)
})
const layers = computed(() => (version.value === 'v1' || version.value === 'v2' ? V1_LAYERS : V25_LAYERS))

const actors = computed<StageActor[]>(() => [
  {
    id: 'poc-a',
    name: 'Overseer',
    portraitUrl: baseUrl.value,
    outfitUrl: dressed.value ? getStaticImageUrl(layers.value.outfit) : null,
    weaponUrl: dressed.value ? getStaticImageUrl(layers.value.weapon) : null,
  },
  {
    id: 'poc-b',
    name: 'Vault Dweller',
    portraitUrl: baseUrl.value,
    outfitUrl: null,
    weaponUrl: null,
  },
])
</script>

<template>
  <main class="poc-page">
    <h1 class="poc-title">Arena Actor Stage — PoC (818 / 819)</h1>
    <p class="poc-subtitle">
      Art set: {{ version }}
      <template v-if="version === 'v2'"> (no transparency in gpt-image-2; reuses v1 body)</template>
      <template v-if="version === 'v2.5'"> · pose: {{ pose }}</template>
    </p>

    <div class="poc-controls">
      <div class="poc-group" role="group" aria-label="Art model version">
        <button
          v-for="option in VERSIONS"
          :key="option"
          type="button"
          class="poc-button"
          :class="{ 'poc-button--active': version === option }"
          @click="version = option"
        >
          {{ option }}
        </button>
      </div>
      <div v-if="version === 'v2.5'" class="poc-group" role="group" aria-label="Actor pose">
        <button
          v-for="option in POSES"
          :key="option"
          type="button"
          class="poc-button"
          :class="{ 'poc-button--active': pose === option }"
          @click="pose = option"
        >
          {{ option.replace('pose_', '') }}
        </button>
      </div>
      <div class="poc-group">
        <button type="button" class="poc-button" :class="{ 'poc-button--active': dressed }" @click="dressed = !dressed">
          {{ dressed ? 'Remove equipment' : 'Equip overcoat + rifle' }}
        </button>
      </div>
    </div>

    <div class="poc-stage-wrap">
      <ArenaActorStage :key="`${version}-${pose}`" :scene-url="sceneUrl" :actors="actors" />
    </div>
  </main>
</template>

<style scoped>
.poc-page {
  min-height: 100vh;
  padding: 1.5rem;
  background: var(--color-surface-dark);
  color: var(--color-theme-primary);
}
.poc-title {
  font-size: 1rem;
  font-weight: 700;
  letter-spacing: 0.08em;
  text-transform: uppercase;
}
.poc-subtitle {
  margin-top: 0.25rem;
  font-size: 0.75rem;
  color: var(--color-gray-400);
}
.poc-controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem;
}
.poc-group {
  display: flex;
  gap: 0.35rem;
  margin: 0.75rem 0;
}
.poc-button {
  padding: 0.4rem 0.8rem;
  border: 1px solid var(--color-theme-primary);
  border-radius: 4px;
  background: transparent;
  color: var(--color-theme-primary);
  font-size: 0.75rem;
  cursor: pointer;
}
.poc-button--active {
  background: color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
}
.poc-stage-wrap {
  max-width: 960px;
}
</style>
