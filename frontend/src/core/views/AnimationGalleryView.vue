<script setup lang="ts">
import { reactive, ref, watch } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { Button } from '@/core/components/ui/button'
import { Input } from '@/core/components/ui/input'
import VaultBoyFeedback from '@/core/components/common/VaultBoyFeedback.vue'
import { useVaultBoyFeedback } from '@/core/composables/useVaultBoyFeedback'
import VaultBoySprite from '@/core/components/common/VaultBoySprite.vue'
import { FEEDBACK_TIMING_MS } from '@/core/config/feedback'
import {
  VAULT_BOY_ANIMATIONS,
  type VaultBoyAnimationId,
  type VaultBoyAnimation,
} from '@/core/utils/vaultBoyAnimations'

interface Preview {
  id: string
  definition: VaultBoyAnimation
  animationId: VaultBoyAnimationId
  sequence: number[]
  draft: string
  step: number
  pose: number
  playing: boolean
  error: string
}

const intervalMs = ref(FEEDBACK_TIMING_MS.vaultBoyFrame)

function createPreview(animationId: VaultBoyAnimationId): Preview {
  const definition = VAULT_BOY_ANIMATIONS[animationId]
  const sequence = [...definition.sequence]
  const preview = reactive<Preview>({
    id: animationId,
    animationId,
    definition,
    sequence,
    draft: sequence.join(', '),
    step: 0,
    pose: sequence[0]!,
    playing: false,
    error: '',
  })
  const { pause, resume } = useIntervalFn(
    () => {
      if (preview.step < preview.sequence.length - 1) seek(preview, preview.step + 1)
      else preview.playing = false
    },
    intervalMs,
    { immediate: false }
  )
  watch(
    () => preview.playing,
    (playing) => (playing ? resume() : pause())
  )
  return preview
}

const animationIds = Object.keys(VAULT_BOY_ANIMATIONS) as VaultBoyAnimationId[]
const previews = animationIds.map((animationId) => createPreview(animationId))
const sourceSheets = Object.values(VAULT_BOY_ANIMATIONS)

function previewCorner(preview: Preview) {
  useVaultBoyFeedback().show({
    animation: preview.animationId,
    title: preview.definition.title,
    message: 'Development preview — this is where game-event feedback appears.',
    vaultId: 'dev-preview',
  })
}

function seek(preview: Preview, step: number) {
  preview.step = step
  preview.pose = preview.sequence[step]!
}

function selectStep(preview: Preview, step: number) {
  preview.playing = false
  seek(preview, step)
}

function stepBy(preview: Preview, direction: number) {
  preview.playing = false
  seek(preview, (preview.step + direction + preview.sequence.length) % preview.sequence.length)
}

function selectPose(preview: Preview, pose: number) {
  preview.playing = false
  preview.pose = pose
  preview.step = -1
}

function togglePlay(preview: Preview) {
  if (preview.step < 0 || preview.step === preview.sequence.length - 1) seek(preview, 0)
  preview.playing = !preview.playing
}

function applySequence(preview: Preview) {
  const sequence = preview.draft.split(',').map((value) => Number(value.trim()))
  const frameCount = preview.definition.frames.length
  if (
    !/^\s*\d+(\s*,\s*\d+)*\s*$/.test(preview.draft) ||
    sequence.length > 64 ||
    sequence.some((pose) => pose < 0 || pose >= frameCount)
  ) {
    preview.error = `Use comma-separated pose numbers from 0 to ${frameCount - 1} (up to 64 steps).`
    return
  }
  preview.error = ''
  preview.playing = false
  preview.sequence = sequence
  seek(preview, 0)
}

function resetSequence(preview: Preview) {
  preview.draft = preview.definition.sequence.join(', ')
  applySequence(preview)
}
</script>

