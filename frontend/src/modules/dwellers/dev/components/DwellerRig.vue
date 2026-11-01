<script setup lang="ts">
import { computed, useId } from 'vue'
import suitSheet from '../assets/vault-suit-parts.webp'
import headSheet from '../assets/chet-head.webp'
import chetReference from '../assets/chet-reference.webp'
import handSheet from '../assets/hand-poses.webp'
import {
  RIG_REFERENCE,
  resolveRig,
  type BoneId,
  type JointAngles,
  type RigClip,
  type SpriteOverrides,
  type RigJoint,
  type RigSprite,
} from '../models/dwellerRig'

const props = withDefaults(
  defineProps<{
    editing?: boolean
    clip: RigClip
    phase: number
    adjustments?: JointAngles
    sprites?: SpriteOverrides
    display?: 'art' | 'bones' | 'overlay'
    selected?: BoneId
    mirrored?: boolean
    referenceOpacity?: number
  }>(),
  { display: 'overlay', mirrored: false, referenceOpacity: 0 }
)
const emit = defineEmits<{ select: [bone: BoneId]; place: [bone: BoneId, sprite: RigSprite] }>()
const id = useId()
const joints = computed(() => resolveRig(props.clip, props.phase, props.adjustments, props.sprites))
const connections = computed(() =>
  joints.value.flatMap((joint) => {
    const parent = joints.value.find((candidate) => candidate.id === joint.parent)
    return parent ? [{ parent, joint }] : []
  })
)
const layers = computed(() => [...joints.value].sort((a, b) => a.layer - b.layer))
const selectedPart = computed(() => joints.value.find((joint) => joint.id === props.selected))
const corners = [
  [0, 0],
  [1, 0],
  [0, 1],
  [1, 1],
] as const
let drag:
  | {
      joint: RigJoint
      inverse: DOMMatrix
      start: DOMPoint
      corner?: readonly [number, number]
      pointer: number
    }
  | undefined

function startDrag(event: PointerEvent, joint: RigJoint, corner?: readonly [number, number]) {
  if (!props.editing || event.button !== 0) return
  event.preventDefault()
  event.stopPropagation()
  emit('select', joint.id)
  const target = event.currentTarget as SVGGraphicsElement
  const matrix = corner
    ? (target.parentElement as unknown as SVGGraphicsElement).getScreenCTM()!
    : target.getScreenCTM()!.rotate(joint.sprite.rotation ?? 0)
  const inverse = matrix.inverse()
  drag = {
    joint,
    inverse,
    start: new DOMPoint(event.clientX, event.clientY).matrixTransform(inverse),
    corner,
    pointer: event.pointerId,
  }
  target.setPointerCapture(event.pointerId)
}
function movePart(event: PointerEvent) {
  if (!drag || drag.pointer !== event.pointerId) return
  const point = new DOMPoint(event.clientX, event.clientY).matrixTransform(drag.inverse)
  const [x, y, w, h] = drag.joint.sprite.frame
  let frame: [number, number, number, number]
  if (drag.corner) {
    const [cx, cy] = drag.corner
    const ax = x + (1 - cx) * w
    const ay = y + (1 - cy) * h
    const dx = (2 * cx - 1) * w
    const dy = (2 * cy - 1) * h
    const scale = Math.max(0.1, ((point.x - ax) * dx + (point.y - ay) * dy) / (w * w + h * h))
    frame = [ax - (1 - cx) * w * scale, ay - (1 - cy) * h * scale, w * scale, h * scale]
  } else frame = [x + point.x - drag.start.x, y + point.y - drag.start.y, w, h]
  emit('place', drag.joint.id, { ...drag.joint.sprite, frame })
}
function endDrag(event: PointerEvent) {
  if (drag?.pointer === event.pointerId) drag = undefined
}
const sheets = {
  suit: { url: suitSheet, width: 520, height: 260 },
  head: { url: headSheet, width: 94, height: 96 },
  hands: { url: handSheet, width: 180, height: 120 },
}
</script>

