import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { effectScope } from 'vue'
import rawAxios from 'axios'
import { useSse, usePostEventStream } from '@/core/composables/useEventStream'
import { AUTH_SESSION_EXPIRED_EVENT } from '@/core/utils/authSessionEvents'

/**
 * Regression coverage for the SSE auto-reconnect contract: an unintentional
 * close retries with exponential backoff, an explicit `close()` never does,
 * and `stopReconnect` cancels a pending timer.
 */

describe('useEventStream auto-reconnect', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetchMock = vi.fn()
    vi.stubGlobal('fetch', fetchMock)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  // Helper: create a mock fetch response with a controllable SSE stream
  function createMockResponse(chunks: string[], options?: { hang?: boolean }) {
    const encoder = new TextEncoder()
    let index = 0
    let cancelled = false
    let pendingResolve: ((value: { done: boolean; value?: Uint8Array }) => void) | null = null

    const reader = {
      read: vi.fn().mockImplementation(() => {
        if (cancelled || (!options?.hang && index >= chunks.length)) {
          return Promise.resolve({ done: true, value: undefined })
        }
        if (index < chunks.length) {
          const chunk = chunks[index++]
          return Promise.resolve({ done: false, value: encoder.encode(chunk) })
        }
        // hang mode: return a promise that resolves when cancelled
        return new Promise<{ done: boolean; value?: Uint8Array }>((resolve) => {
          pendingResolve = resolve
        })
      }),
      cancel: vi.fn().mockImplementation(() => {
        cancelled = true
        if (pendingResolve) {
          pendingResolve({ done: true, value: undefined })
          pendingResolve = null
        }
        return Promise.resolve(undefined)
      }),
    }
    return {
      ok: true,
      body: {
        getReader: () => reader,
      },
    }
  }

  // Helper: encode SSE events into wire format chunks
  function encodeSse(data: string, event?: string): string {
    let result = ''
    if (event) result += `event: ${event}\n`
    result += `data: ${data}\n\n`
    return result
  }

  /** Starts a stream and settles its first connection under fake timers. */
  async function connect(sse: { start: () => Promise<void> }): Promise<void> {
    const started = sse.start()
    await vi.advanceTimersByTimeAsync(0)
    await started
  }

  /** The abort signal of the nth fetch call. */
  const signalOf = (call = 0): AbortSignal => fetchMock.mock.calls[call][1].signal as AbortSignal

  it.each([403, 404])('does not reconnect after HTTP %s', async (status) => {
    fetchMock.mockResolvedValue({ ok: false, status })
    const sse = useSse('/test')
    await sse.start()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    sse.close()
  })

  it('closes a hidden GET stream and reconnects once when visible', async () => {
    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    fetchMock.mockImplementation(() => Promise.resolve(createMockResponse([], { hang: true })))
    const scope = effectScope()
    const sse = scope.run(() => useSse('/test'))!
    void sse.start()
    await vi.advanceTimersByTimeAsync(0)
    const signal = signalOf()
    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(60_000)
    expect(signal.aborted).toBe(true)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    visibility.mockReturnValue('visible')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    sse.close()
    scope.stop()
  })

  it('keeps an opted-in notification stream alive while hidden but stops it offline', async () => {
    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
    fetchMock.mockResolvedValue(createMockResponse([], { hang: true }))
    const scope = effectScope()
    const sse = scope.run(() => useSse('/notifications', { keepAliveWhenHidden: true }))!
    void sse.start()
    await vi.advanceTimersByTimeAsync(0)
    const signal = signalOf()
    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(signal.aborted).toBe(false)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    window.dispatchEvent(new Event('offline'))
    await vi.advanceTimersByTimeAsync(0)
    expect(signal.aborted).toBe(true)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    sse.close()
    scope.stop()
  })

  it('closes a hidden authenticated notification stream when the session expires', async () => {
    vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('hidden')
    vi.spyOn(navigator, 'onLine', 'get').mockReturnValue(true)
    localStorage.setItem('token', 'test-token')
    fetchMock.mockResolvedValue(createMockResponse([], { hang: true }))
    const scope = effectScope()
    const sse = scope.run(() =>
      useSse('/notifications', {
        keepAliveWhenHidden: true,
        headers: { Authorization: 'Bearer test-token' },
      })
    )!
    void sse.start()
    await vi.advanceTimersByTimeAsync(0)
    const signal = signalOf()
    window.dispatchEvent(new Event(AUTH_SESSION_EXPIRED_EVENT))
    await vi.advanceTimersByTimeAsync(0)
    expect(signal.aborted).toBe(true)
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    sse.close()
    scope.stop()
    localStorage.removeItem('token')
  })

  it('uses the current token when reconnecting a previously configured stream', async () => {
    localStorage.setItem('token', 'current-token')
    fetchMock.mockResolvedValue(createMockResponse([]))
    const sse = useSse('/test', { headers: { Authorization: 'Bearer captured-old-token' } })
    await sse.start()
    expect(fetchMock.mock.calls[0][1].headers.Authorization).toBe('Bearer current-token')
    localStorage.setItem('token', 'new-token')
    await vi.advanceTimersByTimeAsync(1000)
    expect(fetchMock.mock.calls[1][1].headers.Authorization).toBe('Bearer new-token')
    sse.close()
  })

  it('does not refresh or clear the session for a headerless stream rejection', async () => {
    localStorage.setItem('token', 'valid-token')
    localStorage.setItem('refreshToken', 'valid-refresh')
    const refresh = vi
      .spyOn(rawAxios, 'post')
      .mockResolvedValue({ data: { access_token: 'unexpected-token' } })
    fetchMock.mockResolvedValue({ ok: false, status: 401 })
    const sse = useSse('/public-stream')
    await sse.start()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(refresh).not.toHaveBeenCalled()
    expect(localStorage.getItem('token')).toBe('valid-token')
    expect(localStorage.getItem('refreshToken')).toBe('valid-refresh')
    expect(fetchMock).toHaveBeenCalledTimes(1)
    expect(sse.error.value?.message).toContain('401')
    sse.close()
  })

  it('refreshes on 401 and retries a stream only once', async () => {
    localStorage.setItem('token', 'old-token')
    localStorage.setItem('refreshToken', 'stream-refresh')
    const refresh = vi
      .spyOn(rawAxios, 'post')
      .mockResolvedValue({ data: { access_token: 'new-token' } })
    fetchMock.mockResolvedValue({ ok: false, status: 401 })
    const sse = useSse('/test', { headers: { Authorization: 'Bearer old-token' } })
    await sse.start()
    await vi.advanceTimersByTimeAsync(60_000)
    expect(refresh).toHaveBeenCalledTimes(1)
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(localStorage.getItem('token')).toBeNull()
    sse.close()
  })

  it('does not replay a submitted POST when its stream finishes', async () => {
    fetchMock.mockResolvedValue(createMockResponse([]))
    const sse = usePostEventStream('/test')
    await sse.connect({ message: 'hello' })
    await vi.advanceTimersByTimeAsync(60_000)
    expect(fetchMock).toHaveBeenCalledTimes(1)
    sse.close()
  })

  it('does not interrupt a submitted POST stream when hidden', async () => {
    const visibility = vi.spyOn(document, 'visibilityState', 'get').mockReturnValue('visible')
    fetchMock.mockResolvedValue(createMockResponse([], { hang: true }))
    const sse = usePostEventStream('/test')
    void sse.connect({ message: 'hello' })
    await vi.advanceTimersByTimeAsync(0)
    visibility.mockReturnValue('hidden')
    document.dispatchEvent(new Event('visibilitychange'))
    await vi.advanceTimersByTimeAsync(0)
    expect(sse.status.value).toBe('open')
    sse.close()
  })

  describe('auto-reconnect on connection drop', () => {
    it('reconnects when the stream closes unexpectedly', async () => {
      fetchMock
        .mockResolvedValueOnce(createMockResponse([]))
        .mockResolvedValueOnce(createMockResponse([encodeSse('hello')], { hang: true }))

      const sse = useSse('/test')
      await connect(sse)

      // The first stream closed, so a reconnect is scheduled but not yet fired.
      expect(fetchMock).toHaveBeenCalledTimes(1)

      await vi.advanceTimersByTimeAsync(1000)

      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(sse.status.value).toBe('open')
    })

    it('reconnects after a fetch error and clears the recorded error', async () => {
      fetchMock
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(createMockResponse([encodeSse('hello')], { hang: true }))

      const sse = useSse('/test')
      await connect(sse)

      expect(sse.error.value).toBeInstanceOf(Error)
      expect(fetchMock).toHaveBeenCalledTimes(1)

      await vi.advanceTimersByTimeAsync(1000)

      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(sse.status.value).toBe('open')
      expect(sse.error.value).toBeNull()
    })
  })

  describe('exponential backoff', () => {
    it('should increase delay exponentially between reconnect attempts', async () => {
      fetchMock.mockRejectedValue(new Error('Network error'))

      const sse = useSse('/test')
      await connect(sse)
      expect(fetchMock).toHaveBeenCalledTimes(1)

      await vi.advanceTimersByTimeAsync(1000)
      expect(fetchMock).toHaveBeenCalledTimes(2)

      await vi.advanceTimersByTimeAsync(2000)
      expect(fetchMock).toHaveBeenCalledTimes(3)

      await vi.advanceTimersByTimeAsync(4000)
      expect(fetchMock).toHaveBeenCalledTimes(4)
    })

    it('should cap backoff at 30000ms', async () => {
      fetchMock.mockRejectedValue(new Error('Network error'))

      const sse = useSse('/test')
      await connect(sse)

      // 1s, 2s, 4s, 8s, 16s, then the 30s cap
      const delays = [1000, 2000, 4000, 8000, 16000, 30000]
      for (let i = 0; i < delays.length; i++) {
        await vi.advanceTimersByTimeAsync(delays[i])
        expect(fetchMock).toHaveBeenCalledTimes(i + 2)
      }
    })
  })

  describe('no duplicate streams', () => {
    it('should abort old controller before starting new fetch on reconnect', async () => {
      const signals: AbortSignal[] = []
      fetchMock.mockImplementation((_url, init) => {
        signals.push(init.signal)
        return Promise.resolve(createMockResponse([]))
      })

      const sse = useSse('/test')
      await connect(sse)

      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(signals[0]!.aborted).toBe(false)

      await vi.advanceTimersByTimeAsync(1000)
      expect(fetchMock).toHaveBeenCalledTimes(2)

      expect(signals[0]!.aborted).toBe(true)
      expect(signals[1]!.aborted).toBe(false)
    })
  })

  describe('intentional close', () => {
    it('should NOT auto-reconnect after explicit close()', async () => {
      fetchMock.mockResolvedValue(createMockResponse([encodeSse('hello')], { hang: true }))

      const sse = useSse('/test')
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)

      expect(sse.status.value).toBe('open')
      expect(fetchMock).toHaveBeenCalledTimes(1)

      sse.close()

      // Wait for close to propagate through the mock reader
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      expect(sse.status.value).toBe('closed')

      await vi.advanceTimersByTimeAsync(35000)

      expect(fetchMock).toHaveBeenCalledTimes(1)
    })
  })

  describe('reconnected counter', () => {
    it('should increment reconnected on each successful reconnect', async () => {
      fetchMock
        .mockResolvedValueOnce(createMockResponse([]))
        .mockResolvedValueOnce(createMockResponse([encodeSse('msg1')], { hang: true }))

      const sse = useSse('/test')
      expect(sse.reconnected.value).toBe(0)

      await connect(sse)

      await vi.advanceTimersByTimeAsync(1000)
      expect(sse.reconnected.value).toBe(1)
      expect(sse.status.value).toBe('open')
    })
  })

  describe('stopReconnect', () => {
    it('should cancel pending reconnect timer', async () => {
      fetchMock
        .mockResolvedValueOnce(createMockResponse([]))
        .mockResolvedValueOnce(createMockResponse([encodeSse('hello')], { hang: true }))

      const sse = useSse('/test')
      await connect(sse)

      // The reconnect timer is pending but has not fired.
      expect(fetchMock).toHaveBeenCalledTimes(1)

      sse.stopReconnect()

      await vi.advanceTimersByTimeAsync(1000)

      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(sse.status.value).toBe('closed')
    })

    it.each([
      ['usePostEventStream', () => usePostEventStream('/test')],
      ['useSse', () => useSse('/test')],
    ])('should be exposed on %s', (_label, create) => {
      fetchMock.mockResolvedValue(createMockResponse([]))

      const sse = create()
      expect(sse.stopReconnect).toBeDefined()
      expect(typeof sse.stopReconnect).toBe('function')
    })
  })
})
