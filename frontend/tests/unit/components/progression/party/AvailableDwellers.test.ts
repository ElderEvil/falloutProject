import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import AvailableDwellers from '@/modules/progression/components/party/AvailableDwellers.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

vi.mock('@iconify/vue', () => ({ Icon: { template: '<i />' } }))

const dweller = (id: string, firstName: string, status = 'idle', level = 1): DwellerShort =>
  ({
    id,
    first_name: firstName,
    last_name: 'Dweller',
    level,
    status,
  }) as DwellerShort

const mountList = (props: Record<string, unknown> = {}) =>
  mount(AvailableDwellers, {
    props: {
      dwellers: [],
      selectedIds: [],
      isLoading: false,
      showEligibleBadge: false,
      error: null,
      ...props,
    },
  })

describe('AvailableDwellers', () => {
  it('renders dwellers, marks the selected one and emits toggle on click', async () => {
    const wrapper = mountList({
      dwellers: [dweller('a', 'Lucy'), dweller('b', 'Max')],
      selectedIds: ['b'],
    })

    const items = wrapper.findAll('.dweller-item')
    expect(items).toHaveLength(2)
    expect(wrapper.find('.dweller-name').text()).toBe('Lucy Dweller')
    expect(items[0].find('i').attributes('icon')).toBe('mdi:checkbox-blank-outline')
    expect(items[1].find('i').attributes('icon')).toBe('mdi:checkbox-marked')

    await items[0].trigger('click')
    expect(wrapper.emitted('toggle')).toEqual([['a']])
  })

  it('exposes checkbox semantics bound to the selected state', () => {
    const wrapper = mountList({
      dwellers: [dweller('a', 'Lucy'), dweller('b', 'Max')],
      selectedIds: ['b'],
    })

    const items = wrapper.findAll('.dweller-item')
    expect(items[0].attributes('role')).toBe('checkbox')
    expect(items[0].attributes('tabindex')).toBe('0')
    expect(items[0].attributes('aria-checked')).toBe('false')
    expect(items[1].attributes('aria-checked')).toBe('true')
  })

  it.each(['enter', 'space'])('emits toggle when %s is pressed on a row', async (key) => {
    const wrapper = mountList({ dwellers: [dweller('a', 'Lucy')] })

    await wrapper.find('.dweller-item').trigger(`keydown.${key}`)

    expect(wrapper.emitted('toggle')).toEqual([['a']])
  })

  it('labels resting dwellers as Socializing', () => {
    const wrapper = mountList({ dwellers: [dweller('a', 'Lucy', 'resting')] })

    expect(wrapper.find('.dweller-status').text()).toBe('Socializing')
  })

  it('shows the eligibility spinner instead of the list while loading', () => {
    const wrapper = mountList({ isLoading: true })

    expect(wrapper.find('.loading-dwellers').exists()).toBe(true)
    expect(wrapper.find('.dwellers-list').exists()).toBe(false)
    expect(wrapper.find('.loading-text').text()).toBe('(Loading...)')
  })

  it('shows the generic empty state with a hint when no error is set', () => {
    const wrapper = mountList()

    expect(wrapper.find('.no-dwellers').text()).toContain('No available dwellers found')
    expect(wrapper.find('.hint').text()).toContain('Build more living quarters')
  })

  it('shows the eligibility error in place of the generic empty state', () => {
    const wrapper = mountList({ error: 'Failed to check eligibility' })

    expect(wrapper.find('.no-dwellers').text()).toContain('Failed to check eligibility')
    expect(wrapper.find('.hint').exists()).toBe(false)
  })

  it('shows the level-requirements badge only when asked', () => {
    expect(mountList().find('.eligible-badge').exists()).toBe(false)
    expect(mountList({ showEligibleBadge: true }).find('.eligible-badge').text()).toBe(
      '(Level Requirements Met)'
    )
  })
})
