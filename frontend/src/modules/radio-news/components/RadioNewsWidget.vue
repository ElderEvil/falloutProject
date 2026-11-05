<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from '@/core/components/ui/tooltip'
import { useToast } from '@/core/composables/useToast'
import { fetchRadioNews, regenerateRadioNews, type RadioNewsBroadcast } from '../api/radioNews'

const props = defineProps<{ vaultId: string }>()
const emit = defineEmits<{ newBroadcast: [broadcast: RadioNewsBroadcast] }>()
const toast = useToast()
const broadcast = ref<RadioNewsBroadcast | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const isPlaying = ref(false)
const audioEl = ref<HTMLAudioElement | null>(null)
const hasPlayed = ref(false)
const isRegenerating = ref(false)
let loadVersion = 0
let regenerateVersion = 0

const utcDayStart = () => {
  const now = new Date()
  return new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate()))
}
const parseUtcTimestamp = (value: string) =>
  new Date(/[zZ]|[+-]\d{2}:?\d{2}$/.test(value) ? value : `${value}Z`)
const today = ref(utcDayStart())

function isPlayedToday(broadcastId: string): boolean {
  try {
    return !!JSON.parse(localStorage.getItem('radio_news_played') || '{}')[broadcastId]
  } catch {
    return false
  }
}

function markPlayed(broadcastId: string): void {
  hasPlayed.value = true
  try {
    const played = JSON.parse(localStorage.getItem('radio_news_played') || '{}')
    played[broadcastId] = Date.now()
    localStorage.setItem('radio_news_played', JSON.stringify(played))
  } catch {
    // localStorage may be unavailable; ignore
  }
}

const isToday = computed(() => {
  if (!broadcast.value?.created_at) return false
  const created = parseUtcTimestamp(broadcast.value.created_at)
  return Date.UTC(created.getUTCFullYear(), created.getUTCMonth(), created.getUTCDate()) === today.value.getTime()
})
const isNew = computed(() => isToday.value && !hasPlayed.value)
const isAudioAvailable = computed(() => !!broadcast.value?.audio_url)
const hasScript = computed(() => !!broadcast.value?.script)
const showTextBroadcast = computed(() => !isAudioAvailable.value && hasScript.value)
const showCaption = computed(() => isPlaying.value && !!broadcast.value?.script)

const loadBroadcast = async () => {
  const requestVersion = ++loadVersion
  const requestedVaultId = props.vaultId
  isLoading.value = true
  error.value = null
  today.value = utcDayStart()
  try {
    const data = await fetchRadioNews(requestedVaultId)
    if (requestVersion !== loadVersion) return
    broadcast.value = data
    hasPlayed.value = data.id ? isPlayedToday(data.id) : false
    emit('newBroadcast', data)
  } catch (err) {
    if (requestVersion !== loadVersion) return
    toast.warning('Broadcast unavailable')
    error.value = err instanceof Error ? err.message : 'Failed to load broadcast'
  } finally {
    if (requestVersion === loadVersion) isLoading.value = false
  }
}

function stopAudio(): void {
  audioEl.value?.pause()
  audioEl.value = null
  isPlaying.value = false
}

function startAudio(url: string): HTMLAudioElement {
  stopAudio()
  const audio = new Audio(url)
  audioEl.value = audio
  isPlaying.value = true
  audio.onended = stopAudio
  audio.onerror = () => {
    stopAudio()
    toast.error('Unable to play audio')
  }
  return audio
}

async function playAudio(url: string): Promise<boolean> {
  try {
    await startAudio(url).play()
    return true
  } catch {
    stopAudio()
    toast.error('Unable to play audio')
    return false
  }
}

const onTogglePlay = async () => {
  const current = broadcast.value
  if (!current?.audio_url) return
  if (isPlaying.value) {
    stopAudio()
  } else if ((await playAudio(current.audio_url)) && current.id) {
    markPlayed(current.id)
  }
}

const onRegenerate = async () => {
  const current = broadcast.value
  if (!current || isRegenerating.value) return
  const requestVersion = ++regenerateVersion
  const requestedVaultId = props.vaultId
  isRegenerating.value = true
  stopAudio()
  try {
    const data = await regenerateRadioNews(requestedVaultId)
    if (requestVersion !== regenerateVersion) return
    broadcast.value = data
    hasPlayed.value = data.id ? isPlayedToday(data.id) : false
    emit('newBroadcast', data)
    toast.success('Broadcast regenerated')
  } catch (err) {
    if (requestVersion === regenerateVersion) {
      toast.error(err instanceof Error ? err.message : 'Unable to regenerate broadcast')
    }
  } finally {
    if (requestVersion === regenerateVersion) isRegenerating.value = false
  }
}

let midnightTimer: ReturnType<typeof setTimeout> | null = null

const scheduleNextMidnight = () => {
  if (midnightTimer) clearTimeout(midnightTimer)
  const now = new Date()
  const nextUtcMidnight = Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), now.getUTCDate() + 1)
  midnightTimer = setTimeout(
    () => {
      today.value = utcDayStart()
      void loadBroadcast()
      scheduleNextMidnight()
    },
    Math.max(0, nextUtcMidnight - now.getTime())
  )
}

watch(
  () => props.vaultId,
  () => {
    regenerateVersion += 1
    isRegenerating.value = false
    stopAudio()
    broadcast.value = null
    error.value = null
    void loadBroadcast()
  }
)

