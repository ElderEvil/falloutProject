import { describe, it, expect, vi } from 'vite-plus/test'
import { createIconifyMock } from '../../helpers/mocks'
import { mount } from '@vue/test-utils'
import ExplorationEventLog from '@/modules/exploration/components/ExplorationEventLog.vue'

vi.mock('@iconify/vue', () => createIconifyMock())

const makeEvent = (
  overrides: Partial<{ type: string; description: string; time_elapsed_hours: number }> = {}
) => ({
  type: overrides.type ?? 'combat',
  description: overrides.description ?? 'A raider attacked.',
  timestamp: '2026-01-01T00:00:00Z',
  time_elapsed_hours: overrides.time_elapsed_hours ?? 2.5,
})

const makeLootEvent = () => ({
  type: 'loot',
  description: 'Found a stash.',
  timestamp: '2026-01-01T00:00:00Z',
  time_elapsed_hours: 1.5,
  loot: {
    item: { name: 'Laser rifle', rarity: 'Rare', value: 100 },
    caps: 25,
  },
})

const mountLog = (props: Record<string, unknown> = {}) =>
  mount(ExplorationEventLog, { props, global: { stubs: { Icon: true } } })

describe('ExplorationEventLog', () => {
  it('renders event rows when events are provided', () => {
    const events = [
      makeEvent({ type: 'combat', description: 'A raider attacked.', time_elapsed_hours: 1.25 }),
      makeEvent({ type: 'loot', description: 'Found a medkit.', time_elapsed_hours: 3.0 }),
    ]

    const wrapper = mountLog({ events })

    expect(wrapper.text()).toContain('A raider attacked.')
    expect(wrapper.text()).toContain('Found a medkit.')
    expect(wrapper.findAll('.event-row')).toHaveLength(2)
  })

  it('renders the uppercase type badge and the formatted event time', () => {
    const wrapper = mountLog({ events: [makeEvent({ type: 'combat', time_elapsed_hours: 2.5 })] })

    expect(wrapper.find('.event-type-badge').text()).toBe('COMBAT')
    expect(wrapper.find('.event-time').text()).toBe('02:30')
  })

  it('renders the section title and empty state when no events', () => {
    const wrapper = mountLog({ events: [] })

    expect(wrapper.find('.section-title').text()).toContain('Event Log')
    expect(wrapper.text()).toContain('No events yet')
    expect(wrapper.find('.no-events').exists()).toBe(true)
    expect(wrapper.find('.event-list').exists()).toBe(false)
  })

  const orderedEvents = [
    makeEvent({ type: 'combat', description: 'First event', time_elapsed_hours: 1.0 }),
    makeEvent({ type: 'loot', description: 'Second event', time_elapsed_hours: 2.0 }),
  ]

  it.each([
    [true, ['Second event', 'First event']],
    [false, ['First event', 'Second event']],
  ])('orders rows newest-first only when reverse is %s', (reverse, expected) => {
    const rows = mountLog({ events: orderedEvents, reverse }).findAll('.event-row')

    expect(rows[0].text()).toContain(expected[0])
    expect(rows[1].text()).toContain(expected[1])
  })

  it('renders the loot line with its rarity on the item chip and the event accent', () => {
    const wrapper = mountLog({ events: [makeLootEvent()] })

    const lootLine = wrapper.find('.loot-line')
    expect(lootLine.exists()).toBe(true)
    expect(lootLine.text()).toContain('Laser rifle (Rare)')
    expect(lootLine.text()).toContain('25 caps')
    expect(wrapper.find('.event-row').attributes('style')).toContain(
      'border-left-color: var(--color-rarity-legendary)'
    )
  })

  it('hides loot line when showLoot is false', () => {
    expect(
      mountLog({ events: [makeLootEvent()], showLoot: false })
        .find('.loot-line')
        .exists()
    ).toBe(false)
  })
})