<template>
  <svg
    viewBox="0 0 400 480"
    role="group"
    aria-label="Articulated 2D dweller rig"
    class="h-full w-full overflow-visible"
    :class="editing ? 'touch-none select-none' : ''"
    @pointermove="movePart"
    @pointerup="endDrag"
    @pointercancel="endDrag"
    @lostpointercapture="endDrag"
  >
    <title>Articulated dweller · {{ clip }} · {{ Math.round(phase * 100) }}%</title>
    <defs>
      <clipPath :id="`${id}-head-cutout`" clipPathUnits="userSpaceOnUse">
        <polygon points="0,0 94,0 94,77 83,77 80,82 75,87 69,90 64,93 0,96" />
      </clipPath>
      <radialGradient :id="`${id}-shadow`">
        <stop offset="0" stop-color="black" stop-opacity="0.5" />
        <stop offset="1" stop-color="black" stop-opacity="0" />
      </radialGradient>
    </defs>
    <ellipse cx="200" cy="457" rx="69" ry="12" :fill="`url(#${id}-shadow)`" />
    <g :transform="mirrored ? 'translate(400 0) scale(-1 1)' : undefined">
      <g
        v-if="editing || display !== 'bones'"
        :opacity="!editing && display === 'overlay' ? 0.8 : 1"
        :aria-hidden="!editing"
      >
        <g
          v-for="joint in layers"
          :key="joint.id"
          :transform="`translate(${joint.x} ${joint.y}) rotate(${joint.angle})`"
          v-bind="{ 'data-part': joint.id }"
          :role="editing ? 'button' : undefined"
          :tabindex="editing ? 0 : undefined"
          :aria-label="editing ? `Edit ${joint.label}` : undefined"
          :aria-pressed="editing ? joint.id === selected : undefined"
          :class="editing ? 'cursor-move' : ''"
          @pointerdown="startDrag($event, joint)"
          @keydown.enter.prevent="editing && emit('select', joint.id)"
          @keydown.space.prevent="editing && emit('select', joint.id)"
        >
          <svg
            :transform="`rotate(${joint.sprite.rotation ?? 0}) ${joint.sprite.flipX ? `translate(${2 * joint.sprite.frame[0] + joint.sprite.frame[2]} 0) scale(-1 1)` : ''} ${joint.sprite.flipY ? `translate(0 ${2 * joint.sprite.frame[1] + joint.sprite.frame[3]}) scale(1 -1)` : ''}`"
            :x="joint.sprite.frame[0]"
            :y="joint.sprite.frame[1]"
            :width="joint.sprite.frame[2]"
            :height="joint.sprite.frame[3]"
            :viewBox="joint.sprite.crop.join(' ')"
            overflow="hidden"
            preserveAspectRatio="none"
          >
            <image
              :href="sheets[joint.sprite.sheet].url"
              :width="sheets[joint.sprite.sheet].width"
              :height="sheets[joint.sprite.sheet].height"
              :clip-path="joint.id === 'head' ? `url(#${id}-head-cutout)` : undefined"
            />
          </svg>
        </g>
      </g>
      <svg
        v-if="referenceOpacity > 0"
        :x="RIG_REFERENCE.x"
        :y="RIG_REFERENCE.y"
        :width="RIG_REFERENCE.width * RIG_REFERENCE.scale"
        :height="RIG_REFERENCE.height * RIG_REFERENCE.scale"
        :viewBox="`0 0 ${RIG_REFERENCE.width} ${RIG_REFERENCE.height}`"
        class="pointer-events-none"
        :opacity="referenceOpacity"
        v-bind="{ 'data-reference': 'chet' }"
        aria-label="Original Chet reference overlay"
      >
        <image :href="chetReference" width="136" height="287" />
      </svg>
      <g
        v-if="editing && selectedPart"
        :transform="`translate(${selectedPart.x} ${selectedPart.y}) rotate(${selectedPart.angle + (selectedPart.sprite.rotation ?? 0)})`"
        class="text-warning"
        v-bind="{ 'data-selection-box': true }"
      >
        <rect
          :x="selectedPart.sprite.frame[0]"
          :y="selectedPart.sprite.frame[1]"
          :width="selectedPart.sprite.frame[2]"
          :height="selectedPart.sprite.frame[3]"
          fill="none"
          stroke="currentColor"
          stroke-width="1"
          stroke-dasharray="3 2"
          pointer-events="none"
        />
        <rect
          v-for="(corner, index) in corners"
          :key="index"
          :x="selectedPart.sprite.frame[0] + corner[0] * selectedPart.sprite.frame[2] - 4"
          :y="selectedPart.sprite.frame[1] + corner[1] * selectedPart.sprite.frame[3] - 4"
          width="8"
          height="8"
          fill="currentColor"
          stroke="black"
          stroke-width="1"
          v-bind="{ 'data-resize-handle': index }"
          class="cursor-nwse-resize"
          @pointerdown="startDrag($event, selectedPart, corner)"
        />
      </g>
      <g
        v-if="!editing && display !== 'art'"
        class="text-theme-primary"
        fill="none"
        stroke="currentColor"
        stroke-width="2"
        aria-hidden="true"
      >
        <line
          v-for="{ parent, joint } in connections"
          :key="`link-${joint.id}`"
          :x1="parent.x"
          :y1="parent.y"
          :x2="joint.x"
          :y2="joint.y"
          stroke-dasharray="2 4"
          opacity="0.4"
        />
        <g
          v-for="joint in joints"
          :key="joint.id"
          v-bind="{ 'data-bone': joint.id }"
          :class="joint.id === selected ? 'text-warning' : 'text-theme-primary'"
        >
          <line
            :x1="joint.x"
            :y1="joint.y"
            :x2="joint.tip[0]"
            :y2="joint.tip[1]"
            stroke-linecap="round"
          />
          <circle
            :cx="joint.x"
            :cy="joint.y"
            :r="joint.id === selected ? 6 : 3"
            class="fill-surface-sunken"
          />
        </g>
      </g>
      <g
        v-for="joint in editing ? [] : joints"
        :key="joint.id"
        role="button"
        tabindex="0"
        :aria-label="`Select ${joint.label}`"
        :aria-pressed="joint.id === selected"
        v-bind="{ 'data-joint': joint.id }"
        class="group cursor-pointer text-warning focus:outline-none"
        @click="emit('select', joint.id)"
        @keydown.enter.prevent="emit('select', joint.id)"
        @keydown.space.prevent="emit('select', joint.id)"
      >
        <title>{{ joint.label }}</title>
        <circle
          :cx="joint.x"
          :cy="joint.y"
          r="10"
          fill="transparent"
          class="stroke-transparent hover:stroke-current group-focus:stroke-current"
          stroke-width="2"
        />
      </g>
    </g>
  </svg>
</template>
