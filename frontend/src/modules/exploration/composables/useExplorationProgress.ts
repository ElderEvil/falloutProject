import { computed, onMounted, onUnmounted, ref, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import { parseUtcDate } from '@/core/utils/date'

export function parseStartTimeMs(startTime: string): number {
  return parseUtcDate(startTime).getTime()
}

export function getProgressPercentage(exploration: Exploration, nowMs = Date.now()): number {
  const start = parseStartTimeMs(exploration.start_time)
  const durationMs = exploration.duration * 3600 * 1000
  return Math.max(0, Math.min(100, ((nowMs - start) / durationMs) * 100))
}

export function getTimeRemaining(exploration: Exploration, nowMs = Date.now()): string {
  const progress = getProgressPercentage(exploration, nowMs)
  const remaining = exploration.duration * 3600 * (1 - progress / 100)
  if (remaining <= 0) return 'Complete!'
  const hours = Math.floor(remaining / 3600)
  const minutes = Math.floor((remaining % 3600) / 60)
  if (hours > 0) return `${hours}h ${minutes}m remaining`
  return `${minutes}m remaining`
}

export function useExplorationProgress(exploration: MaybeRefOrGetter<Exploration | null | undefined>) {
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

  return { progress, timeRemaining }
}
