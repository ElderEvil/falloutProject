import { describe, expect, it } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import RoomRushPanel from '@/modules/rooms/components/RoomRushPanel.vue'
import type { RoomRushQuote, RoomRushResult } from '@/modules/rooms/models/room'

const ButtonStub = {
  props: ['disabled'],
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
}

const quote: RoomRushQuote = {
  can_rush: true,
  blocked_reason: null,
  fail_chance: 23,
  success_chance: 77,
  stacks: 2,
  max_stacks: 6,
  avg_ability: 8,
  avg_luck: 7,
  worker_count: 2,
  payout: { power: 12, food: 0, water: 0, stimpack: 0, radaway: 0 },
  caps_chance: 35,
  eligible_incidents: ['fire'],
  next_stack_penalty: 10,
}

const success: RoomRushResult = {
  outcome: 'success',
  payout: { power: 12, food: 0, water: 0, stimpack: 0, radaway: 0 },
  caps: 120,
  xp_per_worker: 25,
  happiness_delta: 10,
  incident_id: null,
  incident_type: null,
  stacks_after: 3,
  next_fail_chance: 33,
  message: 'The rush succeeded and produced 12 power.',
}

function mountPanel(overrides: Record<string, unknown> = {}) {
  return mount(RoomRushPanel, {
    props: {
      quote,
      result: null,
      loading: false,
      rushing: false,
      error: null,
      blockedMessage: '',
      ...overrides,
    },
    global: {
      stubs: {
        Button: ButtonStub,
        Icon: true,
      },
    },
  })
}

describe('RoomRushPanel', () => {
  it('shows risk, success, stacks, caps chance, and payout', () => {
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('Risk')
    expect(wrapper.text()).toContain('23%')
    expect(wrapper.text()).toContain('77%')
    expect(wrapper.text()).toContain('2/6')
    expect(wrapper.text()).toContain('35%')
    expect(wrapper.text()).toContain('+12 Power')
  })

  it('emits rush when the primary button is clicked', async () => {
    const wrapper = mountPanel()

    await wrapper.get('button').trigger('click')

    expect(wrapper.emitted('rush')).toBeTruthy()
  })

  it('disables the button and shows the blocked reason', () => {
    const wrapper = mountPanel({
      quote: { ...quote, can_rush: false, blocked_reason: 'no_workers' },
      blockedMessage: 'Assign at least one living dweller to rush.',
    })

    expect(wrapper.text()).toContain('Assign at least one living dweller to rush.')
    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
  })

  it('renders a success stamp and outcome details', () => {
    const wrapper = mountPanel({ result: success })

    expect(wrapper.text()).toContain('RUSH OK')
    expect(wrapper.text()).toContain('Produced: +12 Power')
    expect(wrapper.text()).toContain('Caps bonus: +120')
  })

  it('renders a failure stamp with the incident type', () => {
    const wrapper = mountPanel({
      result: {
        ...success,
        outcome: 'failure',
        payout: { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 },
        caps: 0,
        xp_per_worker: 0,
        happiness_delta: -10,
        incident_id: 'incident-1',
        incident_type: 'fire',
        message: 'The rush backfired and triggered fire.',
      },
    })

    expect(wrapper.text()).toContain('RUSH FAIL')
    expect(wrapper.text()).toContain('Incident: fire')
  })

  it('shows a quote error instead of stale risk', () => {
    const wrapper = mountPanel({ quote: null, error: 'Quote unavailable' })

    expect(wrapper.text()).toContain('Quote unavailable')
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
