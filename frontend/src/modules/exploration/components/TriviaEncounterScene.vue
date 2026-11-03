<script setup lang="ts">
import { computed } from 'vue'
import { Icon } from '@iconify/vue'
import { Button } from '@/core/components/ui/button'
import DwellerPortrait from '@/modules/dwellers/components/DwellerPortrait.vue'
import { useFallbackImage } from '@/modules/rooms/composables/useFallbackImage'
import { getStaticImageUrl } from '@/core/utils/image'
import { WASTELAND_SCENES, widestSceneImage } from '../models/wastelandScenes'
import { pickRaiderPose, raiderVarietySeed } from '../models/raiderPoses'
import type { SiteRoomView } from '../api/expeditionSite'

interface Props {
  room: SiteRoomView
  dwellerName?: string
  dwellerImageUrl?: string | null
  dwellerThumbnailUrl?: string | null
  busy?: boolean
}

const props = withDefaults(defineProps<Props>(), {
  dwellerName: 'Dweller',
  dwellerImageUrl: null,
  dwellerThumbnailUrl: null,
  busy: false,
})

const emit = defineEmits<{
  answer: [id: string]
}>()

const artwork = computed(() => (props.room.scene_id ? WASTELAND_SCENES[props.room.scene_id] : null))
const variants = computed(() => artwork.value?.landscape.variants ?? [])
const fullImage = computed(() => widestSceneImage(variants.value))
const sceneSrcset = computed(() =>
  variants.value.map((image) => `${image.src} ${image.width}w`).join(', ')
)
const { url: sceneImage, onError: sceneFailed } = useFallbackImage(() => [fullImage.value?.src])

// Pick the seeded pose, with the other pose as a graceful fallback.
const raiderCandidates = computed(() => {
  const node = props.room.node
  const pose = { image_url: node.raider_image_url, alt_image_url: node.raider_alt_image_url }
  const primary = pickRaiderPose(
    pose,
    raiderVarietySeed(props.room.exploration_id, props.room.site_id)
  )
  const alternate = [pose.image_url, pose.alt_image_url].find((url) => url && url !== primary)
  return [getStaticImageUrl(primary), getStaticImageUrl(alternate)]
})
const { url: raiderImage, onError: raiderFailed } = useFallbackImage(() => raiderCandidates.value)

const raiderName = computed(() => props.room.node.enemy_names?.[0] || 'Raider')
const questionIndex = computed(() => props.room.node.question_index ?? 1)
const questionTotal = computed(() => props.room.node.question_total ?? 1)
const options = computed(() => props.room.node.options ?? [])
const outcomeText = computed(() =>
  props.room.status === 'in_room' ? (props.room.outcome?.text ?? null) : null
)
const enemySummary = computed(() => {
  const counts = new Map<string, number>()
  for (const name of props.room.node.enemy_names ?? []) {
    counts.set(name, (counts.get(name) ?? 0) + 1)
  }
  return [...counts.entries()].map(([name, n]) => (n > 1 ? `${name} ×${n}` : name)).join(', ')
})

const answer = (id: string) => {
  if (!props.busy) emit('answer', id)
}
</script>

