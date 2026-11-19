<script setup lang="ts">
import { ref, watch } from 'vue'
import { RouterLink } from 'vue-router'
import { useDocumentVisibility, usePreferredReducedMotion, useRafFn } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { Slider } from '@/core/components/ui/slider'
import { ToggleGroup, ToggleGroupItem } from '@/core/components/ui/toggle-group'
import {
  Select,
  SelectContent,
  SelectGroup,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/core/components/ui/select'
import { Play, Pause, RotateCcw, FlipHorizontal2, Download, Bone } from '@lucide/vue'
import { writeSkeletonJson } from '../../../../../vendor/rigby2d'
import RigbyStudyStage from '../components/RigbyStudyStage.vue'
import {
  ATLAS_TEXT,
  CLIP_SECONDS,
  VIEW_LABELS,
  createStudySkeleton,
  type StudyView,
  type StudyBody,
  type StudyClip,
  type StudyHat,
  type StudyWeapon,
} from '../models/rigbyStudy'

const iconAttrs: Record<string, string> = { 'data-icon': 'inline-start' }
const view = ref<StudyView>('quarter')
const body = ref<StudyBody>('human')
const outfit = ref('vault')
const weapon = ref<StudyWeapon>('none')
const hat = ref<StudyHat>('none')
const clip = ref<StudyClip>('idle')
const mode = ref<'views' | 'single' | 'crowd'>('views')
const phase = ref(0)
const speed = ref(1)
const mirrored = ref(false)
const bones = ref(false)
const playing = ref(false)
const loaded = ref(false)
const reload = ref(0)
const status = ref('')
const metrics = ref({ milliseconds: 0, actors: 3, drawCalls: 0 })
const visibility = useDocumentVisibility()
const reducedMotion = usePreferredReducedMotion()
const { pause, resume } = useRafFn(
  ({ delta }) => {
    phase.value =
      (phase.value + ((Math.min(delta, 100) / 1000) * speed.value) / CLIP_SECONDS[clip.value]) % 1
  },
  { immediate: false }
)
watch([playing, loaded, visibility], ([active, ready, visible]) =>
  active && ready && visible === 'visible' ? resume() : pause()
)
watch(reducedMotion, () => {
  playing.value = false
})
watch(clip, () => {
  phase.value = 0
})

function onReady() {
  loaded.value = true
  playing.value = reducedMotion.value !== 'reduce'
}
function seek(values: number[] | undefined) {
  playing.value = false
  phase.value = Math.min(0.999, (values?.[0] ?? 0) / 100)
}
function download(name: string, content: string, type: string) {
  const url = URL.createObjectURL(new Blob([content], { type }))
  const link = document.createElement('a')
  link.href = url
  link.download = name
  link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
}
function exportRig() {
  const skeleton = createStudySkeleton(view.value, body.value)
  skeleton.skin = outfit.value
  skeleton.slots.find((slot) => slot.name === 'weapon')!.attachment =
    weapon.value === 'none' ? null : weapon.value
  skeleton.slots.find((slot) => slot.name === 'hat')!.attachment =
    hat.value === 'none' ? null : hat.value
  download(
    `dweller-${view.value}-${body.value}.json`,
    JSON.stringify(writeSkeletonJson(skeleton).json, null, 2),
    'application/json'
  )
  status.value =
    'Rig exported. Atlas pages and the three head images are in the study assets folder.'
}
function reloadRig() {
  reload.value++
  status.value =
    'Rig serialized and reloaded through Rigby2D. Equipment and playback phase preserved.'
}
</script>

<template>
  <main class="mx-auto flex max-w-[1560px] flex-col gap-6 px-4 py-6 text-theme-primary sm:px-8">
    <header class="flex flex-wrap items-end justify-between gap-5 border-b border-theme-glow pb-6">
      <div class="flex flex-col gap-2">
        <RouterLink to="/dev" class="w-fit text-xs text-theme-primary/60 hover:text-theme-primary"
          >← Development tools</RouterLink
        >
        <p class="mt-2 text-xs tracking-[0.25em]">VAULT-TEC / CHARACTER RESEARCH / 02</p>
        <h1 class="text-3xl font-bold tracking-tight sm:text-5xl">Dweller motion lab</h1>
        <p class="max-w-2xl text-sm leading-relaxed text-theme-primary/65">
          One skeleton family. A wardrobe of possibilities. Change equipment while the animation
          keeps running.
        </p>
      </div>
      <div class="border-l border-theme-glow pl-4 text-xs leading-6 text-theme-primary/60">
        <p>RIGBY2D 0.3.0 · WEBGL</p>
        <p>17 bones · original outfit atlas</p>
        <p>Research preview · local only</p>
      </div>
    </header>

    <div class="grid items-start gap-5 xl:grid-cols-[minmax(0,1fr)_280px]">
      <section
        class="min-w-0 overflow-hidden rounded-lg border border-theme-glow bg-surface"
        aria-label="Animation stage"
      >
        <div
          class="flex flex-wrap items-center justify-between gap-3 border-b border-theme-glow px-4 py-3"
        >
          <ToggleGroup
            type="single"
            :model-value="mode"
            variant="outline"
            size="sm"
            @update:model-value="
              (v) => {
                if (v) mode = v as typeof mode
              }
            "
          >
            <ToggleGroupItem value="views">Three views</ToggleGroupItem>
            <ToggleGroupItem value="single">Single</ToggleGroupItem>
            <ToggleGroupItem value="crowd">Crowd ×36</ToggleGroupItem>
          </ToggleGroup>
          <div class="flex gap-2">
            <Button variant="outline" size="sm" :aria-pressed="bones" @click="bones = !bones"
              ><Bone v-bind="iconAttrs" />Joints</Button
            >
            <Button
              variant="outline"
              size="sm"
              :aria-pressed="mirrored"
              @click="mirrored = !mirrored"
              ><FlipHorizontal2 v-bind="iconAttrs" />Mirror</Button
            >
          </div>
        </div>
        <RigbyStudyStage
          :view="view"
          :body="body"
          :outfit="outfit"
          :weapon="weapon"
          :hat="hat"
          :clip="clip"
          :phase="phase"
          :mode="mode"
          :bones="bones"
          :mirrored="mirrored"
          :reload="reload"
          @ready="onReady"
          @metrics="metrics = $event"
        />
        <div
          class="flex flex-wrap items-center justify-between gap-2 border-t border-theme-glow px-4 py-2 text-[11px] text-theme-primary/60"
        >
          <span>{{ metrics.actors }} actors · {{ metrics.drawCalls }} draw calls</span>
          <!-- @vue-ignore -->
          <span data-testid="frame-cost"
            >{{ metrics.milliseconds.toFixed(2) }} ms CPU update + submit</span
          >
          <span>GPU time excluded</span>
        </div>
        <div class="flex flex-col gap-5 border-t border-theme-glow p-4 sm:p-5">
          <div class="flex flex-wrap items-center justify-between gap-3">
            <ToggleGroup
              type="single"
              :model-value="clip"
              variant="outline"
              @update:model-value="
                (v) => {
                  if (v) clip = v as StudyClip
                }
              "
            >
              <ToggleGroupItem value="idle">Idle</ToggleGroupItem
              ><ToggleGroupItem value="walk">Walk</ToggleGroupItem
              ><ToggleGroupItem value="attack">Attack</ToggleGroupItem>
            </ToggleGroup>
            <ToggleGroup
              v-if="mode !== 'views'"
              type="single"
              :model-value="view"
              variant="outline"
              size="sm"
              @update:model-value="
                (v) => {
                  if (v) view = v as StudyView
                }
              "
            >
              <ToggleGroupItem v-for="(label, id) in VIEW_LABELS" :key="id" :value="id">{{
                label
              }}</ToggleGroupItem>
            </ToggleGroup>
            <div class="flex items-center gap-2">
              <Button
                :disabled="!loaded"
                :aria-label="playing ? 'Pause animation' : 'Play animation'"
                @click="playing = !playing"
                ><Pause v-if="playing" v-bind="iconAttrs" /><Play v-else v-bind="iconAttrs" />{{
                  playing ? 'Pause' : 'Play'
                }}</Button
              >
              <Button variant="outline" size="icon" aria-label="Reset animation" @click="phase = 0"
                ><RotateCcw
              /></Button>
            </div>
          </div>
          <div class="flex items-center gap-4">
            <span class="w-12 shrink-0 text-xs tabular-nums"
              >{{
                Math.round(phase * 100)
                  .toString()
                  .padStart(2, '0')
              }}%</span
            >
            <!-- @vue-ignore -->
            <Slider
              :model-value="[phase * 100]"
              :max="100"
              :step="1"
              aria-label="Animation position"
              @update:model-value="seek"
            />
            <span class="shrink-0 text-xs text-theme-primary/50">{{ CLIP_SECONDS[clip] }} s</span>
          </div>
          <div class="flex items-center justify-between gap-4 text-xs">
            <span class="text-theme-primary/60">PLAYBACK SPEED</span>
            <ToggleGroup
              type="single"
              :model-value="String(speed)"
              size="sm"
              variant="outline"
              @update:model-value="
                (v) => {
                  if (v) speed = Number(v)
                }
              "
            >
              <ToggleGroupItem value="0.25">¼×</ToggleGroupItem
              ><ToggleGroupItem value="0.5">½×</ToggleGroupItem
              ><ToggleGroupItem value="1">1×</ToggleGroupItem>
            </ToggleGroup>
          </div>
        </div>
      </section>

      <aside
        class="flex flex-col gap-6 rounded-lg border border-theme-glow bg-surface p-5"
        aria-label="Character configuration"
      >
        <div class="flex flex-col gap-1">
          <h2 class="text-lg font-bold">Wardrobe</h2>
          <p class="text-xs leading-5 text-theme-primary/55">Attachments change. Motion stays.</p>
        </div>
        <div class="flex flex-col gap-2">
          <label id="body-label" class="text-xs uppercase tracking-wider text-theme-primary/60"
            >Body profile</label
          >
          <Select
            :model-value="body"
            @update:model-value="
              (v) => {
                if (v === 'human' || v === 'bulky') body = v
              }
            "
            ><SelectTrigger aria-label="Body profile"><SelectValue /></SelectTrigger
            ><SelectContent
              ><SelectGroup
                ><SelectItem value="human">Human</SelectItem
                ><SelectItem value="bulky">Bulky humanoid</SelectItem></SelectGroup
              ></SelectContent
            ></Select
          >
        </div>
        <div class="flex flex-col gap-2">
          <label id="outfit-label" class="text-xs uppercase tracking-wider text-theme-primary/60"
            >Outfit</label
          >
          <Select
            :model-value="outfit"
            @update:model-value="
              (v) => {
                if (v === 'vault' || v === 'wasteland') outfit = v
              }
            "
            ><SelectTrigger aria-label="Outfit"><SelectValue /></SelectTrigger
            ><SelectContent
              ><SelectGroup
                ><SelectItem value="vault">Vault suit</SelectItem
                ><SelectItem value="wasteland">Wasteland vest</SelectItem></SelectGroup
              ></SelectContent
            ></Select
          >
        </div>
        <div class="flex flex-col gap-2">
          <label id="weapon-label" class="text-xs uppercase tracking-wider text-theme-primary/60"
            >Weapon</label
          >
          <Select
            :model-value="weapon"
            @update:model-value="
              (v) => {
                if (v === 'none' || v === 'pistol' || v === 'rifle') weapon = v
              }
            "
            ><SelectTrigger aria-label="Weapon"><SelectValue /></SelectTrigger
            ><SelectContent
              ><SelectGroup
                ><SelectItem value="none">Unarmed</SelectItem
                ><SelectItem value="pistol">10mm pistol</SelectItem
                ><SelectItem value="rifle">Hunting rifle</SelectItem></SelectGroup
              ></SelectContent
            ></Select
          >
        </div>
        <div class="flex flex-col gap-2">
          <label id="hat-label" class="text-xs uppercase tracking-wider text-theme-primary/60"
            >Headwear</label
          >
          <Select
            :model-value="hat"
            @update:model-value="
              (v) => {
                if (v === 'none' || v === 'fedora' || v === 'cowboy') hat = v
              }
            "
            ><SelectTrigger aria-label="Headwear"><SelectValue /></SelectTrigger
            ><SelectContent
              ><SelectGroup
                ><SelectItem value="none">No headwear</SelectItem
                ><SelectItem value="fedora">Fedora</SelectItem
                ><SelectItem value="cowboy">Cowboy hat</SelectItem></SelectGroup
              ></SelectContent
            ></Select
          >
        </div>
        <div class="flex flex-col gap-3 border-t border-theme-glow pt-5">
          <h3 class="text-xs uppercase tracking-wider text-theme-primary/60">Round-trip check</h3>
          <Button variant="outline" @click="reloadRig"
            ><RotateCcw v-bind="iconAttrs" />Reload exported rig</Button
          >
          <div class="grid grid-cols-2 gap-2">
            <Button variant="outline" size="sm" @click="exportRig"
              ><Download v-bind="iconAttrs" />Rig JSON</Button
            ><Button
              variant="outline"
              size="sm"
              @click="download('dwellers.atlas', ATLAS_TEXT, 'text/plain')"
              >Atlas</Button
            >
          </div>
          <p v-if="status" role="status" class="text-xs leading-5 text-theme-primary/65">
            {{ status }}
          </p>
        </div>
      </aside>
    </div>
    <footer
      class="grid gap-5 border-t border-theme-glow pt-5 text-xs leading-6 text-theme-primary/60 md:grid-cols-3"
    >
      <p>
        <strong class="text-theme-primary">Original parts.</strong> Outfits, hands, weapons, and
        hats come directly from your supplied atlases. The three-quarter head reuses Chet’s existing
        cutout.
      </p>
      <p>
        <strong class="text-theme-primary">View studies.</strong> Front and side use provisional
        vector heads and projected outfit pieces. Dedicated front/side outfit artwork is still
        needed for production.
      </p>
      <p>
        <strong class="text-theme-primary">Shared motion.</strong> Both body profiles use the same
        clips. The bulky profile tests fitting; it is not finished super-mutant art. Grip correction
        runs in the preview.
      </p>
    </footer>
  </main>
</template>
