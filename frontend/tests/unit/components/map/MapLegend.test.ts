import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import MapLegend from '@/modules/map/components/MapLegend.vue'
import { useMapStore, VIEWED_LOCATIONS_STORAGE_KEY } from '@/modules/map/stores/map'

function discoveryLocation(id: string, is_unlocked = true) {
  return {
    id,
    name: `Discovery ${id}`,
    normalized_name: `discovery ${id}`,
    type: 'discovery' as const,
    coord_x: 10,
    coord_y: 20,
    description: 'An uncharted signal',
    vault_id: 'vault-1',
    exploration_id: null,
    created_at: null,
    is_unlocked,
    dwellers: [],
  }
}

describe('MapLegend', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem(VIEWED_LOCATIONS_STORAGE_KEY)
    localStorage.removeItem('map:legend-collapsed')
  })

  function mountLegend(expanded = true) {
    if (expanded) localStorage.setItem('map:legend-collapsed', 'false')
    return mount(MapLegend, {
      global: { stubs: { Icon: true } },
    })
  }

  function discoveryWrapper(wrapper: ReturnType<typeof mount>) {
    const items = wrapper.findAll('.legend-icon-wrapper')
    return items[3]
  }

  it('should render the MAP KEY title', () => {
    const wrapper = mountLegend()

    expect(wrapper.text()).toContain('MAP KEY')
  })

  it('should render all six marker type entries', () => {
    const wrapper = mountLegend()

    expect(wrapper.text()).toContain('Home Vault')
    expect(wrapper.text()).toContain('Origin')
    expect(wrapper.text()).toContain('Visited')
    expect(wrapper.text()).toContain('Discovery')
    expect(wrapper.text()).toContain('Vault Signal')
    expect(wrapper.text()).toContain('Expedition Sites')
  })

  it('should have the correct role and aria-label', () => {
    const wrapper = mountLegend()

    const legend = wrapper.find('[role="complementary"]')
    expect(legend.exists()).toBe(true)
    expect(legend.attributes('aria-label')).toBe('Map legend')
  })

  it('should render exactly 6 legend items', () => {
    const wrapper = mountLegend()

    const items = wrapper.findAll('.legend-item')
    expect(items).toHaveLength(6)
  })

  it('should render the five biome swatches plus the road and river overlays', () => {
    const wrapper = mountLegend()

    const terrain = wrapper.findAll('.legend-terrain')
    expect(terrain).toHaveLength(7)
    expect(wrapper.text()).toContain('Wasteland')
    expect(wrapper.text()).toContain('Water')
    expect(wrapper.text()).toContain('Road')
    expect(wrapper.text()).toContain('River')
  })

  it('should render an icon for each marker type', () => {
    const wrapper = mountLegend()

    const icons = wrapper.findAll('.legend-icon-wrapper')
    expect(icons).toHaveLength(6)
  })

  it('pulses the discovery icon while an unseen discovery exists', () => {
    const store = useMapStore()
    store.locations = [discoveryLocation('loc-1')]

    const wrapper = mountLegend()

    expect(discoveryWrapper(wrapper).classes()).toContain('legend-unseen')
  })

  it('renders the discovery icon static once all discoveries are viewed', async () => {
    const store = useMapStore()
    store.locations = [discoveryLocation('loc-1')]

    const wrapper = mountLegend()
    expect(discoveryWrapper(wrapper).classes()).toContain('legend-unseen')

    store.markLocationViewed('vault-1', 'loc-1')
    await wrapper.vm.$nextTick()

    expect(discoveryWrapper(wrapper).classes()).not.toContain('legend-unseen')
  })

  it('renders the discovery icon static when no discoveries exist', () => {
    const store = useMapStore()
    store.locations = []

    const wrapper = mountLegend()

    expect(discoveryWrapper(wrapper).classes()).not.toContain('legend-unseen')
  })

  it('renders the discovery icon static when discoveries are still locked', () => {
    const store = useMapStore()
    store.locations = [discoveryLocation('loc-1', false)]

    const wrapper = mountLegend()

    expect(discoveryWrapper(wrapper).classes()).not.toContain('legend-unseen')
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
