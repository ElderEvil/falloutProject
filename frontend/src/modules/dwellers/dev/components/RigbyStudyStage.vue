<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watchEffect } from 'vue'
import {
  Pose,
  WebGLRenderer,
  parseAtlas,
  readSkeletonJson,
  writeSkeletonJson,
  type Skeleton,
  type TextureLookup,
} from '../../../../../vendor/rigby2d'
import {
  ATLAS_IMAGES,
  ATLAS_TEXT,
  HEAD_IMAGES,
  REGIONS,
  CLIP_SECONDS,
  VIEW_LABELS,
  createStudySkeleton,
  type StudyView,
  type StudyBody,
  type StudyClip,
  type StudyHat,
  type StudyWeapon,
} from '../models/rigbyStudy'
import { getErrorMessage } from '@/core/utils/errorHandler'

const props = defineProps<{
  view: StudyView
  body: StudyBody
  outfit: string
  weapon: StudyWeapon
  hat: StudyHat
  clip: StudyClip
  phase: number
  mirrored: boolean
  bones: boolean
  mode: 'views' | 'single' | 'crowd'
  reload: number
}>()
const emit = defineEmits<{
  metrics: [value: { milliseconds: number; actors: number; drawCalls: number }]
  ready: []
}>()
const canvas = ref<HTMLCanvasElement>()
const overlay = ref<HTMLCanvasElement>()
const ready = ref(false)
const error = ref('')
let renderer: WebGLRenderer | undefined
let lookup: TextureLookup = () => null
let gl: WebGLRenderingContext | null = null
let disposed = false
let actors: Array<{ skeleton: Skeleton; pose: Pose; view: StudyView }> = []
let signature = ''
let reportAt = 0
const textures = new Set<WebGLTexture>()

function loadImage(url: string): Promise<HTMLImageElement> {
  return new Promise((resolve, reject) => {
    const image = new Image()
    image.onload = () => resolve(image)
    image.onerror = () => reject(new Error(`Could not load character artwork: ${url}`))
    image.src = url
  })
}

onMounted(async () => {
  try {
    const entries = await Promise.all(
      Object.entries({ ...ATLAS_IMAGES, ...HEAD_IMAGES }).map(
        async ([name, url]) => [name, await loadImage(url)] as const
      )
    )
    if (disposed || !canvas.value) return
    gl = canvas.value.getContext('webgl', {
      alpha: true,
      premultipliedAlpha: false,
      antialias: true,
      preserveDrawingBuffer: true,
    })
    if (!gl)
      throw new Error('WebGL is unavailable. Enable browser hardware acceleration to view the rig.')
    renderer = new WebGLRenderer(gl)
    const images = Object.fromEntries(entries)
    const atlasLookup = renderer.atlasTextures(parseAtlas(ATLAS_TEXT), images)
    const headsLookup = renderer.imageTextures(
      Object.fromEntries(entries.filter(([name]) => name.startsWith('head-')))
    )
    lookup = (name) => atlasLookup(name) ?? headsLookup(name)
    for (const name of [...Object.keys(REGIONS), ...Object.keys(HEAD_IMAGES)]) {
      const entry = lookup(name)
      if (entry) textures.add(entry.tex.texture)
    }
    ready.value = true
    emit('ready')
  } catch (cause) {
    console.error('[Rigby study] Failed to initialize renderer', cause)
    error.value = getErrorMessage(cause)
  }
})
onBeforeUnmount(() => {
  disposed = true
  for (const texture of textures) gl?.deleteTexture(texture)
  renderer?.dispose()
})

