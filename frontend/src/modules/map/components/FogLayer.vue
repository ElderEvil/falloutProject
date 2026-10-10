<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { ATLAS_TILES, MAP_UNITS } from '../utils/atlasProjection'

const props = withDefaults(defineProps<{ explored: Uint8Array; tiles?: number }>(), {
  tiles: ATLAS_TILES,
})

const imageUrl = ref('')

function renderFog(): void {
  const tiles = props.tiles
  if (props.explored.length !== tiles * tiles) {
    imageUrl.value = ''
    return
  }
  const canvas = document.createElement('canvas')
  canvas.width = tiles
  canvas.height = tiles
  const ctx = canvas.getContext('2d')
  if (ctx === null) {
    imageUrl.value = ''
    return
  }
  const fog = getComputedStyle(document.documentElement).getPropertyValue('--color-fog').trim()
  ctx.fillStyle = fog
  for (let i = 0; i < props.explored.length; i++) {
    if (props.explored[i] === 1) continue
    ctx.fillRect(i % tiles, Math.floor(i / tiles), 1, 1)
  }
  imageUrl.value = canvas.toDataURL()
}

watch(() => props.explored, renderFog, { immediate: true })
onBeforeUnmount(() => {
  imageUrl.value = ''
})
</script>

<template>
  <image
    v-if="imageUrl"
    :href="imageUrl"
    x="0"
    y="0"
    :width="MAP_UNITS"
    :height="MAP_UNITS"
    preserveAspectRatio="none"
    class="atlas-fog"
    aria-hidden="true"
  />
</template>

<style scoped>
.atlas-fog {
  image-rendering: pixelated;
}
</style>
