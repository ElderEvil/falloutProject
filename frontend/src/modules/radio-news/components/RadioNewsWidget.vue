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
  <div class="radio-news-widget">
    <!-- Loading state -->
    <div v-if="isLoading" class="radio-news-widget__loading" aria-label="Loading broadcast">
      <div class="skeleton skeleton--pill" />
      <span class="radio-news-widget__loading-text">Loading…</span>
    </div>

    <!-- Error state -->
    <div v-else-if="error && !broadcast" class="radio-news-widget__error" aria-label="Broadcast error">
      <Icon icon="mdi:alert-circle-outline" class="radio-news-widget__error-icon" />
      <span class="radio-news-widget__error-text">{{ error }}</span>
    </div>

    <!-- Welcome panel: unplayed today broadcast with blocked autoplay -->
    <div
      v-if="showWelcomePanel && broadcast"
      class="radio-news-widget__welcome-panel"
    >
      <div class="radio-news-widget__welcome-header">
        <Icon icon="mdi:radio" class="radio-news-widget__welcome-icon" />
        <h3 class="radio-news-widget__welcome-title">
          📻 Vault Radio Hour
        </h3>
      </div>
      <p class="radio-news-widget__welcome-script">
        {{ broadcast.script }}
      </p>
      <Button
        variant="outline"
        size="sm"
        class="radio-news-widget__welcome-play-btn"
        @click="onWelcomePanelPlay"
      >
        <Icon icon="mdi:play-circle-outline" class="radio-news-widget__welcome-play-icon" />
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
              class="radio-news-widget__badge"
              :class="{ 'badge-active': isToday }"
            >
              <Icon icon="mdi:radio" class="radio-news-widget__badge-icon" />
              <span class="radio-news-widget__badge-text">
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
        class="radio-news-widget__text-panel"
      >
        <div class="radio-news-widget__text-panel-header">
          <Icon icon="mdi:radio" class="radio-news-widget__text-panel-icon" />
          <h4 class="radio-news-widget__text-panel-title">
            {{ broadcast.title || 'Radio Broadcast' }}
          </h4>
        </div>
        <p class="radio-news-widget__text-panel-script">
          {{ broadcast.script }}
        </p>
        <div class="radio-news-widget__text-panel-meta">
          {{ broadcast.created_at ? new Date(broadcast.created_at).toLocaleString() : 'Audio unavailable' }}
        </div>
      </div>

      <!-- Play button (audio available) -->
      <div v-if="isAudioAvailable" class="radio-news-widget__play-controls">
        <Button
          variant="outline"
          size="sm"
          class="radio-news-widget__play-btn"
          :class="{ 'is-playing': isPlaying }"
          @click="onTogglePlay"
        >
          <Icon
            :icon="isPlaying ? 'mdi:pause' : 'mdi:play'"
            class="radio-news-widget__play-icon"
          />
          <span class="radio-news-widget__play-text">
            {{ isPlaying ? 'Stop' : 'Play' }}
          </span>
        </Button>
      </div>
    </div>

    <!-- Caption overlay while playing -->
    <div
      v-if="showCaption"
      class="radio-news-widget__caption"
      aria-live="polite"
    >
      <div class="radio-news-widget__caption-header">
        <Icon icon="mdi:radio" class="radio-news-widget__caption-icon" />
        <h4 class="radio-news-widget__caption-title">
          {{ broadcast?.title || 'Radio Broadcast' }}
        </h4>
      </div>
      <p class="radio-news-widget__caption-script">
        {{ broadcast?.script }}
      </p>
    </div>
  </div>
</template>

<style scoped>
.radio-news-widget {
  display: flex;
  flex-direction: column;
  gap: 0.5rem;
}

.radio-news-widget__loading {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.radio-news-widget__loading-text {
  font-size: 0.75rem;
  color: var(--color-theme-primary);
}

.skeleton {
  background: linear-gradient(90deg,
    var(--color-surface) 25%,
    var(--color-surface-hover) 50%,
    var(--color-surface) 75%);
  background-size: 200% 100%;
  animation: shimmer 1.5s ease-in-out infinite;
  border-radius: 9999px;
}

.skeleton--pill {
  width: 6rem;
  height: 1.25rem;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.radio-news-widget__badge {
  border-color: color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  background: color-mix(in srgb, var(--color-theme-primary) 5%, transparent);
  cursor: default;
}

.radio-news-widget__badge.badge-active {
  border-color: color-mix(in srgb, var(--color-theme-primary) 60%, transparent);
  background: color-mix(in srgb, var(--color-theme-primary) 15%, transparent);
  animation: badgePulse 2s ease-in-out infinite;
}

.radio-news-widget__badge-icon {
  height: 0.875rem;
  width: 0.875rem;
}

.radio-news-widget__badge-text {
  font-size: 0.6rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
}

@keyframes badgePulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.75; }
}

