<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
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
import {
  fetchRadioNews,
  type RadioNewsBroadcast,
} from '../api/radioNews'

interface Props {
  vaultId: string
}

const props = defineProps<Props>()

const emit = defineEmits<{
  newBroadcast: [broadcast: RadioNewsBroadcast]
}>()

const toast = useToast()
const broadcast = ref<RadioNewsBroadcast | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const isPlaying = ref(false)
const audioEl = ref<HTMLAudioElement | null>(null)

// Welcome panel state
const showWelcomePanel = ref(false)
const welcomeBlocked = ref(false)

const today = new Date()
today.setHours(0, 0, 0, 0)

/** Check if a broadcast has been played this session. */
function isPlayedToday(broadcastId: string): boolean {
  try {
    const played = JSON.parse(localStorage.getItem('radio_news_played') || '{}')
    return !!played[broadcastId]
  } catch {
    return false
  }
}

/** Mark a broadcast as played this session. */
function markPlayed(broadcastId: string): void {
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
  const created = new Date(broadcast.value.created_at)
  created.setHours(0, 0, 0, 0)
  return created.getTime() === today.getTime()
})

const isAudioAvailable = computed(() => !!broadcast.value?.audio_url)
const hasScript = computed(() => !!broadcast.value?.script && broadcast.value.script.length > 0)
const showTextBroadcast = computed(
  () => !isAudioAvailable.value && hasScript.value
)
const showCaption = computed(
  () => isPlaying.value && broadcast.value?.script
)

const loadBroadcast = async () => {
  isLoading.value = true
  error.value = null
  try {
    const data = await fetchRadioNews(props.vaultId)
    broadcast.value = data
    emit('newBroadcast', data)

    // After loading, attempt auto-play for today's unplayed broadcast
    if (isToday.value && data.audio_url && data.id && !isPlayedToday(data.id)) {
      await attemptAutoPlay(data)
    }
  } catch (err) {
    toast.warning('Broadcast unavailable')
    error.value = err instanceof Error ? err.message : 'Failed to load broadcast'
  } finally {
    isLoading.value = false
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

async function attemptAutoPlay(b: RadioNewsBroadcast): Promise<void> {
  if (!b.audio_url || !b.id) return
  let audio: HTMLAudioElement
  try {
    audio = startAudio(b.audio_url)
  } catch {
    return
  }
  try {
    await audio.play()
    markPlayed(b.id)
  } catch {
    stopAudio()
    showWelcomePanel.value = true
    welcomeBlocked.value = true
  }
}

const onTogglePlay = () => {
  if (!broadcast.value?.audio_url) return
  if (isPlaying.value) stopAudio()
  else void playAudio(broadcast.value.audio_url)
}

const onWelcomePanelPlay = async () => {
  const b = broadcast.value
  if (!b?.audio_url || !b.id) return
  welcomeBlocked.value = false
  showWelcomePanel.value = false
  if (await playAudio(b.audio_url)) markPlayed(b.id)
}

// Periodically refresh at midnight to pick up new broadcasts
let midnightTimer: ReturnType<typeof setTimeout> | null = null

const scheduleNextMidnight = () => {
  if (midnightTimer) clearTimeout(midnightTimer)
  const now = Date.now()
  const tomorrow = new Date(today)
  tomorrow.setDate(tomorrow.getDate() + 1)
  tomorrow.setHours(0, 0, 0, 0)
  const delay = tomorrow.getTime() - now
  if (delay > 0) {
    midnightTimer = setTimeout(loadBroadcast, delay)
  }
}

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

    <!-- Welcome panel: unplayed today broadcast with blocked autoplay -->
    <div
      v-if="showWelcomePanel && broadcast"
      class="radio-news-widget__welcome-panel mt-2 rounded-md border border-theme-primary/30 bg-surface-warm/90 p-4 shadow-lg"
    >
      <div class="radio-news-widget__welcome-header mb-3 flex items-center gap-2">
        <Icon icon="mdi:radio" class="radio-news-widget__welcome-icon h-5 w-5 text-theme-primary" />
        <h3 class="radio-news-widget__welcome-title m-0 text-sm font-bold uppercase tracking-widest text-theme-primary">
          📻 Vault Radio Hour
        </h3>
      </div>
      <p class="radio-news-widget__welcome-script mb-3 whitespace-pre-wrap text-xs leading-relaxed text-theme-primary/80">
        {{ broadcast.script }}
      </p>
      <Button
        variant="outline"
        size="sm"
        class="radio-news-widget__welcome-play-btn w-full"
        @click="onWelcomePanelPlay"
      >
        <Icon icon="mdi:play-circle-outline" class="radio-news-widget__welcome-play-icon mr-1.5 h-4 w-4" />
        Tap to listen
      </Button>
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
              :class="{ 'border-theme-primary/60 bg-theme-primary/15 animate-pulse': isToday }"
            >
              <Icon icon="mdi:radio" class="radio-news-widget__badge-icon h-3.5 w-3.5" />
              <span class="radio-news-widget__badge-text text-[0.6rem] font-bold uppercase tracking-widest">
                {{ isToday ? 'New Broadcast' : 'Radio' }}
              </span>
            </Badge>
          </TooltipTrigger>
          <TooltipContent>
            <span v-if="isToday">New broadcast available — click to play</span>
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

      <!-- Play button (audio available) -->
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
