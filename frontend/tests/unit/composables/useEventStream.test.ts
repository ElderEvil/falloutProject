import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest'
import { useSse } from '@/core/composables/useEventStream'

/**
 * SSE Auto-Reconnect Bug Regression Tests
 *
 * BACKGROUND:
 * useSseBase had zero reconnect logic. When the reader loop ended or an error
 * occurred, status just became 'closed' and the function returned. No retry,
 * no backoff, no reconnection.
 *
 * FIX:
 * useSseBase now:
 * 1. Tracks an intentionalClose flag (set true by close())
 * 2. Auto-reconnects with exponential backoff when unintentionally closed
 * 3. Calls close() before reconnecting to prevent duplicate subscriptions
 * 4. Exposes a reconnected counter and stopReconnect cleanup function
 */

describe('useEventStream auto-reconnect', () => {
  let fetchMock: ReturnType<typeof vi.fn>

  beforeEach(() => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    fetchMock = vi.fn()
    global.fetch = fetchMock
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
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

  describe('auto-reconnect on connection drop', () => {
    it('should trigger reconnect when stream closes unexpectedly', async () => {
      // ARRANGE: first connection closes immediately, second hangs open
      fetchMock
        .mockResolvedValueOnce(createMockResponse([]))
        .mockResolvedValueOnce(createMockResponse([encodeSse('hello')], { hang: true }))

      const sse = useSse('/test')

      // ACT: start connection, let first stream close
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      // ASSERT: reconnect timer scheduled (status briefly 'closed')
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // ACT: advance past first reconnect delay (1000ms)
      await vi.advanceTimersByTimeAsync(1000)

      // ASSERT: fetch called twice (initial + reconnect), stream is open
      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(sse.status.value).toBe('open')
    })

    it('should trigger reconnect on fetch error', async () => {
      // ARRANGE: first fetch fails, second hangs open
      fetchMock
        .mockRejectedValueOnce(new Error('Network error'))
        .mockResolvedValueOnce(createMockResponse([encodeSse('hello')], { hang: true }))

      const sse = useSse('/test')

      // ACT: start connection, let first fetch fail
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      // ASSERT: error recorded, status closed after failure
      expect(sse.error.value).toBeInstanceOf(Error)
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // ACT: advance past first reconnect delay
      await vi.advanceTimersByTimeAsync(1000)

      // ASSERT: reconnected successfully
      expect(fetchMock).toHaveBeenCalledTimes(2)
      expect(sse.status.value).toBe('open')
      expect(sse.error.value).toBeNull()
    })
  })

  describe('exponential backoff', () => {
    it('should increase delay exponentially between reconnect attempts', async () => {
      // ARRANGE: all connections fail immediately to force multiple retries
      fetchMock.mockRejectedValue(new Error('Network error'))

      const sse = useSse('/test')

      // ACT: start first connection
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      // ASSERT: first fetch done
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // ACT: advance to first reconnect (1000ms)
      await vi.advanceTimersByTimeAsync(1000)
      expect(fetchMock).toHaveBeenCalledTimes(2)

      // ACT: advance to second reconnect (2000ms)
      await vi.advanceTimersByTimeAsync(2000)
      expect(fetchMock).toHaveBeenCalledTimes(3)

      // ACT: advance to third reconnect (4000ms)
      await vi.advanceTimersByTimeAsync(4000)
      expect(fetchMock).toHaveBeenCalledTimes(4)
    })

    it('should cap backoff at 30000ms', async () => {
      // ARRANGE: all connections fail
      fetchMock.mockRejectedValue(new Error('Network error'))

      const sse = useSse('/test')

      // ACT: initial connection
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      // Run through delays: 1s, 2s, 4s, 8s, 16s, 30s(cap)
      const delays = [1000, 2000, 4000, 8000, 16000, 30000]
      for (let i = 0; i < delays.length; i++) {
        await vi.advanceTimersByTimeAsync(delays[i])
        expect(fetchMock).toHaveBeenCalledTimes(i + 2)
      }
    })
  })

  describe('no duplicate streams', () => {
    it('should abort old controller before starting new fetch on reconnect', async () => {
      // ARRANGE: track all abort signals passed to fetch
      const signals: AbortSignal[] = []
      fetchMock.mockImplementation((_url, init) => {
        signals.push(init.signal)
        return Promise.resolve(createMockResponse([]))
      })

      const sse = useSse('/test')

      // ACT: start connection
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      // ASSERT: first fetch done, signal not aborted yet
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(signals[0].aborted).toBe(false)

      // ACT: trigger reconnect
      await vi.advanceTimersByTimeAsync(1000)
      expect(fetchMock).toHaveBeenCalledTimes(2)

      // ASSERT: old signal was aborted before new fetch
      expect(signals[0].aborted).toBe(true)
      expect(signals[1].aborted).toBe(false)
    })
  })

  describe('intentional close', () => {
    it('should NOT auto-reconnect after explicit close()', async () => {
      // ARRANGE: stream hangs open
      fetchMock.mockResolvedValue(createMockResponse([encodeSse('hello')], { hang: true }))

      const sse = useSse('/test')

      // ACT: start and let it connect
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)

      // ASSERT: connected
      expect(sse.status.value).toBe('open')
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // ACT: explicit close
      sse.close()

      // Wait for close to propagate through the mock reader
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      // ASSERT: status closed, no pending reconnect
      expect(sse.status.value).toBe('closed')

      // ACT: advance time well past any reconnect delay
      await vi.advanceTimersByTimeAsync(35000)

      // ASSERT: no reconnect attempted
      expect(fetchMock).toHaveBeenCalledTimes(1)
    })
  })

  describe('reconnected counter', () => {
    it('should increment reconnected on each successful reconnect', async () => {
      // ARRANGE: first closes immediately, second hangs open
      fetchMock
        .mockResolvedValueOnce(createMockResponse([]))
        .mockResolvedValueOnce(createMockResponse([encodeSse('msg1')], { hang: true }))

      const sse = useSse('/test')

      // ASSERT: counter starts at 0
      expect(sse.reconnected.value).toBe(0)

      // ACT: first connection then reconnect
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      await vi.advanceTimersByTimeAsync(1000)
      expect(sse.reconnected.value).toBe(1)
      expect(sse.status.value).toBe('open')
    })
  })

  describe('stopReconnect', () => {
    it('should cancel pending reconnect timer', async () => {
      // ARRANGE: first connection closes, second would hang
      fetchMock
        .mockResolvedValueOnce(createMockResponse([]))
        .mockResolvedValueOnce(createMockResponse([encodeSse('hello')], { hang: true }))

      const sse = useSse('/test')

      // ACT: start, let it close
      const connectPromise = sse.start()
      await vi.advanceTimersByTimeAsync(0)
      await connectPromise

      // ASSERT: reconnect timer pending (not yet fired)
      expect(fetchMock).toHaveBeenCalledTimes(1)

      // ACT: stop reconnect before timer fires
      sse.stopReconnect()

      // ACT: advance time past the reconnect delay
      await vi.advanceTimersByTimeAsync(1000)

      // ASSERT: no reconnect attempted
      expect(fetchMock).toHaveBeenCalledTimes(1)
      expect(sse.status.value).toBe('closed')
    })

    it('should be exposed on useSse', () => {
      fetchMock.mockResolvedValue(createMockResponse([]))

      const sse = useSse('/test')
      expect(sse.stopReconnect).toBeDefined()
      expect(typeof sse.stopReconnect).toBe('function')
    })
  })
})
