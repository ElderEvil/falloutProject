import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WorldMap from '@/modules/map/components/WorldMap.vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '@/modules/map/models/map'

// Stub child components that need complex DOM (Iconify, UTooltip)
const MapMarkerStub = {
  name: 'MapMarker',
  props: ['x', 'y', 'name', 'type'],
  template: '<g class="map-marker-stub" />',
}

function createLocations(count: number): WastelandLocationWithDwellers[] {
  return Array.from({ length: count }, (_, i) => ({
    id: `loc-${i}`,
    name: `Location ${i}`,
    normalized_name: `location ${i}`,
    type: (['origin', 'visited', 'discovery', 'home_vault'] as const)[i % 4],
    coord_x: 10 + i * 15,
    coord_y: 20 + i * 10,
    description: `Description for location ${i}`,
    vault_id: 'vault-1',
    exploration_id: null,
    created_at: null,
    dwellers: [],
  }))
}

function createVaultMarkers(count: number): VaultMarkerRead[] {
  return Array.from({ length: count }, (_, i) => ({
    name: `Vault ${100 + i}`,
    coord_x: 30 + i * 10,
    coord_y: 40 + i * 5,
    type: 'vault' as const,
    description: 'Unexplored vault signal',
  }))
}

describe('WorldMap', () => {
  describe('Marker rendering', () => {
    it('should render 7 markers given 3 locations + 4 vault markers', () => {
      const locations = createLocations(3)
      const vaultMarkers = createVaultMarkers(4)

      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers },
        global: {
          stubs: { MapMarker: MapMarkerStub },
        },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(7)
    })

    it('should render zero markers when both arrays are empty', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: {
          stubs: { MapMarker: MapMarkerStub },
        },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(0)
    })

    it('should render only location markers when vaultMarkers is empty', () => {
      const locations = createLocations(5)

      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: {
          stubs: { MapMarker: MapMarkerStub },
        },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(5)
    })
  })

  describe('Grid lines', () => {
    it('should render grid lines every 10 units', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
      })

      // 0..100 step 10 = 11 lines each direction = 22 total
      const lines = wrapper.findAll('line')
      expect(lines).toHaveLength(22)
    })
  })

  describe('CRT styling', () => {
    it('should have crt-screen class on the container', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
      })

      const container = wrapper.find('.world-map-container')
      expect(container.classes()).toContain('crt-screen')
    })

    it('should have the SVG element with correct viewBox', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
      })

      const svg = wrapper.find('svg')
      expect(svg.attributes('viewBox')).toBe('0 0 100 100')
    })
  })

  describe('Marker click emission', () => {
    it('should emit marker-click with kind=location when a location marker is clicked', async () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: {
          stubs: { MapMarker: MapMarkerStub },
        },
      })

      // Access the component VM to trigger the internal handler
      const vm = wrapper.vm as any
      vm.onLocationClick(locations[0])
      await wrapper.vm.$nextTick()

      const emitted = wrapper.emitted('marker-click')
      expect(emitted).toBeTruthy()
      expect(emitted![0][0]).toEqual({ kind: 'location', data: locations[0] })
    })

    it('should emit marker-click with kind=vault when a vault marker is clicked', async () => {
      const vaultMarkers = createVaultMarkers(1)
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers },
        global: {
          stubs: { MapMarker: MapMarkerStub },
        },
      })

      const vm = wrapper.vm as any
      vm.onVaultClick(vaultMarkers[0])
      await wrapper.vm.$nextTick()

      const emitted = wrapper.emitted('marker-click')
      expect(emitted).toBeTruthy()
      expect(emitted![0][0]).toEqual({ kind: 'vault', data: vaultMarkers[0] })
    })
  })

  describe('Empty store (failure case)', () => {
    it('should render the SVG with zero markers and no exceptions', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: {
          stubs: { MapMarker: MapMarkerStub },
        },
      })

      expect(wrapper.find('svg').exists()).toBe(true)
      expect(wrapper.findAll('.map-marker-stub')).toHaveLength(0)
      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })
  })
})
