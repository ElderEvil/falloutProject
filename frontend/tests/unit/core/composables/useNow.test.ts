import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, type Ref } from 'vue'
import { useNow } from '@/core/composables/useNow'

const EPOCH = Date.parse('2026-01-01T00:00:00.000Z')

describe('useNow', () => {
  afterEach(() => vi.useRealTimers())

  it('seeds from the current time and advances with the interval', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(EPOCH)
    const scope = effectScope()
    let now!: Readonly<Ref<number>>
    scope.run(() => {
      now = useNow(1000)
    })

    expect(now.value).toBe(EPOCH)

    await vi.advanceTimersByTimeAsync(1000)
    expect(now.value).toBe(EPOCH + 1000)

    await vi.advanceTimersByTimeAsync(2000)
    expect(now.value).toBe(EPOCH + 3000)

    scope.stop()
  })

  it('honours a custom interval', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(EPOCH)
    const scope = effectScope()
    let now!: Readonly<Ref<number>>
    scope.run(() => {
      now = useNow(250)
    })

    await vi.advanceTimersByTimeAsync(500)
    expect(now.value).toBe(EPOCH + 500)

    scope.stop()
  })

  it('stops ticking when the owning scope is disposed', async () => {
    vi.useFakeTimers()
    vi.setSystemTime(EPOCH)
    const scope = effectScope()
    let now!: Readonly<Ref<number>>
    scope.run(() => {
      now = useNow(1000)
    })

    await vi.advanceTimersByTimeAsync(1000)
    const lastTick = now.value

    scope.stop()
    await vi.advanceTimersByTimeAsync(5000)
    expect(now.value).toBe(lastTick)
  })
})
