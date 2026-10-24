import { describe, expect, it, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import RoomRushPanel from '@/modules/rooms/components/RoomRushPanel.vue'
import type { RoomRushQuote } from '@/modules/rooms/models/room'

vi.mock('@/core/composables/useGameBalance', async () => {
  const { ref } = await import('vue')
  return { useGameBalance: () => ({ rushHappinessDelta: ref(10) }) }
})

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

function mountPanel(overrides: Record<string, unknown> = {}) {
  return mount(RoomRushPanel, {
    props: {
      quote,
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
        TooltipProvider: { template: '<div><slot /></div>' },
        Tooltip: { template: '<div><slot /></div>' },
        TooltipTrigger: { template: '<div><slot /></div>' },
        TooltipContent: { template: '<div><slot /></div>' },
      },
    },
  })
}

describe('RoomRushPanel', () => {
  it('shows the incident chance, consequences, and success payout', () => {
    const wrapper = mountPanel()

    expect(wrapper.text()).toContain('Incident chance')
    expect(wrapper.text()).toContain('23%')
    expect(wrapper.text()).toContain('Rush penalty +20%')
    expect(wrapper.text()).toContain('Possible incidents')
    expect(wrapper.text()).toContain('FIRE')
    expect(wrapper.text()).toContain('−10 Happiness')
    expect(wrapper.text()).toContain('On success: +12 Power')
    expect(wrapper.text()).not.toContain('Caps chance')
  })

  it('reveals the odds breakdown on demand', async () => {
    const wrapper = mountPanel()
    expect(wrapper.find('#rush-breakdown').exists()).toBe(false)

    await wrapper.get('.rush-why').trigger('click')

    expect(wrapper.find('#rush-breakdown').exists()).toBe(true)
    expect(wrapper.text()).toContain('SPECIAL (gear)')
    expect(wrapper.text()).toContain('Luck (gear)')
    expect(wrapper.text()).toContain('Rush penalty')
  })

  it('emits rush when the primary button is clicked', async () => {
    const wrapper = mountPanel()

    await wrapper.get('.rush-button').trigger('click')

    expect(wrapper.emitted('rush')).toBeTruthy()
  })

  it('disables the button and shows the blocked reason', () => {
    const wrapper = mountPanel({
      quote: { ...quote, can_rush: false, blocked_reason: 'no_workers' },
      blockedMessage: 'Assign at least one living dweller to rush.',
    })

    expect(wrapper.text()).toContain('Assign at least one living dweller to rush.')
    expect(wrapper.get('.rush-button').attributes('disabled')).toBeDefined()
  })

  it('shows a quote error instead of stale risk', () => {
    const wrapper = mountPanel({ quote: null, error: 'Quote unavailable' })

    expect(wrapper.text()).toContain('Quote unavailable')
    expect(wrapper.find('button').exists()).toBe(false)
  })
})