function aimSupportHand(skeleton: Skeleton, pose: Pose) {
  const index = (name: string) => skeleton.bones.findIndex((b) => b.name === name)
  const upper = index('backArm')
  const lower = index('backForearm')
  const weapon = index('weapon')
  const shoulder = pose.world[upper]!
  const gun = pose.world[weapon]!
  const targetX = gun.tx + gun.a * 52 + gun.c * 5
  const targetY = gun.ty + gun.b * 52 + gun.d * 5
  const dx = targetX - shoulder.tx
  const dy = targetY - shoulder.ty
  const scale = Math.hypot(shoulder.a, shoulder.b)
  const a = 50 * scale
  const b = 45 * scale
  const distance = Math.max(Math.abs(a - b) + 0.01, Math.min(a + b - 0.01, Math.hypot(dx, dy)))
  const reflected = props.mirrored ? -1 : 1
  const elbow = Math.acos((distance * distance - a * a - b * b) / (2 * a * b)) * reflected
  const angle = Math.atan2(dy, dx) - Math.atan2(b * Math.sin(elbow), a + b * Math.cos(elbow))
  const torso = pose.world[index('torso')]!
  const determinant = torso.a * torso.d - torso.b * torso.c
  const localX = (torso.d * Math.cos(angle) - torso.c * Math.sin(angle)) / determinant
  const localY = (-torso.b * Math.cos(angle) + torso.a * Math.sin(angle)) / determinant
  pose.local[upper]!.rotation = (Math.atan2(localY, localX) * 180) / Math.PI + 90
  pose.local[lower]!.rotation = ((elbow * 180) / Math.PI) * reflected
  pose.updateWorld(skeleton)
}

