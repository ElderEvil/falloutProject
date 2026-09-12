import { describe, it, expect, beforeEach } from 'vitest'
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
  })

  function mountLegend() {
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

  it('should render all five marker type entries', () => {
    const wrapper = mountLegend()

    expect(wrapper.text()).toContain('Home Vault')
    expect(wrapper.text()).toContain('Origin')
    expect(wrapper.text()).toContain('Visited')
    expect(wrapper.text()).toContain('Discovery')
    expect(wrapper.text()).toContain('Vault Signal')
  })

  it('should have the correct role and aria-label', () => {
    const wrapper = mountLegend()

    const legend = wrapper.find('[role="complementary"]')
    expect(legend.exists()).toBe(true)
    expect(legend.attributes('aria-label')).toBe('Map legend')
  })

  it('should render exactly 5 legend items', () => {
    const wrapper = mountLegend()

    const items = wrapper.findAll('.legend-item')
    expect(items).toHaveLength(5)
  })

  it('should render an icon for each marker type', () => {
    const wrapper = mountLegend()

    const icons = wrapper.findAll('.legend-icon-wrapper')
    expect(icons).toHaveLength(5)
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
})
