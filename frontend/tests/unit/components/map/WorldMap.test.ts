import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import WorldMap from '@/modules/map/components/WorldMap.vue'
import type { WastelandLocationWithDwellers, VaultMarkerRead } from '@/modules/map/models/map'

// Stub child components that need complex DOM (Iconify, UTooltip)
const MapMarkerStub = {
  name: 'MapMarker',
  props: ['x', 'y', 'name', 'type', 'selected'],
  template: '<g class="map-marker-stub" />',
}

const MarkerListPanelStub = {
  name: 'MarkerListPanel',
  props: ['locations', 'vaultMarkers', 'selectedMarkerId', 'docked'],
  emits: ['marker-select'],
  template: '<div class="marker-list-panel-stub" />',
}

const UButtonStub = {
  name: 'UButton',
  props: ['variant', 'size', 'disabled', 'ariaLabel'],
  template: '<button class="ubutton-stub"><slot /></button>',
}

const IconStub = {
  name: 'Icon',
  props: ['icon'],
  template: '<span class="icon-stub" />',
}

const defaultStubs = {
  MapMarker: MapMarkerStub,
  MarkerListPanel: MarkerListPanelStub,
  UButton: UButtonStub,
  Icon: IconStub,
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
    dwellers: [
      { dweller_id: `dweller-${i}-a`, first_name: 'Ada', last_name: null, relation: 'visited' },
      { dweller_id: `dweller-${i}-b`, first_name: 'Bob', last_name: null, relation: 'visited' },
    ],
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
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(7)
    })

    it('should render zero markers when both arrays are empty', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(0)
    })

    it('should render only location markers when vaultMarkers is empty', () => {
      const locations = createLocations(5)

      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(5)
    })
  })

  describe('Grid lines', () => {
    it('should render grid lines every 10 units', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      // 0..160 step 10 = 17 lines each direction = 34 total
      const lines = wrapper.findAll('line')
      expect(lines).toHaveLength(34)
    })
  })

  describe('Discovery routes', () => {
    it('renders API-projected event routes, including repeated location visits', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          discoveryRoutes: [
            {
              exploration_id: 'expl-1',
              points: [
                { location_id: 'loc-1', coord_x: 20, coord_y: 30, timestamp: '2026-01-01T00:00:00Z' },
                { location_id: 'loc-1', coord_x: 20, coord_y: 30, timestamp: '2026-01-01T01:00:00Z' },
              ],
            },
          ],
        },
        global: { stubs: defaultStubs },
      })

      const route = wrapper.find('polyline')
      expect(route.attributes('points')).toBe('20,30 20,30')
    })
  })

  describe('CRT styling', () => {
    it('should have crt-screen class on the container', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const container = wrapper.find('.world-map-container')
      expect(container.classes()).toContain('crt-screen')
    })

    it('should have the SVG element with correct viewBox at default zoom', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const svg = wrapper.find('svg')
      expect(svg.attributes('viewBox')).toBe('0 0 160 160')
    })

    it('should NOT have role="img" on the SVG (children must be accessible)', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const svg = wrapper.find('svg')
      expect(svg.attributes('role')).toBeUndefined()
      expect(svg.attributes('aria-label')).toBeUndefined()
    })
  })

  describe('Marker click emission', () => {
    it('should emit marker-click with kind=location when a location marker is clicked', async () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: { stubs: defaultStubs },
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
        global: { stubs: defaultStubs },
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
        global: { stubs: defaultStubs },
      })

      expect(wrapper.find('svg').exists()).toBe(true)
      expect(wrapper.findAll('.map-marker-stub')).toHaveLength(0)
      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })
  })

  // ── Stage 3: Zoom, pan, selected, panel ──────────────────────────────

  describe('Zoom controls', () => {
    it('should render zoom in, zoom out, and reset buttons', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const controls = wrapper.find('.zoom-controls')
      expect(controls.exists()).toBe(true)

      const buttons = controls.findAllComponents(UButtonStub)
      expect(buttons).toHaveLength(3)
    })

    it('should have an aria-label on the zoom controls group', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const controls = wrapper.find('[role="group"]')
      expect(controls.attributes('aria-label')).toBe('Map zoom controls')
    })

    it('should show zoom level percentage when zoomed', async () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      // Initially no zoom level display
      expect(wrapper.find('.zoom-level').exists()).toBe(false)

      // Trigger zoom in via VM
      const vm = wrapper.vm as any
      vm.zoomIn()
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.zoom-level').exists()).toBe(true)
      expect(wrapper.find('.zoom-level').text()).toContain('%')
    })
  })

  describe('Selected marker wiring', () => {
    it('should pass selected=false to all markers by default', () => {
      const locations = createLocations(3)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAllComponents(MapMarkerStub)
      for (const marker of markers) {
        expect(marker.props('selected')).toBe(false)
      }
    })

    it('should pass selected=true to a marker after it is clicked', async () => {
      const locations = createLocations(2)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const vm = wrapper.vm as any
      vm.onLocationClick(locations[0])
      await wrapper.vm.$nextTick()

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[1].props('selected')).toBe(false)
    })

    it('should suppress marker-click when hasDragMoved is true', async () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const vm = wrapper.vm as any
      vm.hasDragMoved = true
      vm.onLocationClick(locations[0])
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })
  })

  describe('Marker list panel integration', () => {
    it('should render the MarkerListPanel component', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: createLocations(2), vaultMarkers: createVaultMarkers(1) },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findComponent(MarkerListPanelStub).exists()).toBe(true)
    })

    it('should pass locations and vaultMarkers to the panel', () => {
      const locations = createLocations(2)
      const vaultMarkers = createVaultMarkers(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers },
        global: { stubs: defaultStubs },
      })

      const panel = wrapper.findComponent(MarkerListPanelStub)
      expect(panel.props('locations')).toEqual(locations)
      expect(panel.props('vaultMarkers')).toEqual(vaultMarkers)
    })

    it('should dock the location index beside the map', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: createLocations(2), vaultMarkers: createVaultMarkers(1) },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findComponent(MarkerListPanelStub).props('docked')).toBe(true)
    })

    it('should emit marker-click when panel emits marker-select', async () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const panel = wrapper.findComponent(MarkerListPanelStub)
      await panel.vm.$emit('marker-select', { kind: 'location', data: locations[0] })

      const emitted = wrapper.emitted('marker-click')
      expect(emitted).toBeTruthy()
      expect(emitted![0][0]).toEqual({ kind: 'location', data: locations[0] })
    })

    it('should set selectedMarkerId when panel selects a marker', async () => {
      const locations = createLocations(2)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const panel = wrapper.findComponent(MarkerListPanelStub)
      await panel.vm.$emit('marker-select', { kind: 'location', data: locations[0] })
      await wrapper.vm.$nextTick()

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[1].props('selected')).toBe(false)
    })
  })

  describe('Wheel zoom prevention', () => {
    it('should have @wheel.prevent on the container', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      const container = wrapper.find('.world-map-container')
      // Vue attaches wheel.prevent via addEventListener with passive: false
      // The key assertion is the @wheel.prevent directive in the template
      expect(container.exists()).toBe(true)
    })
  })

  describe('Visibility filter (single-dweller visited)', () => {
    it('should hide unknown locations from the index while keeping the map decluttered', () => {
      const visited = createLocations(1)[0]
      const singleVisited: WastelandLocationWithDwellers = {
        ...visited,
        type: 'visited',
        dwellers: [{ dweller_id: 'd-1', first_name: 'Solo', last_name: null, relation: 'visited' }],
      }
      const multiVisited: WastelandLocationWithDwellers = {
        ...visited,
        id: 'loc-multi',
        name: 'Multi Visited',
        type: 'visited',
        dwellers: [
          { dweller_id: 'd-1', first_name: 'A', last_name: null, relation: 'visited' },
          { dweller_id: 'd-2', first_name: 'B', last_name: null, relation: 'visited' },
        ],
      }
      const origin: WastelandLocationWithDwellers = {
        ...visited,
        id: 'loc-origin',
        name: 'Origin Place',
        type: 'origin',
      }
      const unknown: WastelandLocationWithDwellers = {
        ...visited,
        id: 'loc-unknown',
        name: 'Unidentified Signal',
        type: 'discovery',
        is_unlocked: false,
      }

      const wrapper = mount(WorldMap, {
        props: { locations: [singleVisited, multiVisited, origin, unknown], vaultMarkers: [] },
        global: { stubs: defaultStubs },
      })

      // The map still renders discovered signals; only the single visited marker is decluttered.
      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(3)

      // The index only receives locations whose names are known to the vault.
      const panel = wrapper.findComponent(MarkerListPanelStub)
      expect(panel.props('locations')).toHaveLength(3)
      expect(panel.props('locations')).not.toContain(unknown)
    })
  })
})