@keyframes subtlePulse {
  0%, 100% { opacity: 0.9; }
  50% { opacity: 1; }
}

.radio-news-widget__play-controls {
  animation: subtlePulse 2s ease-in-out infinite;
}

.radio-news-widget__play-btn {
  border-color: color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
}

.radio-news-widget__play-btn.is-playing {
  background: color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
}

.radio-news-widget__play-icon {
  height: 1rem;
  width: 1rem;
}

.radio-news-widget__play-text {
  font-size: 0.75rem;
  font-weight: 600;
}

.radio-news-widget__text-panel,
.radio-news-widget__caption {
  animation: subtlePulse 2s ease-in-out infinite;
}

.radio-news-widget__text-panel {
  margin-top: 0.5rem;
  max-width: 20rem;
  border-radius: 0.375rem;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 20%, transparent);
  background: color-mix(in srgb, var(--color-surface-raised) 80%, transparent);
  padding: 0.75rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.radio-news-widget__text-panel-header {
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.radio-news-widget__text-panel-icon {
  height: 1rem;
  width: 1rem;
  color: var(--color-theme-primary);
}

.radio-news-widget__text-panel-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--color-theme-primary);
  margin: 0;
}

.radio-news-widget__text-panel-script {
  white-space: pre-wrap;
  font-size: 0.7rem;
  line-height: 1.5;
  color: color-mix(in srgb, var(--color-theme-primary) 80%, transparent);
}

.radio-news-widget__text-panel-meta {
  margin-top: 0.5rem;
  font-size: 0.6rem;
  color: color-mix(in srgb, var(--color-theme-primary) 50%, transparent);
}

.radio-news-widget__error {
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.radio-news-widget__error-icon {
  height: 1rem;
  width: 1rem;
  color: var(--color-danger);
}

.radio-news-widget__error-text {
  font-size: 0.75rem;
  color: var(--color-danger);
}

.radio-news-widget__welcome-panel {
  margin-top: 0.5rem;
  border-radius: 0.375rem;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
  background: color-mix(in srgb, var(--color-surface-warm) 90%, transparent);
  padding: 1rem;
  box-shadow: 0 4px 16px rgba(0, 0, 0, 0.25);
  animation: welcomeSlideIn 0.3s ease-out;
}

@keyframes welcomeSlideIn {
  from { opacity: 0; transform: translateY(-8px); }
  to { opacity: 1; transform: translateY(0); }
}

.radio-news-widget__welcome-header {
  margin-bottom: 0.75rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.radio-news-widget__welcome-icon {
  height: 1.25rem;
  width: 1.25rem;
  color: var(--color-theme-primary);
}

.radio-news-widget__welcome-title {
  font-size: 0.875rem;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 0.1em;
  color: var(--color-theme-primary);
  margin: 0;
}

.radio-news-widget__welcome-script {
  margin-bottom: 0.75rem;
  white-space: pre-wrap;
  font-size: 0.75rem;
  line-height: 1.5;
  color: color-mix(in srgb, var(--color-theme-primary) 80%, transparent);
}

.radio-news-widget__welcome-play-btn {
  width: 100%;
}

.radio-news-widget__welcome-play-icon {
  margin-right: 0.375rem;
  height: 1rem;
  width: 1rem;
}

.radio-news-widget__caption {
  margin-top: 0.5rem;
  max-width: 20rem;
  border-radius: 0.375rem;
  border: 1px solid color-mix(in srgb, var(--color-theme-primary) 30%, transparent);
  background: color-mix(in srgb, var(--color-surface-warm) 90%, transparent);
  padding: 0.75rem;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
}

.radio-news-widget__caption-header {
  margin-bottom: 0.25rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.radio-news-widget__caption-icon {
  height: 1rem;
  width: 1rem;
  animation: pulse 2s ease-in-out infinite;
  color: var(--color-theme-primary);
}

@keyframes pulse {
  0% { opacity: 0.5; }
  50% { opacity: 1; }
  100% { opacity: 0.5; }
}

.radio-news-widget__caption-title {
  font-size: 0.75rem;
  font-weight: 700;
  text-transform: uppercase;
  color: var(--color-theme-primary);
  margin: 0;
}

.radio-news-widget__caption-script {
  white-space: pre-wrap;
  font-size: 0.7rem;
  line-height: 1.5;
  color: var(--color-theme-primary);
}
</style>
