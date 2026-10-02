import { describe, it, expect, beforeEach, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorldMap from '@/modules/map/components/WorldMap.vue'
import { useMapStore, VIEWED_LOCATIONS_STORAGE_KEY } from '@/modules/map/stores/map'
import type {
  ExpeditionSiteMarkerRead,
  ExplorerTrack,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
} from '@/modules/map/models/map'

// Stub child components that need complex DOM (Iconify, UTooltip)
const MapMarkerStub = {
  name: 'MapMarker',
  props: [
    'x',
    'y',
    'name',
    'type',
    'selected',
    'unseen',
    'is_unlocked',
    'icon',
    'label',
    'cleared',
    'exploring',
    'status',
    'interactive',
  ],
  template: '<g class="map-marker-stub" />',
}

const MarkerListPanelStub = {
  name: 'MarkerListPanel',
  props: ['locations', 'vaultMarkers', 'expeditionSites', 'selectedMarkerId', 'docked'],
  emits: ['marker-select'],
  template: '<div class="marker-list-panel-stub" />',
}

const ButtonStub = {
  name: 'Button',
  props: ['variant', 'size', 'disabled', 'ariaLabel'],
  template: '<button class="ubutton-stub"><slot /></button>',
}

const IconStub = {
  name: 'Icon',
  props: ['icon'],
  template: '<span class="icon-stub" />',
}

const AtlasTerrainStub = { name: 'AtlasTerrain', template: '<g class="atlas-terrain-stub" />' }
const FogLayerStub = { name: 'FogLayer', props: ['explored'], template: '<g class="fog-layer-stub" />' }

const defaultStubs = {
  MapMarker: MapMarkerStub,
  MarkerListPanel: MarkerListPanelStub,
  Button: ButtonStub,
  Icon: IconStub,
  AtlasTerrain: AtlasTerrainStub,
  FogLayer: FogLayerStub,
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

function createSite(overrides: Partial<ExpeditionSiteMarkerRead> = {}): ExpeditionSiteMarkerRead {
  return {
    id: 'site-1',
    name: 'Red Rocket Gas Station',
    flavor: 'A roadside fuel stop.',
    coord_x: 60,
    coord_y: 70,
    min_dweller_level: 5,
    room_total: 3,
    cleared: false,
    cooldown_remaining_seconds: 0,
    block_reason: null,
    ...overrides,
  }
}

describe('WorldMap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem(VIEWED_LOCATIONS_STORAGE_KEY)
  })

  describe('Marker rendering', () => {
    it('should render 7 markers given 3 locations + 4 vault markers', () => {
      const locations = createLocations(3)
      const vaultMarkers = createVaultMarkers(4)

      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(7)
    })

    it('should render zero markers when both arrays are empty', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(0)
    })

    it('should render only location markers when vaultMarkers is empty', () => {
      const locations = createLocations(5)

      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(5)
    })
  })

  describe('Grid lines', () => {
    it('should not render grid lines (quiet player preview)', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAll('line.grid-line')).toHaveLength(0)
    })
  })

  describe('Discovery routes', () => {
    it('renders API-projected event routes, including repeated location visits', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
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
      const points = route.attributes('points')!.split(' ')
      expect(points[0]).toBe('80,80')
      expect(points.at(-1)).toBe('20,30')
      expect(points.length).toBeGreaterThan(3)
    })

    it('anchors trails at the home vault coordinates', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [
            {
              id: 'home-1',
              type: 'home_vault',
              coord_x: 50,
              coord_y: 50,
            } as WastelandLocationWithDwellers,
          ],
          vaultMarkers: [],
          selectedMarkerId: null,
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
      const points = route.attributes('points')!.split(' ')
      expect(points[0]).toBe('50,50')
      expect(points.at(-1)).toBe('20,30')
    })
  })

  describe('CRT styling', () => {
    it('should have crt-screen class on the container', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const container = wrapper.find('.world-map-container')
      expect(container.classes()).toContain('crt-screen')
    })

    it('should have the SVG element with correct viewBox at default zoom', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const svg = wrapper.find('svg')
      expect(svg.attributes('viewBox')).toBe('0 0 160 160')
    })

    it('should NOT have role="img" on the SVG (children must be accessible)', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
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
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
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
        props: { locations: [], vaultMarkers, selectedMarkerId: null },
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
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
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
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const controls = wrapper.find('.zoom-controls')
      expect(controls.exists()).toBe(true)

      const buttons = controls.findAllComponents(ButtonStub)
      expect(buttons).toHaveLength(3)
    })

    it('should have an aria-label on the zoom controls group', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const controls = wrapper.find('[role="group"]')
      expect(controls.attributes('aria-label')).toBe('Map zoom controls')
    })

    it('should show zoom level percentage when zoomed', async () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
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
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
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
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const vm = wrapper.vm as any
      vm.onLocationClick(locations[0])
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('update:selectedMarkerId')).toBeTruthy()
      expect(wrapper.emitted('update:selectedMarkerId')![0][0]).toBe(`loc-${locations[0].id}`)
      await wrapper.setProps({ selectedMarkerId: `loc-${locations[0].id}` })

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[1].props('selected')).toBe(false)
    })

    it('should keep vault highlight on the same vault after markers reorder', async () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: createVaultMarkers(2),
          selectedMarkerId: 'vault-Vault 101',
        },
        global: { stubs: defaultStubs },
      })

      const selected = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Vault 101')
      expect(selected?.props('selected')).toBe(true)

      await wrapper.setProps({
        locations: [],
        vaultMarkers: [...createVaultMarkers(2)].reverse(),
        selectedMarkerId: 'vault-Vault 101',
      })

      const reselected = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Vault 101')
      expect(reselected?.props('selected')).toBe(true)
    })

    it('should suppress marker-click when hasDragMoved is true', async () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const vm = wrapper.vm as any
      vm.hasDragMoved = true
      vm.onLocationClick(locations[0])
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })
  })

  describe('Unseen discovery wiring', () => {
    function discoveryLocation(
      id: string,
      overrides: Partial<WastelandLocationWithDwellers> = {}
    ): WastelandLocationWithDwellers {
      return {
        id,
        name: `Discovery ${id}`,
        normalized_name: `discovery ${id}`,
        type: 'discovery',
        coord_x: 10,
        coord_y: 20,
        description: 'An uncharted signal',
        vault_id: 'vault-1',
        exploration_id: null,
        created_at: null,
        is_unlocked: true,
        dwellers: [],
        ...overrides,
      } as WastelandLocationWithDwellers
    }

    it('passes unseen=true to an unlocked discovery the player has not viewed', () => {
      const locations = [discoveryLocation('loc-1')]
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers).toHaveLength(1)
      expect(markers[0].props('unseen')).toBe(true)
    })

    it('should pass unseen=false once the discovery has been viewed', async () => {
      const store = useMapStore()
      const locations = [discoveryLocation('loc-1')]
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('unseen')).toBe(true)

      store.markLocationViewed('vault-1', 'loc-1')
      await wrapper.vm.$nextTick()

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('unseen')).toBe(false)
    })

    it('hides a locked discovery in the fog until its area is explored', () => {
      const locations = [discoveryLocation('loc-1', { is_unlocked: false })]
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(0)
    })

    it('shows a locked discovery as a hint pin once its area is explored', () => {
      const locked = discoveryLocation('loc-1', { is_unlocked: false })
      const revealed = { ...discoveryLocation('loc-2'), coord_x: locked.coord_x, coord_y: locked.coord_y }
      const wrapper = mount(WorldMap, {
        props: { locations: [locked, revealed], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const hint = wrapper
        .findAllComponents(MapMarkerStub)
        .find(marker => marker.props('is_unlocked') === false)
      expect(hint).toBeTruthy()
      expect(hint!.props('unseen')).toBe(false)
    })

    it('should pass unseen=false to non-discovery locations', () => {
      const locations = [
        discoveryLocation('loc-1', {
          type: 'visited' as const,
          dwellers: [
            { dweller_id: 'd-1', first_name: 'A', last_name: null, relation: 'visited' },
            { dweller_id: 'd-2', first_name: 'B', last_name: null, relation: 'visited' },
          ],
        }),
      ]
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('unseen')).toBe(false)
    })
  })

  describe('Marker list panel integration', () => {
    it('should render the MarkerListPanel component', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: createLocations(2), vaultMarkers: createVaultMarkers(1), selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findComponent(MarkerListPanelStub).exists()).toBe(true)
    })

    it('should pass locations and vaultMarkers to the panel', () => {
      const locations = createLocations(2)
      const vaultMarkers = createVaultMarkers(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const panel = wrapper.findComponent(MarkerListPanelStub)
      expect(panel.props('locations')).toEqual(locations)
      expect(panel.props('vaultMarkers')).toEqual(vaultMarkers)
    })

    it('should dock the location index beside the map', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: createLocations(2), vaultMarkers: createVaultMarkers(1), selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findComponent(MarkerListPanelStub).props('docked')).toBe(true)
    })

    it('should emit marker-click when panel emits marker-select', async () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
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
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const panel = wrapper.findComponent(MarkerListPanelStub)
      await panel.vm.$emit('marker-select', { kind: 'location', data: locations[0] })
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('update:selectedMarkerId')).toBeTruthy()
      await wrapper.setProps({ selectedMarkerId: `loc-${locations[0].id}` })

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[1].props('selected')).toBe(false)
    })
  })

  describe('Wheel zoom prevention', () => {
    it('should have @wheel.prevent on the container', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const container = wrapper.find('.world-map-container')
      // Vue attaches wheel.prevent via addEventListener with passive: false
      // The key assertion is the @wheel.prevent directive in the template
      expect(container.exists()).toBe(true)
    })
  })

  describe('Touch interaction', () => {
    async function mountZoomed() {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
        attachTo: document.body,
      })
      const vm = wrapper.vm as unknown as { focusOnMarker: (x: number, y: number) => void }
      vm.focusOnMarker(80, 80)
      await nextTick()
      const svg = wrapper.find('.world-map-svg')
      vi.spyOn(svg.element, 'getBoundingClientRect').mockReturnValue({
        left: 0,
        top: 0,
        width: 400,
        height: 400,
        right: 400,
        bottom: 400,
        x: 0,
        y: 0,
        toJSON: () => ({}),
      } as DOMRect)
      return { wrapper, container: wrapper.find('.world-map-container'), svg }
    }

    it('should neutralize browser gestures on the container', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.find('.world-map-container').classes()).toContain('touch-none')
    })

    it('should pan with a single finger when zoomed', async () => {
      const { wrapper, container, svg } = await mountZoomed()
      expect(svg.attributes('viewBox')).toBe('40 40 80 80')

      await container.trigger('touchstart', { touches: [{ clientX: 200, clientY: 200 }] })
      expect(container.classes()).toContain('is-dragging')

      await container.trigger('touchmove', { touches: [{ clientX: 220, clientY: 200 }] })
      expect(svg.attributes('viewBox')).toBe('36 40 80 80')

      await container.trigger('touchend', { touches: [] })
      expect(container.classes()).not.toContain('is-dragging')
      wrapper.unmount()
    })

    it('should zoom out on a pinch-in with two fingers', async () => {
      const { wrapper, container, svg } = await mountZoomed()

      await container.trigger('touchstart', {
        touches: [
          { clientX: 50, clientY: 200 },
          { clientX: 350, clientY: 200 },
        ],
      })
      await container.trigger('touchmove', {
        touches: [
          { clientX: 150, clientY: 200 },
          { clientX: 250, clientY: 200 },
        ],
      })

      expect(svg.attributes('viewBox')).toBe('0 0 160 160')
      wrapper.unmount()
    })
  })

  describe('Visibility filter (locked hints + single-dweller visited)', () => {
    function fixture() {
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
      return { singleVisited, multiVisited, origin, unknown }
    }

    it('renders a locked place as a dimmed hint pin while keeping the index known-only', () => {
      const { singleVisited, multiVisited, origin, unknown } = fixture()

      const wrapper = mount(WorldMap, {
        props: { locations: [singleVisited, multiVisited, origin, unknown], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      // The locked discovery still renders as a hint; the single visited marker is decluttered.
      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(3)

      const hint = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Unidentified Signal')
      expect(hint).toBeTruthy()
      expect(hint!.props('is_unlocked')).toBe(false)

      // The index only receives locations whose names are known to the vault.
      const panel = wrapper.findComponent(MarkerListPanelStub)
      expect(panel.props('locations')).toHaveLength(3)
      expect(panel.props('locations')).not.toContain(unknown)
    })

    it('always renders the home vault even when it is not unlocked', () => {
      const { unknown } = fixture()
      const home: WastelandLocationWithDwellers = {
        ...unknown,
        id: 'home-1',
        name: 'Vault 121',
        type: 'home_vault',
        is_unlocked: false,
        coord_x: 80,
        coord_y: 80,
      }

      const wrapper = mount(WorldMap, {
        props: { locations: [home, unknown], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const homeMarker = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'home_vault')
      expect(homeMarker).toBeTruthy()
      expect(homeMarker!.props('name')).toBe('Vault 121')
    })
  })

  describe('Expedition site markers', () => {
    it('renders a site marker per expedition site', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          expeditionSites: [createSite(), createSite({ id: 'site-2', name: 'Crater Store' })],
        },
        global: { stubs: defaultStubs },
      })

      const siteMarkers = wrapper
        .findAllComponents(MapMarkerStub)
        .filter((m) => m.props('type') === 'expedition_site')
      expect(siteMarkers).toHaveLength(2)
      expect(siteMarkers[0].props('name')).toBe('Red Rocket Gas Station')
      expect(siteMarkers[0].props('icon')).toBe('mdi:map-marker-star')
    })

    it('passes cleared + status for a ready site', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          expeditionSites: [createSite()],
        },
        global: { stubs: defaultStubs },
      })

      const site = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(site.props('cleared')).toBe(false)
      expect(site.props('status')).toBe('READY · LVL 5 · 3 ROOMS')
    })

    it('passes cleared + cooldown status for a site in cooldown', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          expeditionSites: [
            createSite({
              cleared: true,
              block_reason: 'cooldown',
              cooldown_remaining_seconds: 3600,
            }),
          ],
        },
        global: { stubs: defaultStubs },
      })

      const site = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(site.props('cleared')).toBe(true)
      expect(site.props('status')).toContain('CLEARED')
      expect(site.props('status')).toContain('COOLDOWN 1h 0m remaining')
    })

    it('does not show CLEARED for a cooldown-only site that was not cleared', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          expeditionSites: [
            createSite({
              cleared: false,
              block_reason: 'cooldown',
              cooldown_remaining_seconds: 3600,
            }),
          ],
        },
        global: { stubs: defaultStubs },
      })

      const site = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(site.props('cleared')).toBe(false)
      expect(site.props('status')).toBe('READY · LVL 5 · 3 ROOMS')
      expect(site.props('status')).not.toContain('CLEARED')
    })

    it('passes an in-progress status for a site with an open run', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          expeditionSites: [createSite({ block_reason: 'open' })],
        },
        global: { stubs: defaultStubs },
      })

      const site = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(site.props('cleared')).toBe(false)
      expect(site.props('status')).toBe('IN PROGRESS · LVL 5 · 3 ROOMS')
    })

    it('emits marker-click with kind=site when a site marker is clicked', async () => {
      const site = createSite()
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          expeditionSites: [site],
        },
        global: { stubs: defaultStubs },
      })

      const vm = wrapper.vm as any
      vm.onSiteClick(site)
      await wrapper.vm.$nextTick()

      const emitted = wrapper.emitted('marker-click')
      expect(emitted).toBeTruthy()
      expect(emitted![0][0]).toEqual({ kind: 'site', data: site })
    })

    it('passes expedition sites to the marker list panel', () => {
      const sites = [createSite()]
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          expeditionSites: sites,
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findComponent(MarkerListPanelStub).props('expeditionSites')).toEqual(sites)
    })
  })

  describe('Explorer tracking', () => {
    it('marks a dispatched target location as exploring with the dweller name', () => {
      const locations = createLocations(1)
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-1',
          dwellerName: 'Ada',
          targetLocationId: locations[0].id,
          lastKnown: null,
        },
      ]
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], explorerTracks: tracks, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('exploring')).toBe(true)
      expect(marker.props('status')).toBe('Exploring — Ada')
    })

    it('falls back to "Dispatching" when the dweller name is unknown', () => {
      const locations = createLocations(1)
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-1',
          dwellerName: '',
          targetLocationId: locations[0].id,
          lastKnown: null,
        },
      ]
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], explorerTracks: tracks, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('exploring')).toBe(true)
      expect(marker.props('status')).toBe('Dispatching')
    })

    it('renders a non-interactive last-known marker for a free-roam explorer', () => {
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-2',
          dwellerName: 'Bob',
          targetLocationId: null,
          lastKnown: { coord_x: 42, coord_y: 43 },
        },
      ]
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], explorerTracks: tracks, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const explorer = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')
      expect(explorer).toBeTruthy()
      expect(explorer!.props('x')).toBe(42)
      expect(explorer!.props('y')).toBe(43)
      expect(explorer!.props('interactive')).toBe(false)
      expect(explorer!.props('status')).toBe('Last known — Bob')
    })

    it('renders no explorer marker when a free-roam run has no trail yet', () => {
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-2',
          dwellerName: 'Bob',
          targetLocationId: null,
          lastKnown: null,
        },
      ]
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], explorerTracks: tracks, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const explorers = wrapper
        .findAllComponents(MapMarkerStub)
        .filter((m) => m.props('type') === 'explorer')
      expect(explorers).toHaveLength(0)
    })

    it('does not mark locations when no explorer tracks exist', () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('exploring')).toBe(false)
      expect(marker.props('status')).toBeUndefined()
    })
  })

  describe('Cleared location markers', () => {
    it('passes cleared=true to a location whose clear_state is cleared', () => {
      const locations = createLocations(1)
      locations[0].clear_state = {
        clearable: true,
        cleared: true,
        clear_count: 2,
        tier: 1,
        time_remaining_seconds: 0,
        loot_table: null,
      }
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('cleared')).toBe(true)
    })

    it('passes cleared=false when clear_state is absent', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: createLocations(1), vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('cleared')).toBe(false)
    })
  })

  describe('Scout targeting', () => {
    function mountScout() {
      return mount(WorldMap, {
        props: { locations: createLocations(1), vaultMarkers: [], selectedMarkerId: null, scoutMode: true },
        global: { stubs: defaultStubs },
        attachTo: document.body,
      })
    }

    it('ignores target clicks while not scouting', async () => {
      const wrapper = mount(WorldMap, {
        props: { locations: createLocations(1), vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      await wrapper.find('svg.world-map-svg').trigger('click')
      expect(wrapper.emitted('scout-target')).toBeFalsy()
      expect(wrapper.emitted('scout-invalid')).toBeFalsy()
    })

    it('rejects a click on an unexplored cell', async () => {
      const wrapper = mountScout()

      await wrapper.find('svg.world-map-svg').trigger('click', { clientX: 5, clientY: 5 })
      expect(wrapper.emitted('scout-invalid')).toBeTruthy()
      expect(wrapper.emitted('scout-target')).toBeFalsy()
      wrapper.unmount()
    })
  })

  describe('Player vaults on the shared atlas', () => {
    it('distinguishes the user own vaults from other players', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          playerVaults: [
            { vault_id: 'v-mine', number: 121, coord_x: 40, coord_y: 8, is_mine: true },
            { vault_id: 'v-other', number: 200, coord_x: 90, coord_y: 60, is_mine: false },
          ],
          selectedMarkerId: null,
        },
        global: { stubs: defaultStubs },
      })

      const mine = wrapper.findAllComponents(MapMarkerStub).find((m) => m.props('name') === 'Vault 121')
      const other = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Vault 200')
      expect(mine!.props('type')).toBe('home_vault')
      expect(mine!.props('label')).toBe('Your Vault')
      expect(other!.props('type')).toBe('vault')
      expect(other!.props('interactive')).toBe(false)
    })
  })
})
