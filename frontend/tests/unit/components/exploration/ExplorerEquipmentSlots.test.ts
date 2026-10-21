import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createIconifyMock } from '../../helpers/mocks'
import ExplorerEquipmentSlots from '@/modules/exploration/components/ExplorerEquipmentSlots.vue'

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<span class="icon-mock" :data-icon="icon" />' })
)

const baseProps = {
  weaponName: null,
  outfitName: null,
  petName: null,
}

describe('ExplorerEquipmentSlots', () => {
  it('uses a fist icon when the explorer is unarmed', () => {
    const wrapper = mount(ExplorerEquipmentSlots, { props: baseProps })

    expect(wrapper.find('[data-icon="fa6-solid:hand-fist"]').exists()).toBe(true)
    expect(wrapper.text()).toContain('Unarmed')
  })

  it('keeps the weapon icon when the explorer is armed', () => {
    const wrapper = mount(ExplorerEquipmentSlots, {
      props: { ...baseProps, weaponName: '10mm Pistol', weapon: { weapon_subtype: 'pistol' } },
    })

    expect(wrapper.find('[data-icon="mdi:pistol"]').exists()).toBe(true)
  })
})