onMounted(() => {
  void loadBroadcast()
  scheduleNextMidnight()
})

onBeforeUnmount(() => {
  stopAudio()
  if (midnightTimer) clearTimeout(midnightTimer)
})
</script>

<template>
  <div class="radio-news-widget flex flex-col gap-2">
    <!-- Loading state -->
    <div v-if="isLoading" class="radio-news-widget__loading flex items-center gap-2" aria-label="Loading broadcast">
      <div class="skeleton skeleton--pill h-5 w-24 animate-pulse rounded-full bg-surface-hover" />
      <span class="radio-news-widget__loading-text text-xs text-theme-primary">Loading…</span>
    </div>

    <!-- Error state -->
    <div v-else-if="error && !broadcast" class="radio-news-widget__error flex items-center gap-2" aria-label="Broadcast error">
      <Icon icon="mdi:alert-circle-outline" class="radio-news-widget__error-icon h-4 w-4 text-danger" />
      <span class="radio-news-widget__error-text text-xs text-danger">{{ error }}</span>
    </div>

    <!-- Broadcast present (normal mode) -->
    <div v-else-if="broadcast" class="radio-news-widget__content">
      <!-- Badge -->
      <TooltipProvider :delay-duration="200">
        <Tooltip>
          <TooltipTrigger as-child>
            <Badge
              variant="outline"
              class="radio-news-widget__badge cursor-default border-theme-primary/20 bg-theme-primary/5"
              :class="{ 'border-theme-primary/60 bg-theme-primary/15 animate-pulse': isNew }"
            >
              <Icon icon="mdi:radio" class="radio-news-widget__badge-icon h-3.5 w-3.5" />
              <span class="radio-news-widget__badge-text text-[0.6rem] font-bold uppercase tracking-widest">
                {{ isNew ? 'New Broadcast' : 'Radio' }}
              </span>
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <span v-if="isNew">New broadcast available — click to play</span>
            <span v-else>Tune in to the radio news</span>
          </TooltipContent>
        </Tooltip>
      </TooltipProvider>

      <!-- Text-only broadcast panel (audio unavailable but script exists) -->
      <div
        v-if="showTextBroadcast"
        class="radio-news-widget__text-panel mt-2 max-w-xs rounded-md border border-theme-primary/20 bg-surface-raised/80 p-3 shadow-sm"
      >
        <div class="radio-news-widget__text-panel-header mb-1 flex items-center gap-2">
          <Icon icon="mdi:radio" class="radio-news-widget__text-panel-icon h-4 w-4 text-theme-primary" />
          <h4 class="radio-news-widget__text-panel-title m-0 text-xs font-bold uppercase text-theme-primary">
            {{ broadcast.title || 'Radio Broadcast' }}
          </h4>
        </div>
        <p class="radio-news-widget__text-panel-script whitespace-pre-wrap text-[0.7rem] leading-normal text-theme-primary/80">
          {{ broadcast.script }}
        </p>
        <div class="radio-news-widget__text-panel-meta mt-2 text-[0.6rem] text-theme-primary/50">
          {{ broadcast.created_at ? new Date(broadcast.created_at).toLocaleString() : 'Audio unavailable' }}
        </div>
      </div>

      <!-- Playback and regeneration controls -->
      <div v-if="broadcast" class="flex items-center gap-2">
        <div v-if="isAudioAvailable" class="radio-news-widget__play-controls animate-pulse">
          <Button
            variant="outline"
            size="sm"
            class="radio-news-widget__play-btn border-theme-primary/30"
            :class="{ 'bg-theme-primary/20': isPlaying }"
            @click="onTogglePlay"
          >
            <Icon
              :icon="isPlaying ? 'mdi:pause' : 'mdi:play'"
              class="radio-news-widget__play-icon h-4 w-4"
            />
            <span class="radio-news-widget__play-text text-xs font-semibold">
              {{ isPlaying ? 'Stop' : 'Play' }}
            </span>
          </Button>
        </div>
        <Button
          variant="outline"
          size="sm"
          class="radio-news-widget__regenerate-btn border-theme-primary/30"
          :disabled="isRegenerating"
          @click="onRegenerate"
        >
          <Icon
            :icon="isRegenerating ? 'mdi:loading' : 'mdi:refresh'"
            class="h-4 w-4"
            :class="{ 'animate-spin': isRegenerating }"
          />
          <span class="text-xs font-semibold">Regenerate</span>
        </Button>
      </div>
    </div>

    <!-- Caption overlay while playing -->
    <div
      v-if="showCaption"
      class="radio-news-widget__caption mt-2 max-w-xs rounded-md border border-theme-primary/30 bg-surface-warm/90 p-3 shadow-sm"
      aria-live="polite"
    >
      <div class="radio-news-widget__caption-header mb-1 flex items-center gap-2">
        <Icon icon="mdi:radio" class="radio-news-widget__caption-icon h-4 w-4 animate-pulse text-theme-primary" />
        <h4 class="radio-news-widget__caption-title m-0 text-xs font-bold uppercase text-theme-primary">
          {{ broadcast?.title || 'Radio Broadcast' }}
        </h4>
      </div>
      <p class="radio-news-widget__caption-script whitespace-pre-wrap text-[0.7rem] leading-normal text-theme-primary">
        {{ broadcast?.script }}
      </p>
    </div>
  </div>
</template>
