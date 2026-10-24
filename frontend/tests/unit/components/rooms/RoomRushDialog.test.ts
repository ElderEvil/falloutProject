import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import RoomRushDialog from '@/modules/rooms/components/RoomRushDialog.vue'
import type { RoomRushQuote } from '@/modules/rooms/models/room'

vi.mock('@/core/composables/useGameBalance', async () => {
  const { ref } = await import('vue')
  return {
    useGameBalance: () => ({ rushHappinessDelta: ref(10), rushXpPerWorker: ref(25) }),
  }
})

vi.mock('@/core/components/common/TerminalModal.vue', () => ({
  default: {
    props: ['open', 'title'],
    template: '<section v-if="open" :data-title="title"><slot /><slot name="footer" /></section>',
  },
}))

vi.mock('@/core/components/common/TerminalModalActions.vue', () => ({
  default: {
    props: ['cancelLabel', 'confirmLabel', 'confirmDisabled', 'confirmIcon'],
    emits: ['cancel', 'confirm'],
    template:
      '<div><button class="cancel" @click="$emit(\'cancel\')">{{ cancelLabel }}</button>' +
      '<button class="confirm" :disabled="confirmDisabled" @click="$emit(\'confirm\')">{{ confirmLabel }}</button></div>',
  },
}))

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

function mountDialog(overrides: Record<string, unknown> = {}) {
  return mount(RoomRushDialog, {
    props: {
      open: true,
      roomName: 'Power Generator',
      quote,
      loading: false,
      rushing: false,
      error: null,
      blockedMessage: '',
      ...overrides,
    },
  })
}

describe('RoomRushDialog', () => {
  it('shows the server risk, success reward, and failure consequences', () => {
    const wrapper = mountDialog()

    expect(wrapper.text()).toContain('Failure chance')
    expect(wrapper.text()).toContain('23%')
    expect(wrapper.text()).toContain('On success: +12 Power · +25 XP per worker')
    expect(wrapper.text()).toContain('FIRE')
    expect(wrapper.text()).toContain('Failure cost: −10 Happiness')
    expect(wrapper.text()).toContain('Odds breakdown')
    expect(wrapper.text()).not.toContain('Incident chance')
    expect(wrapper.text()).not.toContain('Rush stacks')
    expect(wrapper.text()).not.toContain('2 / 6')
  })

  it('shows the XP reward instead of a misleading empty resource payout', () => {
    const wrapper = mountDialog({
      quote: {
        ...quote,
        payout: { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 },
      },
    })

    expect(wrapper.text()).toContain('On success: +25 XP per worker')
    expect(wrapper.text()).not.toContain('no resources')
  })

  it('shows no incident when the server provides no spawnable incident', () => {
    const wrapper = mountDialog({ quote: { ...quote, eligible_incidents: [] } })

    expect(wrapper.text()).toContain('NO INCIDENT')
  })

  it('explains a blocked quote and disables activation', () => {
    const wrapper = mountDialog({
      quote: { ...quote, can_rush: false, blocked_reason: 'no_workers' },
      blockedMessage: 'Assign at least one living dweller to rush.',
    })

    expect(wrapper.text()).toContain('Assign at least one living dweller to rush.')
    expect(wrapper.get('.confirm').attributes('disabled')).toBeDefined()
  })

  it('shows loading and error states without stale risk', () => {
    const loading = mountDialog({ quote: null, loading: true })
    expect(loading.text()).toContain('Checking the odds...')
    expect(loading.get('.confirm').attributes('disabled')).toBeDefined()

    const failed = mountDialog({ quote: null, error: 'Quote unavailable' })
    expect(failed.text()).toContain('Quote unavailable')
    expect(failed.text()).not.toContain('Failure chance')
    expect(failed.get('.confirm').attributes('disabled')).toBeDefined()
  })

  it('emits cancel and confirm, and disables confirm while rushing', async () => {
    const wrapper = mountDialog()
    await wrapper.get('.cancel').trigger('click')
    await wrapper.get('.confirm').trigger('click')

    expect(wrapper.emitted('cancel')).toHaveLength(1)
    expect(wrapper.emitted('confirm')).toHaveLength(1)

    const rushing = mountDialog({ rushing: true })
    expect(rushing.text()).toContain('Activating...')
    expect(rushing.get('.confirm').attributes('disabled')).toBeDefined()
  })
})
