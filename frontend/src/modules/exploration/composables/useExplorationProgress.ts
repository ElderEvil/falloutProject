import { computed, toValue } from 'vue'
import type { MaybeRefOrGetter } from 'vue'
import { useNow } from '@/core/composables/useNow'
import { formatRemaining, parseUtcMs as parseStartTimeMs } from '@/core/utils/time'
import type { Exploration } from '@/modules/exploration/stores/exploration'

export { formatRemaining, parseStartTimeMs }

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
  const now = useNow(60_000)

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
