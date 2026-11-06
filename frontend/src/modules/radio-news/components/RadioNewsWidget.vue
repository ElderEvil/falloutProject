<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, onMounted, ref, shallowRef, watch } from 'vue'
import { Icon } from '@iconify/vue'
import { onClickOutside, useLocalStorage } from '@vueuse/core'
import { Badge } from '@/core/components/ui/badge'
import { Button } from '@/core/components/ui/button'
import { Slider } from '@/core/components/ui/slider'
import { useToast } from '@/core/composables/useToast'
import { fetchRadioNews, regenerateRadioNews, type RadioNewsBroadcast } from '../api/radioNews'

const props = defineProps<{ vaultId: string; inline?: boolean }>()
const isInline = computed(() => props.inline ?? false)
const emit = defineEmits<{ newBroadcast: [broadcast: RadioNewsBroadcast] }>()
const toast = useToast()
const broadcast = ref<RadioNewsBroadcast | null>(null)
const isLoading = ref(true)
const error = ref<string | null>(null)
const isPlaying = ref(false)
const audioEl = shallowRef<HTMLAudioElement | null>(null)
const volume = useLocalStorage('radio_news_volume', 75, {
  serializer: {
    read: (value) => {
      const percent = Number.parseFloat(value)
      return Number.isFinite(percent) ? Math.min(100, Math.max(0, percent)) : 75
    },
    write: String,
  },
})
const lastAudibleVolume = ref(volume.value || 75)
const isPaused = computed(() => audioEl.value !== null && !isPlaying.value)
const playLabel = computed(() => (isPlaying.value ? 'Pause' : isPaused.value ? 'Resume' : 'Play'))
const hasPlayed = ref(false)
const isRegenerating = ref(false)
const isOpen = ref(false)
const rootRef = ref<HTMLElement | null>(null)
const triggerRef = ref<InstanceType<typeof Button> | null>(null)
const panelRef = ref<HTMLElement | null>(null)
let loadVersion = 0
let regenerateVersion = 0
let playbackVersion = 0

const DIAL_TICKS = Array.from({ length: 25 }, (_, index) => index + 1)
// Floating mode docks the tuner at the bottom-right; inline mode renders a
// compact trigger that lives inside the bottom control bar, next to the clock.
const FLOATING_TOGGLE_CLASS =
  'fixed bottom-24 right-4 z-50 flex h-auto w-[min(26rem,calc(100vw-2rem))] items-center justify-between gap-2 rounded-lg border-2 border-theme-primary/40 bg-surface-warm/95 px-3 py-2 text-theme-primary shadow-lg transition-colors hover:border-theme-primary hover:bg-surface-raised focus-visible:ring-2 focus-visible:ring-theme-primary focus-visible:ring-offset-2 focus-visible:ring-offset-surface-warm sm:right-6'
const INLINE_TOGGLE_CLASS =
  'flex h-auto shrink-0 items-center gap-2 rounded border border-theme-primary/30 px-3 py-1 text-theme-primary transition-colors hover:border-theme-primary/60 hover:bg-theme-primary/10'
const FLOATING_PANEL_CLASS =
  'fixed bottom-40 right-4 z-50 max-h-[calc(100vh-11rem)] w-[min(26rem,calc(100vw-2rem))] overflow-y-auto rounded-lg border-2 border-theme-primary/40 bg-surface-warm/95 shadow-2xl focus:outline-none motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 sm:right-6'
// Inline mode has no floating trigger, so the console sits just above the control bar.
const INLINE_PANEL_CLASS =
  'fixed bottom-24 right-4 z-50 max-h-[calc(100vh-8rem)] w-[min(26rem,calc(100vw-2rem))] overflow-y-auto rounded-lg border-2 border-theme-primary/40 bg-surface-warm/95 shadow-2xl focus:outline-none motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-bottom-2 sm:right-6'
