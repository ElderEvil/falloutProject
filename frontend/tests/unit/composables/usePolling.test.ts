import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick } from 'vue'
import { handleStoreError } from '@/core/utils/errorHandler'
import { usePolling } from '@/core/composables/usePolling'

vi.mock('@/core/utils/errorHandler', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/core/utils/errorHandler')>()),
  handleStoreError: vi.fn(),
}))

beforeEach(() => {
  localStorage.setItem('token', 'test-token')
})

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
      () =>
        new Promise<void>((resolve) => {
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

    expect(handleStoreError).toHaveBeenCalledWith(
      expect.any(Error),
      'Failed to refresh polled data'
    )
  })

  it('reports one error per consecutive failure episode', async () => {
    vi.useFakeTimers()
    vi.mocked(handleStoreError).mockClear()
    const refresh = vi
      .fn()
      .mockRejectedValueOnce(new Error('Offline'))
      .mockRejectedValueOnce(new Error('Offline'))
      .mockResolvedValueOnce(undefined)
      .mockRejectedValueOnce(new Error('Offline again'))
    const scope = effectScope()
    scope.run(() => usePolling(refresh, { interval: 100, immediate: false }))

    await vi.advanceTimersByTimeAsync(200)
    expect(handleStoreError).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(600)
    expect(handleStoreError).toHaveBeenCalledTimes(2)
    scope.stop()
  })
})

// Background requests must not depend on browser timer throttling.
describe('background polling lifecycle', () => {
  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('pauses while hidden and refreshes once when the tab returns', async () => {
    vi.useFakeTimers()
    localStorage.setItem('token', 'test-token')
    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    const refresh = vi.fn()
    const scope = effectScope()
    scope.run(() => usePolling(refresh, { interval: 100, immediate: false }))
    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await nextTick()
    await vi.advanceTimersByTimeAsync(500)
    expect(refresh).not.toHaveBeenCalled()
    visibility.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(refresh).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('does not resume a manually paused poll when visibility returns', async () => {
    vi.useFakeTimers()
    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    const refresh = vi.fn()
    const scope = effectScope()
    const poll = scope.run(() => usePolling(refresh, { interval: 100, immediate: false }))!
    poll.pause()
    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await nextTick()
    visibility.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(500)
    expect(refresh).not.toHaveBeenCalled()
    scope.stop()
  })

  it('stops offline and refreshes once on reconnect', async () => {
    vi.useFakeTimers()
    const online = vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
    const refresh = vi.fn()
    const scope = effectScope()
    scope.run(() => usePolling(refresh, { interval: 100, immediate: false }))
    online.mockReturnValue(false)
    window.dispatchEvent(new Event('offline'))
    await vi.advanceTimersByTimeAsync(500)
    expect(refresh).not.toHaveBeenCalled()
    online.mockReturnValue(true)
    window.dispatchEvent(new Event('online'))
    await vi.advanceTimersByTimeAsync(0)
    expect(refresh).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('backs off transient failures rather than repeating at the normal interval', async () => {
    vi.useFakeTimers()
    const refresh = vi.fn().mockRejectedValue(new Error('Network unavailable'))
    const scope = effectScope()
    scope.run(() => usePolling(refresh, { interval: 100, immediate: false }))
    await vi.advanceTimersByTimeAsync(100)
    expect(refresh).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(199)
    expect(refresh).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(1)
    expect(refresh).toHaveBeenCalledTimes(2)
    scope.stop()
  })

  it('stops all future ticks when the session expires', async () => {
    vi.useFakeTimers()
    const refresh = vi.fn()
    const scope = effectScope()
    scope.run(() => usePolling(refresh, { interval: 100, immediate: false }))
    await vi.advanceTimersByTimeAsync(100)
    expect(refresh).toHaveBeenCalledTimes(1)
    window.dispatchEvent(new Event('auth-session-expired'))
    await vi.advanceTimersByTimeAsync(1_000)
    expect(refresh).toHaveBeenCalledTimes(1)
    scope.stop()
  })

  it('stops retrying permission failures', async () => {
    vi.useFakeTimers()
    localStorage.setItem('token', 'test-token')
    const refresh = vi.fn().mockRejectedValue({ response: { status: 403 } })
    const scope = effectScope()
    scope.run(() => usePolling(refresh, { interval: 100, immediate: false }))
    await vi.advanceTimersByTimeAsync(1_000)
    expect(refresh).toHaveBeenCalledTimes(1)
    scope.stop()
  })
})
