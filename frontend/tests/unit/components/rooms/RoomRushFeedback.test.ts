import { afterEach, describe, expect, it, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import RoomRushFeedback from '@/modules/rooms/components/RoomRushFeedback.vue'
import type { RoomRushResult } from '@/modules/rooms/models/room'

const success: RoomRushResult = {
  outcome: 'success',
  payout: { power: 12, food: 0, water: 0, stimpack: 0, radaway: 0 },
  caps: 120,
  xp_per_worker: 25,
  happiness_delta: 10,
  incident_id: null,
  incident_type: null,
  stacks_after: 1,
  next_fail_chance: 20,
  message: 'The rush succeeded and produced 12 power.',
}

function mountFeedback(result: RoomRushResult | null) {
  return mount(RoomRushFeedback, {
    props: { result },
    global: { stubs: { Teleport: true } },
  })
}

describe('RoomRushFeedback', () => {
  afterEach(() => {
    vi.useRealTimers()
  })

  it('shows the success stamp, sprite, and gains', () => {
    const wrapper = mountFeedback(success)

    expect(wrapper.text()).toContain('RUSH OK')
    expect(wrapper.text()).toContain('+12 POWER · +120 CAPS')
    expect(wrapper.find('.rush-popup__sprite').attributes('style')).toContain('rush-ok.webp')

    wrapper.unmount()
  })

  it('shows the failure stamp, sprite, and incident', () => {
    const wrapper = mountFeedback({
      ...success,
      outcome: 'failure',
      payout: { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 },
      caps: 0,
      xp_per_worker: 0,
      happiness_delta: -10,
      incident_id: 'incident-1',
      incident_type: 'fire',
      message: 'The rush backfired and triggered fire.',
    })

    expect(wrapper.text()).toContain('RUSH FAIL')
    expect(wrapper.text()).toContain('FIRE')
    expect(wrapper.text()).toContain('−10 HAPPINESS')
    expect(wrapper.find('.rush-popup__sprite').attributes('style')).toContain('rush-fail.webp')

    wrapper.unmount()
  })

  it('hides itself after the feedback window', async () => {
    vi.useFakeTimers()
    const wrapper = mountFeedback(success)
    expect(wrapper.find('.rush-popup').exists()).toBe(true)

    await vi.advanceTimersByTimeAsync(4300)

    expect(wrapper.find('.rush-popup').exists()).toBe(false)
    wrapper.unmount()
  })

  it('stays hidden without a result', () => {
    const wrapper = mountFeedback(null)

    expect(wrapper.find('.rush-popup').exists()).toBe(false)
    wrapper.unmount()
  })
})
