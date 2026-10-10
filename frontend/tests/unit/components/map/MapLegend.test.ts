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

  it('keeps long reference sections collapsed until requested', () => {
    const wrapper = mountLegend()
    const sections = wrapper.findAll('details')
    expect(sections.length).toBeGreaterThanOrEqual(3)
    for (const section of sections) expect(section.attributes('open')).toBeUndefined()
    expect(wrapper.findAll('summary').map((summary) => summary.text())).toContain('TERRAIN')
  })

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

  it('renders the 6 marker-type entries and the marker-state key', () => {
    const wrapper = mountLegend()

    expect(wrapper.findAll('.legend-icon-wrapper')).toHaveLength(6)
    expect(wrapper.findAll('.legend-state-dot')).toHaveLength(6)
    expect(wrapper.text()).toContain('MARKER STATE')
    expect(wrapper.text()).toContain('Known / active')
  })

  it('should render the five terrain swatches', () => {
    const wrapper = mountLegend()

    const terrain = wrapper.findAll('.legend-terrain')
    expect(terrain).toHaveLength(5)
    expect(wrapper.text()).toContain('Wasteland')
    expect(wrapper.text()).toContain('Water')
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

  describe('Site-type filter emphasis', () => {
    const GAS_STATION = {
      key: 'gas_station',
      label: 'Gas Station',
      icon: 'mdi:gas-station',
      risk: 'low',
      description: 'A roadside fuel stop.',
    }
    const MILITARY = {
      key: 'military',
      label: 'Military',
      icon: 'mdi:shield-cross',
      risk: 'high',
      description: 'A fortified base.',
    }

    function mountWithSites(filter: string | null) {
      const store = useMapStore()
      store.placeGroups = [GAS_STATION, MILITARY] as never
      store.locations = [
        { ...discoveryLocation('loc-1'), group_key: 'gas_station' },
        { ...discoveryLocation('loc-2'), group_key: 'military' },
      ] as never
      localStorage.setItem('map:legend-collapsed', 'false')
      return mount(MapLegend, {
        props: { siteTypeFilter: filter },
        global: { stubs: { Icon: true } },
      })
    }

    function siteItem(wrapper: ReturnType<typeof mount>, label: string) {
      const item = wrapper.findAll('.legend-site-item').find((el) => el.text().includes(label))
      expect(item).toBeTruthy()
      return item!
    }

    it('emphasizes the selected archetype and dims the rest', () => {
      const wrapper = mountWithSites('gas_station')

      expect(siteItem(wrapper, 'Gas Station').classes()).toContain('legend-site-selected')
      expect(siteItem(wrapper, 'Gas Station').classes()).not.toContain('legend-site-dimmed')
      expect(siteItem(wrapper, 'Military').classes()).toContain('legend-site-dimmed')
      expect(siteItem(wrapper, 'Military').classes()).not.toContain('legend-site-selected')
    })

    it('leaves every archetype neutral when the filter is null', () => {
      const wrapper = mountWithSites(null)

      for (const item of wrapper.findAll('.legend-site-item')) {
        expect(item.classes()).not.toContain('legend-site-selected')
        expect(item.classes()).not.toContain('legend-site-dimmed')
      }
    })
  })
})
