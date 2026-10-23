import { describe, it, expect, vi } from 'vite-plus/test'
import { mount } from '@vue/test-utils'
import MapLegend from '@/modules/map/components/MapLegend.vue'
import MapMarker from '@/modules/map/components/MapMarker.vue'
import { MARKER_TYPES } from '@/modules/map/models/markerTypeMeta'
import { groupColor } from '@/modules/map/models/groupColors'
import type { PlaceGroup } from '@/modules/map/models/map'

const group: PlaceGroup = {
  key: 'gas_station',
  label: 'Gas station',
  icon: 'mdi:gas-station',
  risk: 'low',
  description: '',
  clearable: true,
}
const mountLegend = (props = {}) =>
  mount(MapLegend, { props, global: { stubs: { Icon: true, MapMarker: true } } })

describe('MapLegend', () => {
  it('retains symbolic states independently of place colors', () => {
    const wrapper = mountLegend()
    for (const state of ['Locked', 'Cleared', 'Cooldown', 'Exploring'])
      expect(wrapper.text()).toContain(state)
  })

  it('uses the canonical marker labels', () => {
    const wrapper = mountLegend()
    for (const symbol of MARKER_TYPES) expect(wrapper.text()).toContain(symbol.label)
    expect(wrapper.text()).toContain('Grouped markers')
  })

  it('names the legend region for assistive technology', () => {
    const wrapper = mountLegend()
    expect(wrapper.find('[role="region"]').attributes('aria-label')).toBe('Map legend')
  })

  it('shows the full reference without a nested expand control', () => {
    const wrapper = mountLegend()
    expect(wrapper.text()).toContain('Marker symbols')
    expect(wrapper.text()).toContain('Place status')
    expect(wrapper.find('button').exists()).toBe(false)
  })

  it('renders catalog icons using the actual map marker component', () => {
    const wrapper = mountLegend({ placeGroups: [group] })
    const marker = wrapper.findComponent(MapMarker)
    expect(marker.props('icon')).toBe(group.icon)
    expect(marker.props('interactive')).toBe(false)
    expect(marker.props('color')).toBeNull()
  })

  it('uses the shared optional group colors and stays neutral for unknown groups', () => {
    const wrapper = mountLegend({
      placeGroups: [group, { ...group, key: 'unknown' }],
      groupColors: true,
    })
    const markers = wrapper.findAllComponents(MapMarker)
    expect(markers[0].props('color')).toBe(groupColor(group.key))
    expect(markers[1].props('color')).toBeNull()
  })

  it('works when storage reads are unavailable', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new DOMException('denied', 'SecurityError')
    })
    try {
      expect(mountLegend().text()).toContain('Locked')
    } finally {
      vi.restoreAllMocks()
    }
  })

  it('works when storage writes are unavailable', () => {
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new DOMException('denied', 'QuotaExceededError')
    })
    try {
      expect(mountLegend().text()).toContain('Cooldown')
    } finally {
      vi.restoreAllMocks()
    }
  })
})