<template>
  <div class="mx-auto max-w-6xl space-y-8 px-4 py-8 sm:px-6">
    <header class="space-y-3">
      <h1 class="text-3xl font-bold text-theme-primary">Animation Gallery</h1>
      <p class="max-w-3xl text-sm leading-relaxed text-theme-primary/60">
        Inspect the character animations used for vault events. Play a sequence, step through it, or
        select a source pose below. Previews start paused and play once, holding the final pose.
        Sequence edits stay on this page.
      </p>
      <div class="flex flex-wrap items-center gap-2">
        <span class="mr-2 text-xs text-theme-primary/60">Playback speed</span>
        <Button
          v-for="speed in [
            { label: 'Slow', ms: 360 },
            { label: 'Normal', ms: FEEDBACK_TIMING_MS.vaultBoyFrame },
            { label: 'Fast', ms: 90 },
          ]"
          :key="speed.ms"
          :variant="intervalMs === speed.ms ? 'default' : 'outline'"
          :aria-pressed="intervalMs === speed.ms"
          size="sm"
          @click="intervalMs = speed.ms"
          >{{ speed.label }}</Button
        >
        <span class="text-xs text-theme-primary/60 tabular-nums">{{ intervalMs }} ms / step</span>
      </div>
    </header>

    <div class="grid items-start gap-6 lg:grid-cols-2">
      <section
        v-for="preview in previews"
        :key="preview.id"
        :aria-labelledby="`animation-${preview.id}`"
        class="min-w-0 overflow-hidden rounded-lg border border-theme-glow bg-surface"
      >
        <div class="flex items-center justify-between gap-3 border-b border-theme-glow px-4 py-3">
          <h2 :id="`animation-${preview.id}`" class="text-lg font-semibold text-theme-primary">
            {{ preview.definition.title }}
          </h2>
          <span class="text-xs text-theme-primary/60">{{
            preview.playing ? 'Playing' : 'Paused'
          }}</span>
        </div>

        <div class="flex flex-col items-center gap-3 bg-surface-sunken px-4 py-5">
          <VaultBoySprite
            :animation="preview.animationId"
            :definition="preview.definition"
            :pose="preview.pose"
            class="h-60 w-full max-w-72"
          />
          <p class="text-sm text-theme-primary tabular-nums">
            Pose {{ preview.pose }} ·
            {{
              preview.step < 0
                ? 'Source pose'
                : `Step ${preview.step + 1} / ${preview.sequence.length}`
            }}
          </p>
          <div class="flex flex-wrap justify-center gap-2">
            <Button variant="outline" size="sm" @click="stepBy(preview, -1)">Previous</Button>
            <Button size="sm" @click="togglePlay(preview)">{{
              preview.playing ? 'Pause' : 'Play'
            }}</Button>
            <Button variant="outline" size="sm" @click="stepBy(preview, 1)">Next</Button>
            <Button variant="ghost" size="sm" @click="previewCorner(preview)"
              >Show in corner</Button
            >
          </div>
        </div>

        <div class="space-y-5 p-4">
          <div class="space-y-2">
            <h3 class="text-sm font-semibold text-theme-primary">Playback order</h3>
            <div class="flex flex-wrap gap-1" aria-label="Playback steps">
              <Button
                v-for="(pose, index) in preview.sequence"
                :key="index"
                :variant="preview.step === index ? 'default' : 'outline'"
                size="xs"
                :aria-label="`Step ${index + 1}, pose ${pose}`"
                :aria-pressed="preview.step === index"
                @click="selectStep(preview, index)"
                >{{ pose }}</Button
              >
            </div>
            <label :for="`sequence-${preview.id}`" class="block text-xs text-theme-primary/60">
              Pose order (comma-separated; repeat a number to hold that pose)
            </label>
            <Input
              :id="`sequence-${preview.id}`"
              v-model="preview.draft"
              :maxlength="200"
              autocomplete="off"
            />
            <p v-if="preview.error" class="text-xs text-danger" role="alert">{{ preview.error }}</p>
            <div class="flex flex-wrap gap-2">
              <Button variant="outline" size="sm" @click="applySequence(preview)"
                >Apply order</Button
              >
              <Button variant="ghost" size="sm" @click="resetSequence(preview)">Reset order</Button>
            </div>
          </div>

          <div class="space-y-2">
            <h3 class="text-sm font-semibold text-theme-primary">Source poses</h3>
            <p class="text-xs text-theme-primary/60">
              Numbered by position in the sheet. Click a pose to inspect it.
            </p>
            <div class="grid grid-cols-4 gap-2">
              <div
                v-for="(_, index) in preview.definition.frames"
                :key="index"
                role="group"
                :aria-label="`Source pose ${index}`"
                class="relative flex min-w-0 justify-center pb-6"
              >
                <VaultBoySprite
                  :animation="preview.animationId"
                  :definition="preview.definition"
                  :pose="index"
                  class="size-20 max-w-full"
                />
                <Button
                  variant="outline"
                  class="absolute inset-0 h-full w-full items-end bg-transparent px-1 pb-1 hover:bg-theme-primary/5"
                  :aria-label="`Inspect pose ${index}`"
                  :aria-pressed="preview.pose === index"
                  @click="selectPose(preview, index)"
                >
                  <span class="text-xs">{{ index }}</span>
                </Button>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
    <section aria-labelledby="source-sheets" class="space-y-4">
      <div class="space-y-1">
        <h2 id="source-sheets" class="text-xl font-semibold text-theme-primary">
          All Vault Boy sheets
        </h2>
        <p class="text-sm text-theme-primary/60">
          Original files. Open a sheet at full size to inspect its layout.
        </p>
      </div>
      <div class="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <a
          v-for="sheet in sourceSheets"
          :key="sheet.sheet"
          :href="sheet.sheet"
          target="_blank"
          rel="noopener noreferrer"
          class="overflow-hidden rounded-lg border border-theme-glow bg-surface focus-visible:outline-2 focus-visible:outline-theme-primary"
        >
          <img
            :src="sheet.sheet"
            :alt="`${sheet.title} sprite sheet`"
            :width="sheet.sheetSize?.[0] ?? 2048"
            :height="sheet.sheetSize?.[1] ?? 1024"
            class="w-full bg-surface-sunken"
            loading="lazy"
          />
          <span class="block px-3 py-2 text-sm text-theme-primary">{{ sheet.title }} ↗</span>
        </a>
      </div>
    </section>
    <VaultBoyFeedback vault-id="dev-preview" />
  </div>
</template>