<template>
  <div class="relative flex h-full min-h-0 flex-col md:block" aria-label="Trivia encounter">
    <section
      class="relative min-h-0 flex-1 overflow-hidden bg-surface-sunken md:h-full"
      :aria-label="`${raiderName} posing a question`"
    >
      <img
        v-if="fullImage && sceneImage"
        :src="sceneImage"
        :srcset="sceneSrcset"
        sizes="(max-width: 768px) calc(100vw - 32px), 960px"
        :width="fullImage.width"
        :height="fullImage.height"
        :alt="artwork?.label ?? room.site_name"
        class="absolute inset-0 h-full w-full object-cover object-[50%_18%]"
        decoding="async"
        @error="sceneFailed"
      />
      <div
        v-else
        class="absolute inset-0 flex items-center justify-center text-theme-primary/60"
        role="img"
        :aria-label="artwork?.label ?? room.site_name"
      >
        <Icon icon="mdi:compass-outline" class="h-12 w-12" />
      </div>

      <!-- Progress, threat and result chips -->
      <div
        class="absolute top-3 left-3 z-20 flex max-w-[min(20rem,60%)] flex-col items-start gap-2 md:max-w-[min(20rem,30%)]"
      >
        <span
          class="rounded-full border border-theme-primary/60 bg-surface-sunken px-3 py-1 text-[0.6875rem] font-bold tracking-widest text-theme-primary"
          :aria-label="`Question ${questionIndex} of ${questionTotal}`"
        >
          QUESTION {{ questionIndex }} / {{ questionTotal }}
        </span>
        <span
          v-if="enemySummary"
          class="rounded-md border border-warning/40 bg-surface-sunken px-2 py-1 text-[0.6875rem] font-semibold text-warning"
        >
          If it goes wrong: {{ enemySummary }}
        </span>
        <span
          v-if="outcomeText"
          class="rounded-md border border-theme-primary/40 bg-surface-sunken px-2 py-1 text-[0.6875rem] leading-relaxed text-theme-primary/90"
        >
          {{ outcomeText }}
        </span>
      </div>

      <!-- Dweller, bottom-left, facing the raider -->
      <div
        v-if="dwellerImageUrl || dwellerThumbnailUrl"
        class="actor-ground-shadow absolute bottom-[6%] left-[5%] z-10 h-[56%] aspect-[1/2]"
        role="group"
        :aria-label="`${dwellerName} facing the raider`"
      >
        <DwellerPortrait
          :image-url="dwellerImageUrl"
          :thumbnail-url="dwellerThumbnailUrl"
          :alt="dwellerName"
          prefer-thumbnail
          :zoom="false"
          class="block h-full w-full drop-shadow-[0_4px_3px_rgba(0,0,0,0.6)]"
          image-class="h-full w-full object-contain"
          fallback-class="h-full w-full text-theme-primary"
          fallback-icon="mdi:account"
        />
      </div>

      <!-- Raider stands inside the scene, bottom-right, facing viewer-left -->
      <img
        v-if="raiderImage"
        :src="raiderImage"
        alt="Raider posing the question"
        class="absolute right-[5%] bottom-[2%] z-10 h-[64%] w-auto max-w-[40%] object-contain drop-shadow-[0_6px_6px_rgba(0,0,0,0.55)]"
        decoding="async"
        @error="raiderFailed"
      />
      <div
        v-else
        class="absolute right-[6%] bottom-[8%] z-10 flex h-[40%] aspect-[1/2] items-center justify-center text-theme-primary/40"
        role="img"
        aria-label="Raider posing the question"
      >
        <Icon icon="mdi:account-alert-outline" class="h-16 w-16" />
      </div>

      <!-- Question bubble, anchored upper-left of the raider -->
      <div
        class="absolute right-3 bottom-3 left-3 z-20 md:top-[18%] md:right-[20%] md:bottom-auto md:left-auto md:max-w-[36%]"
      >
        <div
          class="relative rounded-lg border-2 border-theme-primary/70 bg-surface-sunken/95 p-3 shadow-lg md:p-4"
        >
          <p class="text-[0.6875rem] font-bold tracking-widest text-theme-primary/80 uppercase">
            {{ raiderName }}
          </p>
          <p
            v-if="room.node.prompt"
            class="mt-1 hidden text-xs leading-relaxed text-theme-primary/70 md:block"
          >
            {{ room.node.prompt }}
          </p>
          <p
            v-if="room.node.question"
            class="mt-2 text-base leading-snug font-bold text-theme-primary terminal-glow"
            aria-live="polite"
          >
            {{ room.node.question }}
          </p>
          <span
            class="absolute top-[62%] -right-2 hidden h-4 w-4 rotate-45 border-t-2 border-r-2 border-theme-primary/70 bg-surface-sunken md:block"
            aria-hidden="true"
          ></span>
        </div>
      </div>
    </section>

    <!-- Answers: overlay on desktop, solid panel below the scene on phones -->
    <div
      class="z-20 shrink-0 border-t border-theme-primary/25 bg-surface-sunken p-3 md:absolute md:bottom-[7%] md:left-[16%] md:w-[min(27rem,34%)] md:border-0 md:bg-transparent md:p-0"
      :aria-busy="busy"
      aria-label="Answer options"
    >
      <div class="flex flex-col gap-2">
        <Button
          v-for="option in options"
          :key="option.id"
          variant="ghost"
          size="lg"
          type="button"
          :disabled="busy"
          class="relative h-auto w-full justify-start rounded-lg border-2 border-theme-primary/70 bg-surface-sunken px-4 py-2.5 text-left text-sm font-semibold text-theme-primary hover:border-theme-primary hover:bg-theme-primary/15 focus-visible:outline focus-visible:outline-2 focus-visible:outline-ring disabled:cursor-not-allowed disabled:opacity-60 motion-reduce:transition-none"
          @click="answer(option.id)"
        >
          <span
            class="pointer-events-none absolute top-1/2 -left-2 h-3 w-3 -translate-y-1/2 rotate-45 border-b-2 border-l-2 border-theme-primary/70 bg-surface-sunken"
            aria-hidden="true"
          ></span>
          {{ option.label }}
        </Button>
      </div>
      <p
        v-if="busy"
        class="mt-2 flex items-center gap-2 text-xs font-semibold text-theme-primary/70"
        role="status"
      >
        <Icon icon="mdi:loading" class="h-4 w-4 animate-spin motion-reduce:animate-none" />
        Checking your answer…
      </p>
    </div>
  </div>
</template>