const SIGNAL_BARS = [
  { key: 'one', height: 'h-1' },
  { key: 'two', height: 'h-1.5' },
  { key: 'three', height: 'h-2' },
  { key: 'four', height: 'h-2.5' },
] as const

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
  return (
    Date.UTC(created.getUTCFullYear(), created.getUTCMonth(), created.getUTCDate()) ===
    today.value.getTime()
  )
})
const isNew = computed(() => isToday.value && !hasPlayed.value)
const isAudioAvailable = computed(() => !!broadcast.value?.audio_url)
const hasScript = computed(() => !!broadcast.value?.script)
const showTextBroadcast = computed(() => !isAudioAvailable.value && hasScript.value)
const title = computed(() => broadcast.value?.title?.trim() || 'Vault Radio Hour')
const broadcastDate = computed(() => {
  const createdAt = broadcast.value?.created_at
  if (!createdAt) return 'Awaiting transmission'
  return parseUtcTimestamp(createdAt).toLocaleDateString(undefined, {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
  })
})
const toggleLabel = computed(() =>
  isOpen.value ? 'Close the vault radio' : 'Open the vault radio'
)

const loadBroadcast = async () => {
  const requestVersion = ++loadVersion
  const requestedVaultId = props.vaultId
  isLoading.value = true
  error.value = null
  today.value = utcDayStart()
  try {
    const data = await fetchRadioNews(requestedVaultId)
    if (requestVersion !== loadVersion) return
    if (broadcast.value?.id !== data.id) stopAudio()
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
  playbackVersion += 1
  if (audioEl.value) {
    audioEl.value.onended = null
    audioEl.value.onerror = null
    audioEl.value.pause()
  }
  audioEl.value = null
  isPlaying.value = false
}

function startAudio(url: string): HTMLAudioElement {
  stopAudio()
  const audio = new Audio(url)
  audio.volume = volume.value / 100
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
  const audio = audioEl.value ?? startAudio(url)
  const requestVersion = ++playbackVersion
  isPlaying.value = true
  try {
    await audio.play()
    return requestVersion === playbackVersion && audioEl.value === audio && isPlaying.value
  } catch {
    if (requestVersion === playbackVersion && audioEl.value === audio && isPlaying.value) {
      stopAudio()
      toast.error('Unable to play audio')
    }
    return false
  }
}

const onTogglePlay = async () => {
  const current = broadcast.value
  if (!current?.audio_url) return
  if (isPlaying.value) {
    playbackVersion += 1
    audioEl.value?.pause()
    isPlaying.value = false
  } else if ((await playAudio(current.audio_url)) && current.id) {
    markPlayed(current.id)
  }
}

function replayAudio(): void {
  if (!audioEl.value) return
  audioEl.value.currentTime = 0
  if (!isPlaying.value) void onTogglePlay()
}

function setVolume(values: number[] | undefined): void {
  if (values?.[0] !== undefined) volume.value = values[0]
}

watch(
  volume,
  (value, previous) => {
    if (previous > 0) lastAudibleVolume.value = previous
    if (audioEl.value) audioEl.value.volume = value / 100
  },
  { flush: 'sync' }
)

function toggleMute(): void {
  volume.value = volume.value > 0 ? 0 : lastAudibleVolume.value
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

function openPanel(): void {
  isOpen.value = true
  void nextTick(() => panelRef.value?.focus())
}

function closePanel(returnFocus = true): void {
  if (!isOpen.value) return
  isOpen.value = false
  if (returnFocus) void nextTick(() => (triggerRef.value?.$el as HTMLElement | undefined)?.focus())
}

const togglePanel = () => {
  if (isOpen.value) closePanel()
  else openPanel()
}

// The panel is non-modal, so Escape and a click outside both dismiss it.
const onKeydown = (event: KeyboardEvent) => {
  if (event.key === 'Escape' && isOpen.value) closePanel()
}

onClickOutside(rootRef, () => {
  if (isOpen.value) closePanel(false)
})

// A transcript-only broadcast has nothing to play, so an open console counts it
// as read. Watch the broadcast too: it can arrive or change while the panel is open.
watch([isOpen, broadcast], ([open, current]) => {
  if (
    open &&
    current?.id &&
    isToday.value &&
    !hasPlayed.value &&
    !current.audio_url &&
    current.script
  ) {
    markPlayed(current.id)
  }
})

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
  document.addEventListener('keydown', onKeydown)
  void loadBroadcast()
  scheduleNextMidnight()
})

