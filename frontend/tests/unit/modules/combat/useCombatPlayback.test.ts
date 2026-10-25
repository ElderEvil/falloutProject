import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent, ref } from 'vue'
import { mount } from '@vue/test-utils'
import { useCombatPlayback } from '@/modules/combat/composables/useCombatPlayback'
import type { CombatPlaybackEvent, CombatPlaybackSnapshot } from '@/modules/combat/models/playback'

const hit = (
  id: string,
  actor = 'a',
  target = 'b',
  before = 100,
  after = 90
): CombatPlaybackEvent => ({
  id,
  message: 'Attack',
  action: {
    actor_id: actor,
    effect: 'strike',
    skill: null,
    targets: [
      { target_id: target, damage: before - after, health_before: before, health_after: after },
    ],
  },
})

describe('combat playback', () => {
  const snapshot = ref<CombatPlaybackSnapshot>({ key: 'fight', health: {}, events: [] })
  const impact = vi.fn()
  let playback: ReturnType<typeof useCombatPlayback>
  let wrapper: ReturnType<typeof mount>
  const start = () => {
    wrapper = mount(
      defineComponent({
        setup() {
          playback = useCombatPlayback(() => snapshot.value, impact)
          return () => null
        },
      })
    )
  }
  beforeEach(() => {
    vi.useFakeTimers()
    impact.mockClear()
    snapshot.value = { key: 'fight', health: { a: 100, b: 100, c: 100 }, events: [] }
  })
  afterEach(() => {
    wrapper?.unmount()
    vi.useRealTimers()
  })

  it('plays participants in order and applies each target outcome at impact', async () => {
    start()
    snapshot.value = {
      ...snapshot.value,
      health: { a: 95, b: 90, c: 100 },
      events: [hit('1'), hit('2', 'b', 'a', 100, 95)],
    }
    expect(playback.active.value?.action.actor_id).toBe('a')
    expect(playback.health.value).toEqual({ a: 100, b: 100, c: 100 })
    await vi.advanceTimersByTimeAsync(150)
    expect(playback.health.value.b).toBe(90)
    expect(playback.health.value.a).toBe(100)
    expect(impact).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(200)
    expect(playback.active.value?.action.actor_id).toBe('b')
    await vi.advanceTimersByTimeAsync(150)
    expect(playback.health.value.a).toBe(95)
    await vi.advanceTimersByTimeAsync(200)
    expect(playback.isPlaying.value).toBe(false)
  })

  it('plays an area skill once before the same actor ordinary attack', async () => {
    start()
    const skill = hit('skill')
    skill.action!.skill = 'Cleave'
    skill.action!.targets.push({ target_id: 'c', damage: 7, health_before: 100, health_after: 93 })
    snapshot.value = {
      ...snapshot.value,
      health: { a: 100, b: 85, c: 93 },
      events: [skill, hit('normal', 'a', 'b', 90, 85)],
    }
    await vi.advanceTimersByTimeAsync(249)
    expect(playback.damageNumbers.value).toEqual([])
    await vi.advanceTimersByTimeAsync(1)
    expect(playback.health.value).toEqual({ a: 100, b: 90, c: 93 })
    expect(impact).toHaveBeenCalledTimes(1)
    await vi.advanceTimersByTimeAsync(300)
    expect(playback.active.value?.id).toBe('normal')
    await vi.advanceTimersByTimeAsync(150)
    expect(playback.health.value.b).toBe(85)
  })

  it('skips history on entry and deduplicates repeated rolling windows', async () => {
    snapshot.value.events = [hit('old')]
    start()
    expect(playback.isPlaying.value).toBe(false)
    snapshot.value = {
      ...snapshot.value,
      health: { a: 100, b: 90 },
      events: [hit('old'), hit('new')],
    }
    snapshot.value = { ...snapshot.value, events: [...snapshot.value.events] }
    await vi.advanceTimersByTimeAsync(1000)
    expect(impact).toHaveBeenCalledTimes(1)
    snapshot.value = { ...snapshot.value, events: [hit('new')] }
    await vi.advanceTimersByTimeAsync(1000)
    expect(impact).toHaveBeenCalledTimes(1)
  })

  it.each(['reset', 'different fight', 'missing history', 'long absence'])(
    'cancels pending effects after %s',
    async (reason) => {
      start()
      snapshot.value = { ...snapshot.value, events: [hit('1')] }
      if (reason === 'reset') playback.reset()
      else {
        if (reason === 'long absence') vi.setSystemTime(Date.now() + 11_000)
        snapshot.value = {
          key: reason === 'different fight' ? 'other' : 'fight',
          health: { b: 42 },
          events: reason === 'missing history' ? [hit('missing')] : snapshot.value.events,
        }
      }
      await vi.advanceTimersByTimeAsync(1000)
      expect(impact).not.toHaveBeenCalled()
      expect(playback.isPlaying.value).toBe(false)
    }
  )

  it('cancels impact and damage timers when the scene unmounts', async () => {
    start()
    snapshot.value = { ...snapshot.value, events: [hit('1')] }
    wrapper.unmount()
    await vi.advanceTimersByTimeAsync(1000)
    expect(impact).not.toHaveBeenCalled()
    expect(playback.damageNumbers.value).toEqual([])
  })

  it('bounds a backlog instead of replaying an indefinitely old fight', () => {
    start()
    snapshot.value = {
      ...snapshot.value,
      health: { b: 1 },
      events: Array.from({ length: 60 }, (_, index) => hit(String(index))),
    }
    expect(playback.isPlaying.value).toBe(false)
    expect(playback.health.value.b).toBe(1)
  })

  it('keeps impacts while a roster lags, then accepts healing after it catches up', async () => {
    start()
    snapshot.value = { ...snapshot.value, events: [hit('1'), hit('2', 'a', 'b', 90, 85)] }
    await vi.advanceTimersByTimeAsync(700)
    expect(playback.health.value.b).toBe(85)
    snapshot.value = { ...snapshot.value, health: { b: 90 } }
    expect(playback.health.value.b).toBe(85)
    snapshot.value = { ...snapshot.value, health: { b: 85 } }
    snapshot.value = { ...snapshot.value, health: { b: 100 } }
    expect(playback.health.value.b).toBe(100)
  })

  it('uses current healed HP when entering a fight with historical damage', () => {
    snapshot.value.events = [hit('old')]
    start()
    expect(playback.health.value.b).toBe(100)
    expect(playback.isPlaying.value).toBe(false)
  })
})
