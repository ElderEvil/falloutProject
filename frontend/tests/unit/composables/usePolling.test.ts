import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { handleStoreError } from '@/core/utils/errorHandler'
import { usePolling } from '@/core/composables/usePolling'

vi.mock('@/core/utils/errorHandler', () => ({
  handleStoreError: vi.fn(),
}))

describe('usePolling', () => {
  afterEach(() => vi.useRealTimers())

  it('stops its interval when the owning scope is disposed', async () => {
    vi.useFakeTimers()
    const refresh = vi.fn()
    const scope = effectScope()
    scope.run(() => usePolling(refresh, { interval: 100, immediate: false }))

    await vi.advanceTimersByTimeAsync(300)
    expect(refresh).toHaveBeenCalledTimes(3)

    scope.stop()
    await vi.advanceTimersByTimeAsync(300)
    expect(refresh).toHaveBeenCalledTimes(3)
  })

  it('does not overlap a slow refresh', async () => {
    let resolveRefresh!: () => void
    const refresh = vi.fn(
      () => new Promise<void>((resolve) => {
        resolveRefresh = resolve
      })
    )
    const { run, isRefreshing } = usePolling(refresh, { immediate: false })

    const first = run()
    await run()
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(isRefreshing.value).toBe(true)

    resolveRefresh()
    await first
    expect(isRefreshing.value).toBe(false)
  })

  it('handles rejected scheduled refreshes without changing run() semantics', async () => {
    vi.useFakeTimers()
    const refresh = vi.fn().mockRejectedValue(new Error('Refresh failed'))
    usePolling(refresh, { interval: 100, immediate: false })

    await vi.advanceTimersByTimeAsync(100)

    expect(handleStoreError).toHaveBeenCalledWith(expect.any(Error), 'Failed to refresh polled data')
  })
})
