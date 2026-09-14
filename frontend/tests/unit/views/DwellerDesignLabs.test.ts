import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import DwellerPageLabView from '@/modules/dwellers/views/DwellerPageLabView.vue'
import PanelHeaderLabView from '@/modules/dwellers/views/PanelHeaderLabView.vue'

describe('dweller design labs', () => {
  it('renders the V1 and V1-improved layout variants', () => {
    const wrapper = mount(DwellerPageLabView)

    expect(wrapper.findAll('.variant')).toHaveLength(2)
    expect(wrapper.text()).toContain('V1 — Today')
    expect(wrapper.text()).toContain('V1 improved')
  })

  it('renders the panel header separator variants', () => {
    const wrapper = mount(PanelHeaderLabView)

    expect(wrapper.findAll('.variant')).toHaveLength(6)
    expect(wrapper.text()).toContain('Row rule')
    expect(wrapper.text()).toContain('Bracketed title')
  })
})
