import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import MapLegend from '@/modules/map/components/MapLegend.vue'

describe('MapLegend', () => {
  it('should render the MAP KEY title', () => {
    const wrapper = mount(MapLegend, {
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('MAP KEY')
  })

  it('should render all five marker type entries', () => {
    const wrapper = mount(MapLegend, {
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.text()).toContain('Home Vault')
    expect(wrapper.text()).toContain('Origin')
    expect(wrapper.text()).toContain('Visited')
    expect(wrapper.text()).toContain('Discovery')
    expect(wrapper.text()).toContain('Vault Signal')
  })

  it('should have the correct role and aria-label', () => {
    const wrapper = mount(MapLegend, {
      global: { stubs: { Icon: true } },
    })

    const legend = wrapper.find('[role="complementary"]')
    expect(legend.exists()).toBe(true)
    expect(legend.attributes('aria-label')).toBe('Map legend')
  })

  it('should render exactly 5 legend items', () => {
    const wrapper = mount(MapLegend, {
      global: { stubs: { Icon: true } },
    })

    const items = wrapper.findAll('.legend-item')
    expect(items).toHaveLength(5)
  })

  it('should render an icon for each marker type', () => {
    const wrapper = mount(MapLegend, {
      global: { stubs: { Icon: true } },
    })

    const icons = wrapper.findAll('.legend-icon-wrapper')
    expect(icons).toHaveLength(5)
  })
})