watchEffect(() => {
  if (!ready.value || !renderer || !gl || !canvas.value || !overlay.value) return
  const start = performance.now()
  const views: StudyView[] =
    props.mode === 'views'
      ? ['front', 'quarter', 'side']
      : Array.from({ length: props.mode === 'crowd' ? 36 : 1 }, () => props.view)
  const key = `${views.join(',')}-${props.body}-${props.reload}`
  if (key !== signature) {
    actors = views.map((view) => {
      const original = createStudySkeleton(view, props.body)
      // Exercise the actual export/import path on every setup change.
      const { skeleton } = readSkeletonJson(
        JSON.parse(JSON.stringify(writeSkeletonJson(original).json))
      )
      return { view, skeleton, pose: new Pose(skeleton) }
    })
    signature = key
  }
  const width = canvas.value.width
  const height = canvas.value.height
  const ctx = overlay.value.getContext('2d')!
  ctx.clearRect(0, 0, width, height)
  const styles = getComputedStyle(canvas.value)
  const theme = styles.color
  const jointColor = styles.getPropertyValue('--color-warning').trim() || theme
  ctx.strokeStyle = theme
  ctx.globalAlpha = 0.1
  ctx.lineWidth = 1
  for (let x = 0; x <= width; x += 40) {
    ctx.beginPath()
    ctx.moveTo(x, 0)
    ctx.lineTo(x, height)
    ctx.stroke()
  }
  for (let y = 0; y <= height; y += 40) {
    ctx.beginPath()
    ctx.moveTo(0, y)
    ctx.lineTo(width, y)
    ctx.stroke()
  }
  ctx.globalAlpha = 1
  gl.viewport(0, 0, width, height)
  gl.clearColor(0, 0, 0, 0)
  gl.clear(gl.COLOR_BUFFER_BIT)
  renderer.begin(width, height, { x: width / 2, y: height / 2, zoom: 1 })
  const columns = props.mode === 'crowd' ? 9 : views.length
  const scale = props.mode === 'crowd' ? 0.3 : 1.1
  actors.forEach(({ skeleton, pose, view }, actorIndex) => {
    const cx = (((actorIndex % columns) + 0.5) * width) / columns
    const floor =
      props.mode === 'crowd' ? height - (Math.floor(actorIndex / columns) + 1) * 132 : 72
    skeleton.skin = props.outfit
    pose.reset(skeleton)
    const animation = skeleton.animations.find((a) => a.name === props.clip)!
    const phase = (props.phase + (props.mode === 'crowd' ? actorIndex / 36 : 0)) % 1
    pose.apply(skeleton, animation, phase * CLIP_SECONDS[props.clip], 1)
    const root = pose.local[0]!
    root.x = cx
    root.y = floor
    root.scale_x = scale * (props.mirrored ? -1 : 1)
    root.scale_y = scale
    const slot = (name: string) => skeleton.slots.findIndex((s) => s.name === name)
    pose.attachment[slot('hat')] = props.hat === 'none' ? null : props.hat
    pose.attachment[slot('weapon')] = props.weapon === 'none' ? null : props.weapon
    if (props.weapon !== 'none') {
      pose.attachment[slot('frontHand')] = 'fist'
      const arm = skeleton.bones.findIndex((b) => b.name === 'frontArm')
      const forearm = skeleton.bones.findIndex((b) => b.name === 'frontForearm')
      // Hold the primary grip up; attack keys add recoil without replacing the walk/idle clip.
      pose.local[arm]!.rotation =
        props.clip === 'attack' ? pose.local[arm]!.rotation * 0.2 + 48 : 55
      pose.local[forearm]!.rotation = 35
    }
    pose.updateWorld(skeleton)
    if (props.weapon !== 'none') {
      const hand = skeleton.bones.findIndex((b) => b.name === 'frontHand')
      const weapon = skeleton.bones.findIndex((b) => b.name === 'weapon')
      const world = pose.world[hand]!
      pose.local[weapon]!.rotation =
        ((-Math.atan2(world.b * (props.mirrored ? -1 : 1), world.a * (props.mirrored ? -1 : 1)) *
          180) /
          Math.PI) *
        (props.mirrored ? -1 : 1)
      pose.updateWorld(skeleton)
      if (props.weapon === 'rifle') {
        aimSupportHand(skeleton, pose)
        pose.attachment[slot('backHand')] = 'fist'
      }
    }
    renderer!.drawSkeleton(skeleton, pose, lookup)
    ctx.fillStyle = theme
    ctx.globalAlpha = 0.25
    ctx.beginPath()
    ctx.ellipse(cx, height - floor + 7, 52 * scale, 7 * scale, 0, 0, Math.PI * 2)
    ctx.fill()
    ctx.globalAlpha = 1
    if (props.bones) {
      ctx.strokeStyle = jointColor
      ctx.lineWidth = props.mode === 'crowd' ? 1 : 2
      skeleton.bones.forEach((bone, i) => {
        if (!i || bone.name === 'weapon') return
        const world = pose.world[i]!
        const parent = bone.parent === null ? undefined : pose.world[bone.parent]
        if (parent && bone.parent !== 0) {
          ctx.beginPath()
          ctx.moveTo(parent.tx, height - parent.ty)
          ctx.lineTo(world.tx, height - world.ty)
          ctx.stroke()
        }
        ctx.beginPath()
        ctx.arc(world.tx, height - world.ty, 3, 0, Math.PI * 2)
        ctx.fillStyle = theme
        ctx.fill()
      })
    }
    if (props.mode !== 'crowd') {
      ctx.fillStyle = theme
      ctx.font = '15px monospace'
      ctx.textAlign = 'center'
      ctx.fillText(VIEW_LABELS[view].toUpperCase(), cx, 32)
      ctx.globalAlpha = 0.55
      ctx.font = '12px monospace'
      ctx.fillText(
        view === 'quarter' ? 'SOURCE ART / SHARED RIG' : 'PROJECTED OUTFIT / STUDY HEAD',
        cx,
        height - 23
      )
      ctx.globalAlpha = 1
    }
  })
  renderer.end()
  const elapsed = performance.now() - start
  if (start - reportAt > 400) {
    emit('metrics', { milliseconds: elapsed, actors: actors.length, drawCalls: renderer.drawCalls })
    reportAt = start
  }
})
</script>

<template>
  <!-- @vue-ignore -->
  <div
    class="relative aspect-[15/7] w-full overflow-hidden bg-surface-sunken text-theme-primary"
    :data-ready="ready"
    :data-phase="phase.toFixed(3)"
    :data-mode="mode"
    data-testid="rigby-stage"
  >
    <canvas
      ref="canvas"
      width="1200"
      height="560"
      class="absolute inset-0 size-full"
      aria-label="Animated dwellers rendered by Rigby2D"
    />
    <canvas
      ref="overlay"
      width="1200"
      height="560"
      class="pointer-events-none absolute inset-0 size-full"
      aria-hidden="true"
    />
    <p v-if="error" role="alert" class="absolute inset-x-6 top-1/2 text-center text-danger">
      {{ error }}
    </p>
    <p v-else-if="!ready" role="status" class="absolute inset-x-6 top-1/2 text-center">
      Loading the wardrobe…
    </p>
  </div>
</template>
