import { afterEach, describe, expect, it, vi } from 'vitest'
import { effectScope, nextTick, ref } from 'vue'
import { useCountdown } from '@/core/composables/useCountdown'

describe('useCountdown', () => {
  afterEach(() => vi.useRealTimers())

  it('seeds secondsLeft from the source value', () => {
    const scope = effectScope()
    let countdown!: ReturnType<typeof useCountdown>
    scope.run(() => {
      countdown = useCountdown(5)
    })

    expect(countdown.secondsLeft.value).toBe(5)
    expect(countdown.isFinished.value).toBe(false)

    scope.stop()
  })

  it('is already finished when seeded at zero', () => {
    const scope = effectScope()
    let countdown!: ReturnType<typeof useCountdown>
    scope.run(() => {
      countdown = useCountdown(0)
    })

    expect(countdown.secondsLeft.value).toBe(0)
    expect(countdown.isFinished.value).toBe(true)

    scope.stop()
  })

  it('decrements each interval, stops at zero and flags isFinished', async () => {
    vi.useFakeTimers()
    const scope = effectScope()
    let countdown!: ReturnType<typeof useCountdown>
    scope.run(() => {
      countdown = useCountdown(3, 1000)
    })

    await vi.advanceTimersByTimeAsync(1000)
    expect(countdown.secondsLeft.value).toBe(2)
    expect(countdown.isFinished.value).toBe(false)

    await vi.advanceTimersByTimeAsync(1000)
    expect(countdown.secondsLeft.value).toBe(1)

    await vi.advanceTimersByTimeAsync(1000)
    expect(countdown.secondsLeft.value).toBe(0)
    expect(countdown.isFinished.value).toBe(true)

    // Nothing left to tick: the interval must have stopped at zero.
    await vi.advanceTimersByTimeAsync(5000)
    expect(countdown.secondsLeft.value).toBe(0)

    scope.stop()
  })

  it('re-seeds when the source changes', async () => {
    vi.useFakeTimers()
    const source = ref(5)
    const scope = effectScope()
    let countdown!: ReturnType<typeof useCountdown>
    scope.run(() => {
      countdown = useCountdown(source, 1000)
    })

    await vi.advanceTimersByTimeAsync(2000)
    expect(countdown.secondsLeft.value).toBe(3)

    source.value = 10
    await nextTick()

    expect(countdown.secondsLeft.value).toBe(10)
    expect(countdown.isFinished.value).toBe(false)

    await vi.advanceTimersByTimeAsync(1000)
    expect(countdown.secondsLeft.value).toBe(9)

    scope.stop()
  })

  it('re-seeds to zero and flags isFinished when the source drops to zero', async () => {
    vi.useFakeTimers()
    const source = ref(4)
    const scope = effectScope()
    let countdown!: ReturnType<typeof useCountdown>
    scope.run(() => {
      countdown = useCountdown(source, 1000)
    })

    source.value = 0
    await nextTick()

    expect(countdown.secondsLeft.value).toBe(0)
    expect(countdown.isFinished.value).toBe(true)

    await vi.advanceTimersByTimeAsync(5000)
    expect(countdown.secondsLeft.value).toBe(0)

    scope.stop()
  })

  it('stops ticking when the owning scope is disposed', async () => {
    vi.useFakeTimers()
    const scope = effectScope()
    let countdown!: ReturnType<typeof useCountdown>
    scope.run(() => {
      countdown = useCountdown(10, 1000)
    })

    await vi.advanceTimersByTimeAsync(1000)
    const lastTick = countdown.secondsLeft.value

    scope.stop()
    await vi.advanceTimersByTimeAsync(5000)
    expect(countdown.secondsLeft.value).toBe(lastTick)
  })
})
