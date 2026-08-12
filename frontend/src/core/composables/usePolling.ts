import { getCurrentScope, onScopeDispose, ref } from 'vue'
import { useIntervalFn } from '@vueuse/core'
import { handleStoreError } from '@/core/utils/errorHandler'

export interface PollingOptions {
  interval?: number
  immediate?: boolean
}

/**
 * Runs a data refresh at a fixed interval with overlap protection.
 * The interval is disposed with the current Vue effect scope when one exists.
 */
export function usePolling(
  refresh: () => unknown,
  { interval = 30_000, immediate = true }: PollingOptions = {}
) {
  const isRefreshing = ref(false)
  let generation = 0

  async function run() {
    if (isRefreshing.value) return

    const activeGeneration = ++generation
    isRefreshing.value = true
    try {
      await refresh()
    } finally {
      // A late completion from a prior generation must not clear a newer run.
      if (activeGeneration === generation) isRefreshing.value = false
    }
  }

  const runScheduledRefresh = () => {
    void run().catch((error) => handleStoreError(error, 'Failed to refresh polled data'))
  }

  const { pause, resume, isActive } = useIntervalFn(runScheduledRefresh, interval, {
    immediate: true,
    immediateCallback: immediate,
  })

  if (getCurrentScope()) onScopeDispose(pause)

  return { run, pause, resume, isActive, isRefreshing }
}
