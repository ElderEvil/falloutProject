import { describe, it, expect, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import SpecialGuideModal from '@/modules/dwellers/components/stats/SpecialGuideModal.vue'
import { SPECIAL_GUIDE } from '@/modules/dwellers/models/specialGuide'

vi.mock('@iconify/vue', () => ({ Icon: { template: '<i />' } }))

describe('SpecialGuideModal', () => {
  it('should render all seven guide entries when open', () => {
    const wrapper = mount(SpecialGuideModal, {
      props: { modelValue: true },
      global: {
        stubs: {
          Teleport: { template: '<div><slot /></div>' },
        },
      },
    })
    expect(wrapper.findAll('.guide-entry')).toHaveLength(7)
    expect(wrapper.findAll('.guide-letter').map((l) => l.text())).toEqual([
      'S',
      'P',
      'E',
      'C',
      'I',
      'A',
      'L',
    ])
  })

  it('should render nothing when closed', () => {
    const wrapper = mount(SpecialGuideModal, {
      props: { modelValue: false },
      global: {
        stubs: {
          Teleport: { template: '<div><slot /></div>' },
        },
      },
    })
    expect(wrapper.find('.guide-entry').exists()).toBe(false)
  })

  it('should explain bars alongside stats', () => {
    const wrapper = mount(SpecialGuideModal, {
      props: { modelValue: true },
      global: {
        stubs: {
          Teleport: { template: '<div><slot /></div>' },
        },
      },
    })
    expect(wrapper.find('.guide-bars').text()).toContain('Numbers always rule over bars')
  })

  it('should keep guide data strictly mechanical', () => {
    for (const entry of SPECIAL_GUIDE) {
      expect(entry.effects.length).toBeGreaterThan(0)
    }
  })
})
