import { computed, onMounted, onUnmounted, ref, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'

export function parseStartTimeMs(startTime: string): number {
  const normalized = startTime.includes('T') ? startTime : startTime.replace(' ', 'T')
  const withZone = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(normalized) ? normalized : `${normalized}Z`
  return new Date(withZone).getTime()
}

export function getProgressPercentage(exploration: Exploration, nowMs = Date.now()): number {
  if (exploration.status === 'returning') {
    const { return_started_at: startedAt, return_completes_at: completesAt } = exploration
    if (!startedAt || !completesAt) return 100
    const start = parseStartTimeMs(startedAt)
    const total = parseStartTimeMs(completesAt) - start
    if (total <= 0) return 100
    return Math.max(0, Math.min(100, ((nowMs - start) / total) * 100))
  }
  if (exploration.status !== 'active') return 100
  const start = parseStartTimeMs(exploration.start_time)
  const durationMs = exploration.duration * 3600 * 1000
  return Math.max(0, Math.min(100, ((nowMs - start) / durationMs) * 100))
}

function formatRemaining(seconds: number): string {
  const hours = Math.floor(seconds / 3600)
  const minutes = Math.floor((seconds % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m remaining`
  return `${minutes}m remaining`
}

export function getTimeRemaining(exploration: Exploration, nowMs = Date.now()): string {
  if (exploration.status === 'returning') {
    if (!exploration.return_completes_at) return 'Returning home'
    const remaining = (parseStartTimeMs(exploration.return_completes_at) - nowMs) / 1000
    if (remaining <= 0) return 'Arriving home'
    return `Returning — ${formatRemaining(remaining)}`
  }
  const progress = getProgressPercentage(exploration, nowMs)
  const remaining = exploration.duration * 3600 * (1 - progress / 100)
  if (remaining <= 0) return 'Complete!'
  return formatRemaining(remaining)
}

export function canRecall(exploration: Exploration): boolean {
  return exploration.status === 'active'
}

export function isReadyToComplete(exploration: Exploration, nowMs = Date.now()): boolean {
  return exploration.status === 'active' && getProgressPercentage(exploration, nowMs) >= 100
}

export function useExplorationProgress(
  exploration: MaybeRefOrGetter<Exploration | null | undefined>
) {
  const now = ref(Date.now())
  let clock: ReturnType<typeof setInterval> | undefined

  onMounted(() => {
    clock = setInterval(() => {
      now.value = Date.now()
    }, 60_000)
  })

  onUnmounted(() => {
    if (clock !== undefined) clearInterval(clock)
  })

  const resolved = computed(() => toValue(exploration))
  const progress = computed(() => {
    const exp = resolved.value
    return exp ? getProgressPercentage(exp, now.value) : 0
  })
  const timeRemaining = computed(() => {
    const exp = resolved.value
    return exp ? getTimeRemaining(exp, now.value) : ''
  })
  const isReturning = computed(() => resolved.value?.status === 'returning')
  const isReady = computed(() => {
    const exp = resolved.value
    return exp ? isReadyToComplete(exp, now.value) : false
  })
  const recallable = computed(() => {
    const exp = resolved.value
    return exp ? canRecall(exp) : false
  })

  return { progress, timeRemaining, isReturning, isReady, canRecall: recallable }
}
