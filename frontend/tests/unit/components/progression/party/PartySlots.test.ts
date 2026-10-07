import { describe, expect, it, vi } from 'vitest'
import { createIconifyMock } from '../../../helpers/mocks'
import { mount } from '@vue/test-utils'
import PartySlots from '@/modules/progression/components/party/PartySlots.vue'
import type { DwellerShort } from '@/modules/dwellers/models/dweller'

vi.mock('@iconify/vue', () => createIconifyMock({ template: '<i />', props: [] }))

const dweller = (id: string, firstName: string, level = 1): DwellerShort =>
  ({
    id,
    first_name: firstName,
    last_name: 'Dweller',
    level,
    status: 'idle',
  }) as DwellerShort

describe('PartySlots', () => {
  it('renders the selected count, the filled slots and the empty slots', () => {
    const wrapper = mount(PartySlots, {
      props: {
        selectedDwellers: [dweller('a', 'Lucy', 3)],
        selectedCount: 1,
        maxPartySize: 3,
      },
    })

    expect(wrapper.find('.slots-label').text()).toContain('Party Slots (1 / 3)')
    expect(wrapper.find('.slot-name').text()).toBe('Lucy Dweller')
    expect(wrapper.find('.slot-level').text()).toBe('Lv. 3')
    expect(wrapper.findAll('.party-slot.filled')).toHaveLength(1)
    expect(wrapper.findAll('.slot-empty')).toHaveLength(2)
  })

  it('emits remove with the dweller id when the slot remove control is clicked', async () => {
    const wrapper = mount(PartySlots, {
      props: {
        selectedDwellers: [dweller('a', 'Lucy')],
        selectedCount: 1,
        maxPartySize: 1,
      },
    })

    const remove = wrapper.find('.slot-remove')
    expect(remove.attributes('type')).toBe('button')
    expect(remove.attributes('aria-label')).toBe('Remove Lucy Dweller from party')

    await remove.trigger('click')

    expect(wrapper.emitted('remove')).toEqual([['a']])
  })

  it('uses the raw selected count for the header even when an id is unresolvable', () => {
    const wrapper = mount(PartySlots, {
      props: {
        selectedDwellers: [],
        selectedCount: 2,
        maxPartySize: 3,
      },
    })

    expect(wrapper.find('.slots-label').text()).toContain('Party Slots (2 / 3)')
    expect(wrapper.findAll('.slot-empty')).toHaveLength(3)
  })
})
