import { getCurrentScope, onScopeDispose, ref, watch } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { handleStoreError } from '@/core/utils/errorHandler'
import { getErrorStatus } from '@/core/types/utils'
import { ensureAccessToken } from '@/core/utils/authSession'
import { useBackgroundActivity } from './useBackgroundActivity'

export interface PollingOptions {
  interval?: number
  immediate?: boolean
}

/** Authenticated refreshes pause when hidden/offline, with no overlap or catch-up burst. */
export function usePolling(
  refresh: () => unknown,
  { interval = 30_000, immediate = true }: PollingOptions = {}
) {
  const { canRun, stop: stopActivity } = useBackgroundActivity()
  const isRefreshing = ref(false)
  const delay = ref(interval)
  let enabled = true
  let blocked = false
  let disposed = false
  let hasReportedError = false

  async function run() {
    if (isRefreshing.value || disposed) return
    isRefreshing.value = true
    try {
      await ensureAccessToken()
      if (!canRun.value || disposed) return
      await refresh()
      delay.value = interval
      hasReportedError = false
    } catch (error) {
      const status = getErrorStatus(error)
      if (status && [401, 403, 404].includes(status)) {
        blocked = true
        pauseInterval()
      } else {
        delay.value = Math.min(delay.value * 2, Math.max(interval, 60_000))
      }
      throw error
    } finally {
      isRefreshing.value = false
    }
  }

  const scheduledRefresh = () => {
    if (!canRun.value || !enabled || blocked || disposed) return
    void run().catch((error) => {
      if (hasReportedError || getErrorStatus(error) === 401) return
      hasReportedError = true
      handleStoreError(error, 'Failed to refresh polled data')
    })
  }

  const {
    pause: pauseInterval,
    resume: resumeInterval,
    isActive,
  } = useIntervalFn(scheduledRefresh, delay, { immediate: false })

  const stopWatch = watch(
    canRun,
    (active, previous) => {
      pauseInterval()
      if (!active || !enabled || blocked) return
      if (previous !== undefined || immediate) scheduledRefresh()
      resumeInterval()
    },
    { immediate: true }
  )

  function pause() {
    enabled = false
    pauseInterval()
  }

  function resume() {
    enabled = true
    blocked = false
    if (!canRun.value || disposed) return
    if (immediate) scheduledRefresh()
    resumeInterval()
  }

  function stop() {
    disposed = true
    pause()
    stopWatch()
    stopActivity()
  }

  if (getCurrentScope()) onScopeDispose(stop)

  return { run, pause, resume, stop, isActive, isRefreshing }
}
