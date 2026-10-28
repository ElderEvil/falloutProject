<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useDocumentVisibility, usePreferredReducedMotion, useRafFn } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { Slider } from '@/core/components/ui/slider'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import DwellerRig from '../components/DwellerRig.vue'
import chetReference from '../assets/chet-reference.webp'
import {
  RIG_BONES,
  RIG_CLIPS,
  type BoneId,
  type JointAngles,
  type RigClip,
} from '../models/dwellerRig'

const clip = ref<RigClip>('bind')
const phase = ref(0)
const playing = ref(false)
const speed = ref(1)
const display = ref<'art' | 'bones' | 'overlay'>('overlay')
const mirrored = ref(false)
const showReference = ref(false)
const referenceOpacity = ref(40)
const selected = ref<BoneId>('frontUpperArm')
const adjustments = ref<JointAngles>({})
const reducedMotion = usePreferredReducedMotion()
const visibility = useDocumentVisibility()
const joint = computed(() => RIG_BONES.find((bone) => bone.id === selected.value)!)
const adjustment = computed(() => adjustments.value[selected.value] ?? 0)
const parentLabel = computed(
  () => RIG_BONES.find((bone) => bone.id === joint.value.parent)?.label ?? 'World origin'
)
const definition = computed(() => RIG_CLIPS[clip.value])
const clips = Object.entries(RIG_CLIPS) as Array<[RigClip, (typeof RIG_CLIPS)[RigClip]]>
const displays = ['art', 'bones', 'overlay'] as const
const { pause, resume } = useRafFn(
  ({ delta }) => {
    phase.value =
      (phase.value + (Math.min(delta, 50) * speed.value) / (definition.value.duration * 1000)) % 1
  },
  { immediate: false, fpsLimit: 60 }
)
watch([playing, visibility], ([active, visible]) =>
  active && visible === 'visible' ? resume() : pause()
)
watch(reducedMotion, () => {
  playing.value = false
})

function selectClip(value: RigClip) {
  playing.value = false
  clip.value = value
  phase.value = 0
  adjustments.value = {}
}
function seek(values: number[] | undefined) {
  playing.value = false
  phase.value = (values?.[0] ?? 0) / 100
}
function step(direction: number) {
  seek([Math.max(0, Math.min(1, phase.value + direction / 60)) * 100])
}
function adjust(values: number[] | undefined) {
  playing.value = false
  adjustments.value = { ...adjustments.value, [selected.value]: values?.[0] ?? 0 }
}
function reset() {
  playing.value = false
  phase.value = 0
  adjustments.value = {}
}
</script>

