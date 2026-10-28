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
} from '../models/dwellerRig'

const props = withDefaults(
  defineProps<{
    clip: RigClip
    phase: number
    adjustments?: JointAngles
    display?: 'art' | 'bones' | 'overlay'
    selected?: BoneId
    mirrored?: boolean
    referenceOpacity?: number
  }>(),
  { display: 'overlay', mirrored: false, referenceOpacity: 0 }
)
const emit = defineEmits<{ select: [bone: BoneId] }>()
const id = useId()
const joints = computed(() => resolveRig(props.clip, props.phase, props.adjustments))
const connections = computed(() =>
  joints.value.flatMap((joint) => {
    const parent = joints.value.find((candidate) => candidate.id === joint.parent)
    return parent ? [{ parent, joint }] : []
  })
)
const layers = computed(() => [...joints.value].sort((a, b) => a.layer - b.layer))
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
  >
    <title>Articulated dweller · {{ clip }} · {{ Math.round(phase * 100) }}%</title>
    <defs>
      <radialGradient :id="`${id}-shadow`">
        <stop offset="0" stop-color="black" stop-opacity="0.5" />
        <stop offset="1" stop-color="black" stop-opacity="0" />
      </radialGradient>
    </defs>
    <ellipse cx="200" cy="457" rx="69" ry="12" :fill="`url(#${id}-shadow)`" />
    <g :transform="mirrored ? 'translate(400 0) scale(-1 1)' : undefined">
      <g v-if="display !== 'bones'" :opacity="display === 'overlay' ? 0.8 : 1" aria-hidden="true">
        <g
          v-for="joint in layers"
          :key="joint.id"
          :transform="`translate(${joint.x} ${joint.y}) rotate(${joint.angle})`"
          v-bind="{ 'data-part': joint.id }"
        >
          <svg
            :transform="`rotate(${joint.sprite.rotation ?? 0}) ${joint.sprite.flipX ? `translate(${2 * joint.sprite.frame[0] + joint.sprite.frame[2]} 0) scale(-1 1)` : ''}`"
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
        v-if="display !== 'art'"
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
        v-for="joint in joints"
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
