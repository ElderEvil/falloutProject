import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ExplorationEventLog from '@/modules/exploration/components/ExplorationEventLog.vue'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

const makeEvent = (overrides: Partial<{
  type: string
  description: string
  time_elapsed_hours: number
}> = {}) => ({
  type: overrides.type ?? 'combat',
  description: overrides.description ?? 'A raider attacked.',
  timestamp: '2026-01-01T00:00:00Z',
  time_elapsed_hours: overrides.time_elapsed_hours ?? 2.5,
})

describe('ExplorationEventLog', () => {
  it('renders event rows when events are provided', () => {
    const events = [
      makeEvent({ type: 'combat', description: 'A raider attacked.', time_elapsed_hours: 1.25 }),
      makeEvent({ type: 'loot', description: 'Found a medkit.', time_elapsed_hours: 3.0 }),
    ]

    const wrapper = mount(ExplorationEventLog, {
      props: { events },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.text()).toContain('A raider attacked.')
    expect(wrapper.text()).toContain('Found a medkit.')
    expect(wrapper.findAll('.event-row').length).toBe(2)
  })

  it('renders event type badges in uppercase', () => {
    const events = [makeEvent({ type: 'combat' })]

    const wrapper = mount(ExplorationEventLog, {
      props: { events },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.event-type-badge').text()).toBe('COMBAT')
  })

  it('renders formatted event time', () => {
    const events = [makeEvent({ time_elapsed_hours: 2.5 })]

    const wrapper = mount(ExplorationEventLog, {
      props: { events },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.event-time').text()).toBe('02:30')
  })

  it('renders empty state when no events', () => {
    const wrapper = mount(ExplorationEventLog, {
      props: { events: [] },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.text()).toContain('No events yet')
    expect(wrapper.find('.no-events').exists()).toBe(true)
    expect(wrapper.find('.event-list').exists()).toBe(false)
  })

  it('renders section title', () => {
    const wrapper = mount(ExplorationEventLog, {
      props: { events: [] },
      global: {
        stubs: { Icon: true },
      },
    })

    expect(wrapper.find('.section-title').text()).toContain('Event Log')
  })
})
