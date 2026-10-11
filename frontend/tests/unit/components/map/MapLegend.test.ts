import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import MapLegend from '@/modules/map/components/MapLegend.vue'

describe('MapLegend', () => {
  beforeEach(() => {
    localStorage.removeItem('map:legend-collapsed')
  })
  function mountLegend(expanded = true) {
    if (expanded) localStorage.setItem('map:legend-collapsed', 'false')
    return mount(MapLegend, { global: { stubs: { Icon: true } } })
  }
  it('uses four symbolic state cues without color catalogs', () => {
    const wrapper = mountLegend()
    expect(wrapper.findAll('.legend-item').map((item) => item.text())).toEqual([
      'Locked',
      'Cleared',
      'Cooldown',
      'Exploring',
    ])
    expect(wrapper.find('details').exists()).toBe(false)
    expect(wrapper.find('.legend-danger').exists()).toBe(false)
  })

  it('should render the MAP KEY title', () => {
    const wrapper = mountLegend()

    expect(wrapper.text()).toContain('MAP KEY')
  })

  it('should have the correct role and aria-label', () => {
    const wrapper = mountLegend()

    const legend = wrapper.find('[role="complementary"]')
    expect(legend.exists()).toBe(true)
    expect(legend.attributes('aria-label')).toBe('Map legend')
  })

  it('collapses and expands so it can uncover content beneath it', async () => {
    const wrapper = mountLegend()
    expect(wrapper.find('.legend-item').exists()).toBe(true)

    await wrapper.find('.legend-toggle').trigger('click')
    expect(wrapper.find('.legend-item').exists()).toBe(false)
    expect(wrapper.find('.legend-toggle').attributes('aria-expanded')).toBe('false')
    expect(localStorage.getItem('map:legend-collapsed')).toBe('true')

    await wrapper.find('.legend-toggle').trigger('click')
    expect(wrapper.find('.legend-item').exists()).toBe(true)
    expect(localStorage.getItem('map:legend-collapsed')).toBe('false')
  })

  it('starts collapsed on first view so it never covers the map', () => {
    const wrapper = mountLegend(false)

    expect(wrapper.find('.legend-item').exists()).toBe(false)
    expect(wrapper.find('.legend-toggle').attributes('aria-expanded')).toBe('false')
  })

  it('restores the stored collapsed state across visits', () => {
    localStorage.setItem('map:legend-collapsed', 'true')
    const wrapper = mount(MapLegend, {
      global: { stubs: { Icon: true } },
    })

    expect(wrapper.find('.legend-item').exists()).toBe(false)
  })

  it('stays collapsed when storage reads throw', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })
    try {
      const wrapper = mountLegend(false)

      expect(wrapper.find('.legend-item').exists()).toBe(false)
    } finally {
      vi.restoreAllMocks()
    }
  })

  it('still toggles when storage writes throw', async () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('denied', 'QuotaExceededError')
    })
    try {
      const wrapper = mountLegend()

      await wrapper.find('.legend-toggle').trigger('click')
      expect(wrapper.find('.legend-item').exists()).toBe(false)

      await wrapper.find('.legend-toggle').trigger('click')
      expect(wrapper.find('.legend-item').exists()).toBe(true)
    } finally {
      vi.restoreAllMocks()
    }
  })
})