onBeforeUnmount(() => {
  document.removeEventListener('keydown', onKeydown)
  stopAudio()
  if (midnightTimer) clearTimeout(midnightTimer)
})
</script>

<template>
  <div ref="rootRef" class="radio-news-widget">
    <!-- Tuner trigger: the only thing that lives in the HUD, so the control bar stays compact. -->
    <Button
      ref="triggerRef"
      type="button"
      variant="ghost"
      size="sm"
      class="radio-news-widget__toggle"
      :class="[
        isInline ? INLINE_TOGGLE_CLASS : FLOATING_TOGGLE_CLASS,
        { 'border-theme-primary shadow-glow-sm': isNew },
      ]"
      :aria-expanded="isOpen"
      aria-controls="radio-news-panel"
      :aria-label="toggleLabel"
      @click="togglePanel"
    >
      <span class="flex min-w-0 items-center gap-2">
        <span
          class="relative flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-theme-primary/40 bg-surface-sunken"
        >
          <Icon icon="mdi:radio" class="h-4 w-4" />
          <span
            v-if="isPlaying || isNew"
            class="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full motion-reduce:animate-none"
            :class="isPlaying ? 'bg-danger animate-pulse' : 'bg-theme-primary animate-pulse'"
            aria-hidden="true"
          />
        </span>

        <span v-if="isLoading" class="radio-news-widget__loading flex items-center gap-2">
          <span
            class="h-2 w-12 animate-pulse rounded-full bg-theme-primary/30 motion-reduce:animate-none"
          />
          <span class="text-[0.6rem] font-bold uppercase tracking-[0.2em] text-theme-primary/70">
            Tuning
          </span>
        </span>
        <span
          v-else-if="error && !broadcast"
          class="radio-news-widget__error flex max-w-[10rem] items-center gap-1 text-xs text-danger"
          :aria-label="error"
        >
          <Icon icon="mdi:alert-circle-outline" class="h-4 w-4 shrink-0" />
          <span class="truncate">{{ error }}</span>
        </span>
        <span v-else class="radio-news-widget__badge flex flex-col items-start leading-none">
          <span
            class="text-[0.55rem] font-bold uppercase tracking-[0.22em]"
            :class="isNew ? 'text-theme-primary' : 'text-theme-primary/60'"
          >
            {{ isNew ? 'New Broadcast' : 'Radio' }}
          </span>
        </span>
        <span
          v-if="!isLoading && broadcast && !isInline"
          class="hidden max-w-[11rem] truncate text-[0.65rem] font-semibold sm:block"
        >
          {{ isPlaying ? 'On air' : isPaused ? 'Paused' : title }}
        </span>
      </span>

      <Icon
        :icon="isOpen ? 'mdi:chevron-down' : 'mdi:chevron-up'"
        class="h-4 w-4 shrink-0 text-theme-primary/50"
      />
    </Button>

    <!-- Vintage receiver console, anchored above the control bar. -->
    <aside
      v-show="isOpen"
      id="radio-news-panel"
      ref="panelRef"
      tabindex="-1"
      role="region"
      aria-label="Vault Radio Hour broadcast"
      class="radio-news-widget__panel"
      :class="isInline ? INLINE_PANEL_CLASS : FLOATING_PANEL_CLASS"
    >
      <header
        class="flex items-center justify-between gap-3 border-b border-theme-primary/20 bg-surface-sunken/70 px-4 py-2"
      >
        <div class="flex min-w-0 items-center gap-2">
          <span
            class="h-2 w-2 shrink-0 rounded-full motion-reduce:animate-none"
            :class="
              isPlaying
                ? 'bg-danger animate-pulse'
                : isNew
                  ? 'bg-theme-primary animate-pulse'
                  : 'bg-theme-primary/30'
            "
            aria-hidden="true"
          />
          <Icon icon="mdi:radio-tower" class="h-4 w-4 shrink-0 text-theme-primary" />
          <span
            class="truncate text-[0.6rem] font-bold uppercase tracking-[0.3em] text-theme-primary"
          >
            Vault Radio Hour
          </span>
        </div>
        <div class="flex shrink-0 items-center gap-2">
          <div class="flex items-end gap-0.5" aria-hidden="true">
            <span
              v-for="(bar, index) in SIGNAL_BARS"
              :key="bar.key"
              class="w-0.5 rounded-sm transition-colors"
              :class="[
                bar.height,
                isPlaying || index < 2 ? 'bg-theme-primary/70' : 'bg-theme-primary/20',
              ]"
            />
          </div>
          <span class="text-[0.55rem] uppercase tracking-widest text-theme-primary/50">
            {{ isPlaying ? 'On air' : isPaused ? 'Paused' : 'Standby' }}
          </span>
          <Button
            type="button"
            variant="ghost"
            size="icon-sm"
            class="radio-news-widget__close rounded text-theme-primary/60 transition-colors hover:bg-theme-primary/10 hover:text-theme-primary"
            aria-label="Close the vault radio"
            @click="closePanel()"
          >
            <Icon icon="mdi:close" class="h-4 w-4" />
          </Button>
        </div>
      </header>

      <div
        v-if="isLoading"
        class="flex items-center gap-2 px-4 py-6 text-xs uppercase tracking-widest text-theme-primary/60"
      >
        <Icon icon="mdi:loading" class="h-4 w-4 animate-spin" />
        Receiving transmission
      </div>

      <div v-else-if="error && !broadcast" class="space-y-3 px-4 py-5">
        <p class="radio-news-widget__error-text m-0 text-xs leading-relaxed text-danger">
          {{ error }}
        </p>
        <Button variant="outline" size="sm" class="radio-news-widget__retry" @click="loadBroadcast">
          <Icon icon="mdi:refresh" class="h-4 w-4" />
          <span>Retry</span>
        </Button>
      </div>

      <template v-else-if="broadcast">
        <div class="space-y-3 px-4 py-3">
          <div class="flex items-start justify-between gap-3">
            <div class="min-w-0">
              <h3
                class="radio-news-widget__title m-0 truncate font-mono text-sm font-bold uppercase tracking-wide text-theme-primary"
                :class="{ 'terminal-glow': isPlaying }"
              >
                {{ title }}
              </h3>
              <p class="m-0 mt-0.5 text-[0.6rem] uppercase tracking-widest text-theme-primary/50">
                {{ broadcastDate }}
              </p>
            </div>
            <Badge
              v-if="isNew"
              variant="outline"
              class="shrink-0 border-theme-primary/50 bg-theme-primary/10 px-2 py-0.5 text-[0.55rem] font-bold uppercase tracking-widest text-theme-primary"
            >
              New
            </Badge>
          </div>

          <!-- Tuning dial: the needle slides while the broadcast plays. -->
          <div
            class="radio-news-widget__dial relative overflow-hidden rounded border border-theme-primary/20 bg-surface-sunken/70 px-3 pb-1 pt-2"
            aria-hidden="true"
          >
            <div class="flex items-end justify-between gap-px">
              <span
                v-for="tick in DIAL_TICKS"
                :key="tick"
                class="w-px bg-theme-primary/40"
                :class="tick % 5 === 0 ? 'h-3' : 'h-1.5'"
              />
            </div>
            <div class="relative mt-1 h-4">
              <span
                class="absolute top-0 h-4 w-px bg-danger transition-all duration-700"
                :class="isPlaying ? 'left-[62%]' : 'left-[38%]'"
              />
              <div
                class="flex justify-between text-[0.5rem] uppercase tracking-widest text-theme-primary/40"
              >
                <span>530</span>
                <span>1000</span>
                <span>1600</span>
              </div>
            </div>
          </div>

          <div class="flex items-stretch gap-2">
            <Button
              v-if="isAudioAvailable"
              variant="outline"
              size="sm"
              class="radio-news-widget__play-btn flex-1 border-theme-primary/40"
              :class="{ 'bg-theme-primary/15': isPlaying }"
              :aria-label="`${playLabel} broadcast`"
              :disabled="isRegenerating"
              @click="onTogglePlay"
            >
              <Icon
                :icon="isPlaying ? 'mdi:pause' : 'mdi:play'"
                v-bind="{ 'data-icon': 'inline-start' }"
              />
              <span class="text-xs font-semibold">{{ playLabel }}</span>
            </Button>
            <Button
              v-if="isAudioAvailable"
              variant="outline"
              size="icon-sm"
              class="border-theme-primary/30"
              aria-label="Replay broadcast from the beginning"
              title="Replay from the beginning"
              :disabled="!audioEl || isRegenerating"
              @click="replayAudio"
            >
              <Icon icon="mdi:skip-previous" />
            </Button>
            <div
              v-else
              class="flex flex-1 items-center justify-center rounded border border-dashed border-theme-primary/30 px-2 text-[0.55rem] font-bold uppercase tracking-widest text-theme-primary/50"
            >
              Transcript only
            </div>
            <Button
              variant="outline"
              size="sm"
              class="radio-news-widget__regenerate-btn border-theme-primary/40"
              :disabled="isRegenerating"
              aria-label="Regenerate the broadcast"
              @click="onRegenerate"
            >
              <Icon
                :icon="isRegenerating ? 'mdi:loading' : 'mdi:refresh'"
                class="h-4 w-4"
                :class="{ 'animate-spin': isRegenerating }"
              />
              <span class="hidden text-xs font-semibold sm:inline">Regenerate</span>
            </Button>
          </div>

          <div
            v-if="isAudioAvailable"
            class="radio-news-widget__volume flex items-center gap-3 rounded border border-theme-primary/20 bg-surface-sunken/50 px-2"
          >
            <Button
              variant="ghost"
              size="icon-sm"
              class="shrink-0 text-theme-primary/70 hover:text-theme-primary"
              :aria-label="volume === 0 ? 'Unmute broadcast' : 'Mute broadcast'"
              :aria-pressed="volume === 0"
              :title="volume === 0 ? 'Unmute broadcast' : 'Mute broadcast'"
              @click="toggleMute"
            >
              <Icon
                :icon="
                  volume === 0
                    ? 'mdi:volume-off'
                    : volume < 50
                      ? 'mdi:volume-low'
                      : 'mdi:volume-high'
                "
              />
            </Button>
            <span
              class="hidden text-[0.55rem] uppercase tracking-widest text-theme-primary/60 sm:inline"
              aria-hidden="true"
            >
              Volume
            </span>
            <Slider
              :model-value="[volume]"
              :min="0"
              :max="100"
              :step="1"
              aria-label="Broadcast volume"
              class="min-w-0 flex-1 py-3"
              @update:model-value="setVolume"
            />
            <span
              class="w-9 shrink-0 text-right font-mono text-[0.6rem] tabular-nums text-theme-primary/70"
              aria-hidden="true"
            >
              {{ volume }}%
            </span>
          </div>

          <!-- Transcript doubles as the live caption while audio plays. -->
          <section
            class="radio-news-widget__transcript rounded border border-theme-primary/20 bg-surface-sunken/50 p-3"
            :class="{
              'radio-news-widget__caption border-theme-primary/40': isPlaying,
              'radio-news-widget__text-panel': showTextBroadcast,
            }"
            :aria-live="isPlaying ? 'polite' : undefined"
          >
            <header class="mb-1 flex items-center justify-between gap-2">
              <h4
                class="m-0 flex items-center gap-1.5 text-[0.55rem] font-bold uppercase tracking-[0.2em] text-theme-primary/60"
              >
                <Icon icon="mdi:text-box-outline" class="h-3.5 w-3.5" />
                {{ title }}
              </h4>
              <span
                v-if="showTextBroadcast"
                class="shrink-0 text-[0.55rem] uppercase tracking-widest text-warning"
              >
                Audio unavailable
              </span>
            </header>
            <p
              class="m-0 max-h-32 overflow-y-auto whitespace-pre-wrap text-[0.7rem] leading-relaxed text-theme-primary/85 sm:max-h-40"
            >
              {{ broadcast.script }}
            </p>
          </section>
        </div>
      </template>
    </aside>
  </div>
</template>