<template>
  <div class="mx-auto max-w-7xl space-y-6 px-5 py-8 text-theme-primary sm:px-8">
    <header class="flex flex-wrap items-end justify-between gap-4 border-b border-theme-glow pb-5">
      <div class="space-y-2">
        <RouterLink to="/dev" class="text-xs text-theme-primary/60 hover:text-theme-primary"
          >← Development tools</RouterLink
        >
        <p class="text-xs tracking-[0.2em] text-warning">VAULT-TEC / MOTION STUDY 01</p>
        <h1 class="text-3xl font-bold tracking-tight sm:text-4xl">Dweller rig</h1>
        <p class="max-w-xl text-sm leading-relaxed text-theme-primary/65">
          A jointed 2D cutout. Inspect the skeleton, rotate a joint, then try it in motion.
        </p>
      </div>
      <div class="border-l border-theme-glow pl-4 text-xs leading-6 text-theme-primary/60">
        <p>15 bones · forward kinematics</p>
        <p>Source outfit parts · SVG renderer</p>
      </div>
    </header>

    <div class="grid items-start gap-5 lg:grid-cols-[minmax(0,1fr)_20rem]">
      <section
        aria-label="Rig stage"
        class="relative overflow-hidden rounded-xl border border-theme-glow bg-surface-sunken"
      >
        <div class="absolute inset-0 text-theme-primary/10" aria-hidden="true">
          <svg width="100%" height="100%">
            <defs>
              <pattern id="rig-workbench-grid" width="32" height="32" patternUnits="userSpaceOnUse">
                <path d="M32 0H0V32" fill="none" stroke="currentColor" stroke-width="0.5" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#rig-workbench-grid)" />
          </svg>
        </div>
        <div
          class="relative flex items-center justify-between border-b border-theme-glow px-4 py-3"
        >
          <p class="text-xs tracking-widest text-theme-primary/70">
            {{ definition.label.toUpperCase() }} / {{ playing ? 'PLAYING' : 'POSE INSPECTION' }}
          </p>
          <div role="group" aria-label="Rig display" class="flex gap-1">
            <Button
              v-for="mode in displays"
              :key="mode"
              size="sm"
              :variant="display === mode ? 'default' : 'ghost'"
              :aria-pressed="display === mode"
              class="capitalize"
              @click="display = mode"
              >{{ mode }}</Button
            >
          </div>
        </div>
        <div class="relative mx-auto h-[540px] max-w-[450px] px-5 pb-5 pt-2">
          <DwellerRig
            :clip="clip"
            :phase="phase"
            :adjustments="adjustments"
            :display="display"
            :selected="selected"
            :mirrored="mirrored"
            :reference-opacity="showReference ? referenceOpacity / 100 : 0"
            @select="selected = $event"
          />
        </div>
        <div
          class="relative flex items-center justify-between border-t border-theme-glow px-4 py-3 text-xs text-theme-primary/60"
        >
          <span>Independent limbs. Connected pivots.</span>
          <Button size="sm" variant="ghost" :aria-pressed="mirrored" @click="mirrored = !mirrored"
            >Mirror {{ mirrored ? 'on' : 'off' }}</Button
          >
        </div>
      </section>

      <aside class="space-y-5" aria-label="Rig controls">
        <section class="space-y-4 rounded-xl border border-theme-glow bg-surface p-5">
          <h2 class="text-sm font-semibold uppercase tracking-widest">Motion clips</h2>
          <div class="grid grid-cols-2 gap-2" role="group" aria-label="Motion clips">
            <Button
              v-for="[key, item] in clips"
              :key="key"
              :variant="clip === key ? 'default' : 'outline'"
              :aria-pressed="clip === key"
              @click="selectClip(key)"
              >{{ item.label }}</Button
            >
          </div>
          <p class="min-h-12 text-sm leading-relaxed text-theme-primary/65">
            {{ definition.description }}
          </p>
          <div
            class="flex items-center justify-between border-t border-theme-glow pt-3 text-xs text-theme-primary/60"
          >
            <span>Cycle duration</span><span>{{ definition.duration.toFixed(1) }}s</span>
          </div>
        </section>
        <section class="space-y-4 rounded-xl border border-theme-glow bg-surface p-5">
          <Button
            variant="outline"
            class="w-full"
            :aria-pressed="showReference"
            @click="showReference = !showReference"
            >Chet overlay {{ showReference ? 'on' : 'off' }}</Button
          >
          <div class="flex justify-between text-xs text-theme-primary/65">
            <span>Reference opacity</span><span>{{ referenceOpacity }}%</span>
          </div>
          <Slider
            aria-label="Reference opacity"
            :model-value="[referenceOpacity]"
            :min="0"
            :max="100"
            :step="1"
            :disabled="!showReference"
            @update:model-value="referenceOpacity = $event?.[0] ?? 40"
          />
          <p class="text-xs leading-relaxed text-theme-primary/60">
            Aligned at the neck at the same scale. Bind pose follows Chet’s stance; Vault 33
            clothing differs from the classic suit.
          </p>
        </section>
        <section class="space-y-5 rounded-xl border border-theme-glow bg-surface p-5">
          <div class="flex items-center justify-between">
            <h2 class="text-sm font-semibold uppercase tracking-widest">Joint inspector</h2>
            <span class="text-xs text-warning"
              >{{ adjustment > 0 ? '+' : '' }}{{ adjustment }}°</span
            >
          </div>
          <Select :model-value="selected" @update:model-value="selected = $event as BoneId">
            <SelectTrigger aria-label="Selected joint"><SelectValue /></SelectTrigger>
            <SelectContent
              ><SelectItem v-for="bone in RIG_BONES" :key="bone.id" :value="bone.id">{{
                bone.label
              }}</SelectItem></SelectContent
            >
          </Select>
          <div class="space-y-2 text-xs text-theme-primary/60">
            <p>Parent → {{ parentLabel }}</p>
            <p>Local pivot → {{ joint.offset.join(', ') }}</p>
          </div>
          <div class="space-y-3">
            <p class="text-xs text-theme-primary/70">Angle adjustment</p>
            <Slider
              aria-label="Joint angle adjustment"
              :model-value="[adjustment]"
              :min="-135"
              :max="135"
              :step="1"
              @update:model-value="adjust"
            />
          </div>
          <Button variant="outline" size="sm" class="w-full" @click="reset">Reset pose</Button>
        </section>
        <p class="px-1 text-xs leading-relaxed text-theme-primary/50">
          Prototype only. An original Chet head with classic vault-suit parts; not yet connected to
          dweller appearance or game state.
        </p>
        <details
          class="rounded-xl border border-theme-glow bg-surface p-4 text-xs text-theme-primary/65"
        >
          <summary class="cursor-pointer text-theme-primary">Original art reference: Chet</summary>
          <div class="mt-3 flex items-center gap-4">
            <img
              :src="chetReference"
              width="136"
              height="287"
              class="h-40 w-auto"
              alt="Original Fallout Shelter Chet wearing his Vault 33 suit"
            />
            <p class="leading-relaxed">
              Chet wears the Vault 33 suit. This study uses his original head and the classic suit’s
              original separated parts; no common/rare generated portrait is used.
            </p>
          </div>
        </details>
      </aside>
    </div>

    <section
      aria-label="Playback timeline"
      class="space-y-5 rounded-xl border border-theme-glow bg-surface p-5"
    >
      <div class="flex flex-wrap items-center justify-between gap-3">
        <div class="flex gap-2">
          <Button :disabled="clip === 'bind'" @click="playing = !playing">{{
            playing ? 'Pause' : 'Play'
          }}</Button
          ><Button variant="outline" aria-label="Previous frame" @click="step(-1)">← Frame</Button
          ><Button variant="outline" aria-label="Next frame" @click="step(1)">Frame →</Button>
        </div>
        <output aria-label="Clip progress" class="text-sm tabular-nums text-warning"
          >{{ Math.round(phase * 100) }}%</output
        >
        <div class="flex gap-1" role="group" aria-label="Playback speed">
          <Button
            v-for="rate in [0.5, 1, 1.5]"
            :key="rate"
            size="sm"
            :variant="speed === rate ? 'default' : 'ghost'"
            :aria-pressed="speed === rate"
            @click="speed = rate"
            >{{ rate }}×</Button
          >
        </div>
      </div>
      <Slider
        aria-label="Clip timeline"
        :model-value="[phase * 100]"
        :min="0"
        :max="100"
        :step="1"
        @update:model-value="seek"
      />
      <div class="flex justify-between text-xs text-theme-primary/50">
        <span>0.00s</span><span>Scrub or step to inspect a pose</span
        ><span>{{ definition.duration.toFixed(2) }}s</span>
      </div>
      <p v-if="reducedMotion === 'reduce'" class="text-xs text-theme-primary/70">
        Reduced motion detected. Playback starts only when you press Play.
      </p>
    </section>
  </div>
</template>
