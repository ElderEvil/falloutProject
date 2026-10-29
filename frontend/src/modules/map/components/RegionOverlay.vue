<script setup lang="ts">
import { onBeforeUnmount, ref, watch } from 'vue'
import { MAP_UNITS } from '../utils/atlasProjection'

const REGION_VARS = [
  '--color-region-green-belt',
  '--color-region-rust-basin',
  '--color-region-broken-highlands',
  '--color-region-mirelands',
] as const
const SUPERSAMPLE = 4

const props = defineProps<{
  regionMap: readonly number[]
  width: number
  height: number
  visible: boolean
}>()

const imageUrl = ref('')

function renderRegionLayer(): void {
  if (!props.visible || props.regionMap.length === 0) {
    imageUrl.value = ''
    return
  }
  const cells = document.createElement('canvas')
  cells.width = props.width
  cells.height = props.height
  const cellCtx = cells.getContext('2d')
  if (cellCtx === null) return
  const styles = getComputedStyle(document.documentElement)
  const colors = REGION_VARS.map((name) => styles.getPropertyValue(name).trim() || 'transparent')
  for (let index = 0; index < props.regionMap.length; index++) {
    cellCtx.fillStyle = colors[props.regionMap[index]] ?? 'transparent'
    cellCtx.fillRect(index % props.width, Math.floor(index / props.width), 1, 1)
  }

  const canvas = document.createElement('canvas')
  canvas.width = props.width * SUPERSAMPLE
  canvas.height = props.height * SUPERSAMPLE
  const ctx = canvas.getContext('2d')
  if (ctx === null) return
  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'
  ctx.drawImage(cells, 0, 0, canvas.width, canvas.height)
  imageUrl.value = canvas.toDataURL()
}

watch(
  [() => props.visible, () => props.regionMap, () => props.width, () => props.height],
  renderRegionLayer,
  { immediate: true },
)
onBeforeUnmount(() => {
  imageUrl.value = ''
})
</script>

<template>
  <g v-if="visible && imageUrl" class="region-overlay" aria-hidden="true" pointer-events="none">
    <image
      :href="imageUrl"
      x="0"
      y="0"
      :width="MAP_UNITS"
      :height="MAP_UNITS"
      preserveAspectRatio="none"
      opacity="0.22"
    />
  </g>
</template>
