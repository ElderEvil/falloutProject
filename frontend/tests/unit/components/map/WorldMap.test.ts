import { describe, it, expect, beforeEach, vi } from 'vitest'
import { nextTick } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorldMap from '@/modules/map/components/WorldMap.vue'
import { MAX_ZOOM } from '@/modules/map/composables/useMapZoomPan'
import { markerTypeMeta } from '@/modules/map/models/markerTypeMeta'
import { bearingDegrees } from '@/modules/map/utils/bearing'
import { isExploredTile } from '@/modules/map/utils/fog'
import { ATLAS_TILES, registryToTile } from '@/modules/map/utils/atlasProjection'
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
    'artSrc',
    'label',
    'cleared',
    'exploring',
    'status',
    'interactive',
  ],
  template: '<g class="map-marker map-marker-stub" />',
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
const FogLayerStub = {
  name: 'FogLayer',
  props: ['explored'],
  template: '<g class="fog-layer-stub" />',
}

const defaultStubs = {
  MapMarker: MapMarkerStub,
  MarkerListPanel: MarkerListPanelStub,
  Button: ButtonStub,
  Icon: IconStub,
  AtlasTerrain: AtlasTerrainStub,
  FogLayer: FogLayerStub,
}

async function zoomPastDeclutterThreshold(wrapper: VueWrapper) {
  ;(wrapper.vm as unknown as { focusOnMarker: (x: number, y: number) => void }).focusOnMarker(
    80,
    80
  )
  await wrapper.vm.$nextTick()
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
    vi.restoreAllMocks()
  })

  describe('Marker rendering', () => {
    it('hides seeded vault signals until the area is explored', () => {
      const locations = createLocations(3)
      const vaultMarkers = createVaultMarkers(4)

      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const names = wrapper.findAllComponents(MapMarkerStub).map((m) => m.props('name'))
      expect(names).not.toContain('Vault 100')
    })

    it('drops fog and reveals fog-gated markers when fogDisabled', async () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: createVaultMarkers(1),
          selectedMarkerId: null,
          fogDisabled: true,
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findComponent({ name: 'FogLayer' }).exists()).toBe(false)

      await zoomPastDeclutterThreshold(wrapper)
      expect(
        wrapper.findAllComponents(MapMarkerStub).some((m) => m.props('name') === 'Unknown vault')
      ).toBe(true)
    })

    it('should render zero markers when both arrays are empty', () => {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(0)
    })

    it('should render only location markers when vaultMarkers is empty', async () => {
      const locations = createLocations(5)

      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

      const markers = wrapper.findAll('.map-marker-stub')
      expect(markers).toHaveLength(5)
    })

    it('renders the site-type archetype icon on a grouped location marker', async () => {
      const store = useMapStore()
      store.placeGroups = [
        { key: 'gas_station', label: 'Gas Station', icon: 'mdi:gas-station' },
      ] as (typeof store.placeGroups)[number][]
      const [location] = createLocations(1)
      const grouped = { ...location, type: 'visited' as const, group_key: 'gas_station' }

      const wrapper = mount(WorldMap, {
        props: { locations: [grouped], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('icon')).toBe('mdi:gas-station')
    })

    it('renders preserved prototype art for a mappable archetype', async () => {
      const store = useMapStore()
      store.placeGroups = [
        { key: 'gas_station', label: 'Gas Station', icon: 'mdi:gas-station' },
      ] as (typeof store.placeGroups)[number][]
      vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
        new Proxy({} as CanvasRenderingContext2D, { get: () => () => {}, set: () => true })
      )
      vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue(
        'data:image/png;base64,art'
      )
      const [location] = createLocations(1)
      const grouped = { ...location, type: 'visited' as const, group_key: 'gas_station' }

      const wrapper = mount(WorldMap, {
        props: { locations: [grouped], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('artSrc')).toBe(
        'data:image/png;base64,art'
      )
    })

    it('falls back to the generic type icon without an archetype', async () => {
      const store = useMapStore()
      store.placeGroups = []
      const [location] = createLocations(1)
      const plain = { ...location, type: 'visited' as const, group_key: null }

      const wrapper = mount(WorldMap, {
        props: { locations: [plain], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('icon')).toBe(markerTypeMeta('visited').icon)
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
              is_active: true,
              points: [
                {
                  location_id: 'loc-1',
                  coord_x: 20,
                  coord_y: 30,
                  timestamp: '2026-01-01T00:00:00Z',
                },
                {
                  location_id: 'loc-1',
                  coord_x: 20,
                  coord_y: 30,
                  timestamp: '2026-01-01T01:00:00Z',
                },
              ],
            },
          ],
        },
        global: { stubs: defaultStubs },
      })

      const d = wrapper.find('.discovery-route-line').attributes('d')!
      expect(d.startsWith('M 80 80')).toBe(true)
      expect(d).toContain('C ')
      expect(d.endsWith('20 30')).toBe(true)
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
              is_active: true,
              points: [
                {
                  location_id: 'loc-1',
                  coord_x: 20,
                  coord_y: 30,
                  timestamp: '2026-01-01T00:00:00Z',
                },
                {
                  location_id: 'loc-1',
                  coord_x: 20,
                  coord_y: 30,
                  timestamp: '2026-01-01T01:00:00Z',
                },
              ],
            },
          ],
        },
        global: { stubs: defaultStubs },
      })

      const d = wrapper.find('.discovery-route-line').attributes('d')!
      expect(d.startsWith('M 50 50')).toBe(true)
      expect(d.endsWith('20 30')).toBe(true)
    })

    it('renders a dark casing path directly beneath the accent line per route', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          discoveryRoutes: [
            {
              exploration_id: 'expl-1',
              is_active: true,
              points: [
                {
                  location_id: 'loc-1',
                  coord_x: 20,
                  coord_y: 30,
                  timestamp: '2026-01-01T00:00:00Z',
                },
              ],
            },
            {
              exploration_id: 'expl-2',
              is_active: true,
              points: [
                {
                  location_id: 'loc-2',
                  coord_x: 30,
                  coord_y: 40,
                  timestamp: '2026-01-01T00:00:00Z',
                },
              ],
            },
          ],
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAll('.discovery-route-casing')).toHaveLength(2)
      expect(wrapper.findAll('.discovery-route-line')).toHaveLength(2)

      const groups = wrapper.findAll('g.discovery-route')
      expect(groups).toHaveLength(2)
      for (const group of groups) {
        const children = Array.from(group.element.children)
        expect(children[0]!.getAttribute('class')).toContain('discovery-route-casing')
        expect(children[1]!.getAttribute('class')).toContain('discovery-route-line')
        expect(children[0]!.getAttribute('d')).toBe(children[1]!.getAttribute('d'))
        expect(children[0]!.getAttribute('d')).toContain('C ')
      }
    })

    it('draws only active routes while the fog still uses inactive ones', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          discoveryRoutes: [
            {
              exploration_id: 'active-1',
              is_active: true,
              points: [
                {
                  location_id: 'loc-1',
                  coord_x: 10,
                  coord_y: 10,
                  timestamp: '2026-01-01T00:00:00Z',
                },
              ],
            },
            {
              exploration_id: 'done-1',
              is_active: false,
              points: [
                {
                  location_id: 'loc-2',
                  coord_x: 70,
                  coord_y: 10,
                  timestamp: '2026-01-01T00:00:00Z',
                },
              ],
            },
          ],
        },
        global: { stubs: defaultStubs },
      })

      const drawn = wrapper.findAll('.discovery-route-line')
      expect(drawn).toHaveLength(1)
      expect(drawn[0]!.attributes('d')).toContain('10 10')
      expect(drawn.some((line) => line.attributes('d')!.includes('70 10'))).toBe(false)

      const explored = wrapper.findComponent({ name: 'FogLayer' }).props('explored') as Uint8Array
      expect(
        isExploredTile(
          explored,
          registryToTile(70, ATLAS_TILES),
          registryToTile(10, ATLAS_TILES),
          ATLAS_TILES
        )
      ).toBe(true)
    })
  })

  describe('Zoom declutter', () => {
    it('hides secondary location markers at overview zoom and reveals them when zoomed in', async () => {
      const locations = createLocations(2)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(0)

      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(2)
    })

    it('keeps primary markers at overview zoom', () => {
      const locations = createLocations(4)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const types = wrapper.findAllComponents(MapMarkerStub).map((m) => m.props('type'))
      expect(types).toEqual(['discovery', 'home_vault'])
    })

    it('keeps a selected secondary marker visible at overview zoom', () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: `loc-${locations[0].id}` },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers).toHaveLength(1)
      expect(markers[0].props('selected')).toBe(true)
    })

    it('keeps an in-progress secondary marker visible at overview zoom', () => {
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

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers).toHaveLength(1)
      expect(markers[0].props('exploring')).toBe(true)
    })

    it('hides anonymous vault hints at overview zoom and reveals them when zoomed in', async () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: createVaultMarkers(3),
          selectedMarkerId: null,
          fogDisabled: true,
        },
        global: { stubs: defaultStubs },
      })

      const hintCount = () => wrapper.findAllComponents(MapMarkerStub).length
      expect(hintCount()).toBe(0)

      await zoomPastDeclutterThreshold(wrapper)

      expect(hintCount()).toBe(3)
    })
  })

  describe('Discovery clustering', () => {
    function discoveryLocation(
      id: string,
      coord_x: number,
      coord_y: number,
      overrides: Partial<WastelandLocationWithDwellers> = {}
    ): WastelandLocationWithDwellers {
      return {
        id,
        name: `Discovery ${id}`,
        normalized_name: `discovery ${id}`,
        type: 'discovery',
        coord_x,
        coord_y,
        description: 'An uncharted signal',
        vault_id: 'vault-1',
        exploration_id: null,
        created_at: null,
        is_unlocked: true,
        dwellers: [],
        ...overrides,
      } as WastelandLocationWithDwellers
    }

    it('collapses nearby discoveries into a single ×N badge', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [discoveryLocation('d-1', 20, 24), discoveryLocation('d-2', 30, 24)],
          vaultMarkers: [],
          selectedMarkerId: null,
          fogDisabled: true,
        },
        global: { stubs: defaultStubs },
      })

      const badges = wrapper.findAll('.map-cluster')
      expect(badges).toHaveLength(1)
      expect(badges[0].text()).toContain('×2')
      expect(badges[0].attributes('role')).toBe('button')
      expect(badges[0].attributes('aria-label')).toContain('2')
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(0)
    })

    it('leaves discoveries in different cells as individual markers', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [discoveryLocation('d-1', 20, 24), discoveryLocation('d-2', 100, 100)],
          vaultMarkers: [],
          selectedMarkerId: null,
          fogDisabled: true,
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAll('.map-cluster')).toHaveLength(0)
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(2)
    })

    it('never clusters locked discoveries away from their lock pins', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [
            discoveryLocation('d-1', 20, 24, { is_unlocked: false }),
            discoveryLocation('d-2', 30, 24, { is_unlocked: false }),
          ],
          vaultMarkers: [],
          selectedMarkerId: null,
          fogDisabled: true,
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findAll('.map-cluster')).toHaveLength(0)
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(2)
    })

    it('keeps a selected discovery pinned outside the cluster', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [
            discoveryLocation('d-1', 20, 24),
            discoveryLocation('d-2', 30, 24),
            discoveryLocation('d-3', 40, 24),
          ],
          vaultMarkers: [],
          selectedMarkerId: 'loc-d-3',
          fogDisabled: true,
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.find('.map-cluster').text()).toContain('×2')

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers).toHaveLength(1)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[0].props('name')).toBe('Discovery d-3')
    })

    it('zooms in and splits the cluster when the badge is clicked', async () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [discoveryLocation('d-1', 20, 24), discoveryLocation('d-2', 30, 24)],
          vaultMarkers: [],
          selectedMarkerId: null,
          fogDisabled: true,
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.find('.zoom-level').exists()).toBe(false)

      await wrapper.find('.map-cluster').trigger('click')
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.zoom-level').text()).toContain('200%')
      expect(wrapper.findAll('.map-cluster')).toHaveLength(0)
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(2)
    })

    it('renders every discovery individually at max zoom instead of a badge', async () => {
      // Twelve coincident discoveries cannot all separate onto the max-zoom
      // grid (cell size 16/MAX_ZOOM = 4 map units) after the anti-overlap
      // spread, so a badge would persist with no further zoom left for
      // onClusterClick to split it. At max zoom clustering is disabled.
      const wrapper = mount(WorldMap, {
        props: {
          locations: Array.from({ length: 12 }, (_, i) => discoveryLocation(`d-${i}`, 8, 8)),
          vaultMarkers: [],
          selectedMarkerId: null,
          fogDisabled: true,
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.find('.map-cluster').exists()).toBe(true)

      const vm = wrapper.vm as unknown as {
        focusOnMarker: (x: number, y: number, minZoom?: number) => void
      }
      vm.focusOnMarker(80, 80, MAX_ZOOM)
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.zoom-level').text()).toContain(`${Math.round(MAX_ZOOM * 100)}%`)
      expect(wrapper.findAll('.map-cluster')).toHaveLength(0)
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(12)
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

    it('renders foreign vaults as non-interactive anonymous hints where explored', async () => {
      const [base] = createLocations(1)
      const home = { ...base, id: 'home', type: 'home_vault' as const, coord_x: 50, coord_y: 50 }
      const wrapper = mount(WorldMap, {
        props: {
          locations: [home],
          vaultMarkers: [],
          playerVaults: [
            { vault_id: 'v-other', number: 200, coord_x: 50, coord_y: 50, is_mine: false },
          ],
          selectedMarkerId: null,
        },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

      const hint = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Unknown vault')
      expect(hint).toBeTruthy()
      expect(hint!.props('interactive')).toBe(false)
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
    it('should pass selected=false to all markers by default', async () => {
      const locations = createLocations(3)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers).toHaveLength(3)
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
      await zoomPastDeclutterThreshold(wrapper)

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[1].props('selected')).toBe(false)
    })

    it('renders your own vault with identity regardless of fog', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          playerVaults: [
            { vault_id: 'v-mine', number: 121, coord_x: 40, coord_y: 8, is_mine: true },
          ],
          selectedMarkerId: null,
        },
        global: { stubs: defaultStubs },
      })

      const mine = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Vault 121')
      expect(mine).toBeTruthy()
      expect(mine!.props('label')).toBe('Your Vault')
    })

    it('does not render the current vault twice (home marker + owned vault)', () => {
      const home: WastelandLocationWithDwellers = {
        ...createLocations(1)[0],
        id: 'home-765',
        name: 'Vault 765',
        type: 'home_vault',
        vault_id: 'v-current',
      }
      const wrapper = mount(WorldMap, {
        props: {
          locations: [home],
          vaultMarkers: [],
          playerVaults: [
            {
              vault_id: 'v-current',
              number: 765,
              coord_x: home.coord_x,
              coord_y: home.coord_y,
              is_mine: true,
            },
            { vault_id: 'v-other', number: 777, coord_x: 90, coord_y: 60, is_mine: true },
          ],
          selectedMarkerId: null,
        },
        global: { stubs: defaultStubs },
      })

      const markers = wrapper.findAllComponents(MapMarkerStub)
      const vault765 = markers.filter((m) => m.props('name') === 'Vault 765')
      expect(vault765).toHaveLength(1)
      expect(vault765[0].props('label')).not.toBe('Your Vault')

      expect(markers.some((m) => m.props('name') === 'Vault 777')).toBe(true)
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
      const revealed = {
        ...discoveryLocation('loc-2'),
        coord_x: locked.coord_x,
        coord_y: locked.coord_y,
      }
      const wrapper = mount(WorldMap, {
        props: { locations: [locked, revealed], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const hint = wrapper
        .findAllComponents(MapMarkerStub)
        .find((marker) => marker.props('is_unlocked') === false)
      expect(hint).toBeTruthy()
      expect(hint!.props('unseen')).toBe(false)
    })

    it('should pass unseen=false to non-discovery locations', async () => {
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
      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('unseen')).toBe(false)
    })
  })

  describe('Marker list panel integration', () => {
    it('should render the MarkerListPanel component', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: createLocations(2),
          vaultMarkers: createVaultMarkers(1),
          selectedMarkerId: null,
        },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.findComponent(MarkerListPanelStub).exists()).toBe(true)
    })

    it('passes locations to the panel and no unrelated vault signals', () => {
      const locations = createLocations(2)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: createVaultMarkers(1), selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const panel = wrapper.findComponent(MarkerListPanelStub)
      expect(panel.props('locations')).toEqual(locations)
      expect(panel.props('vaultMarkers')).toEqual([])
    })

    it('should dock the location index beside the map', () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: createLocations(2),
          vaultMarkers: createVaultMarkers(1),
          selectedMarkerId: null,
        },
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

    it('renders a locked place as a dimmed hint pin while keeping the index known-only', async () => {
      const { singleVisited, multiVisited, origin, unknown } = fixture()

      const wrapper = mount(WorldMap, {
        props: {
          locations: [singleVisited, multiVisited, origin, unknown],
          vaultMarkers: [],
          selectedMarkerId: null,
        },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

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
      expect(siteMarkers[0].props('artSrc')).toBeNull()
    })

    it('renders prototype art for a site whose id maps to an archetype', () => {
      vi.spyOn(HTMLCanvasElement.prototype, 'getContext').mockReturnValue(
        new Proxy({} as CanvasRenderingContext2D, { get: () => () => {}, set: () => true })
      )
      vi.spyOn(HTMLCanvasElement.prototype, 'toDataURL').mockReturnValue(
        'data:image/png;base64,art'
      )

      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          selectedMarkerId: null,
          expeditionSites: [createSite({ id: 'red_rocket' })],
        },
        global: { stubs: defaultStubs },
      })

      const site = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'expedition_site')
      expect(site!.props('artSrc')).toBe('data:image/png;base64,art')
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

    it('passes the dweller thumbnail as artSrc on a free-roam explorer marker', () => {
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-2',
          dwellerName: 'Bob',
          targetLocationId: null,
          lastKnown: { coord_x: 42, coord_y: 43 },
          dwellerThumbnailUrl: 'https://cdn.example/bob.png',
        },
      ]
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], explorerTracks: tracks, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const explorer = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')
      expect(explorer!.props('artSrc')).toBe('https://cdn.example/bob.png')
    })

    it('forwards backend-static thumbnails as artSrc for the portrait to normalize', () => {
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-2',
          dwellerName: 'Bob',
          targetLocationId: null,
          lastKnown: { coord_x: 42, coord_y: 43 },
          dwellerThumbnailUrl: '/static/portraits/bob.png',
        },
      ]
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], explorerTracks: tracks, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const explorer = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')
      expect(explorer!.props('artSrc')).toBe('/static/portraits/bob.png')
    })

    it('falls back to the walk icon when a free-roam explorer has no thumbnail', () => {
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-2',
          dwellerName: 'Bob',
          targetLocationId: null,
          lastKnown: { coord_x: 42, coord_y: 43 },
          dwellerThumbnailUrl: null,
        },
      ]
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], explorerTracks: tracks, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      const explorer = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')
      expect(explorer!.props('artSrc')).toBeNull()
      expect(explorer!.props('icon')).toBe('mdi:walk')
    })

    it('rotates the heading chevron along the free-roam trail', () => {
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-2',
          dwellerName: 'Bob',
          targetLocationId: null,
          lastKnown: { coord_x: 42, coord_y: 43 },
        },
      ]
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          explorerTracks: tracks,
          selectedMarkerId: null,
          discoveryRoutes: [
            {
              exploration_id: 'expl-2',
              is_active: true,
              points: [
                { coord_x: 0, coord_y: 10, timestamp: '2026-01-01T00:00:00Z' },
                { coord_x: 10, coord_y: 10, timestamp: '2026-01-01T01:00:00Z' },
              ],
            },
          ],
        },
        global: { stubs: defaultStubs },
      })

      const chevron = wrapper.find('.explorer-heading')
      expect(chevron.exists()).toBe(true)
      // Due east along the trail.
      expect(chevron.attributes('transform')).toContain('rotate(90)')
    })

    it('points the heading chevron home for a returning run without a usable trail', () => {
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-2',
          dwellerName: 'Bob',
          targetLocationId: null,
          lastKnown: { coord_x: 10, coord_y: 0 },
        },
      ]
      const home = { id: 'home', type: 'home_vault', coord_x: 0, coord_y: 0 }
      const expected = bearingDegrees({ x: 10, y: 0 }, { x: 0, y: 0 })
      const wrapper = mount(WorldMap, {
        props: {
          locations: [home as WastelandLocationWithDwellers],
          vaultMarkers: [],
          explorerTracks: tracks,
          selectedMarkerId: null,
        },
        global: { stubs: defaultStubs },
      })

      const chevron = wrapper.find('.explorer-heading')
      expect(chevron.exists()).toBe(true)
      expect(chevron.attributes('transform')).toContain(`rotate(${expected})`)
    })

    it('renders no heading chevron when a heading cannot be derived', () => {
      const tracks: ExplorerTrack[] = [
        {
          explorationId: 'expl-2',
          dwellerName: 'Bob',
          targetLocationId: null,
          lastKnown: null,
        },
        {
          explorationId: 'expl-3',
          dwellerName: 'Ann',
          targetLocationId: 'loc-1',
          lastKnown: null,
        },
      ]
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], explorerTracks: tracks, selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })

      expect(wrapper.find('.explorer-heading').exists()).toBe(false)
    })

    it('does not mark locations when no explorer tracks exist', async () => {
      const locations = createLocations(1)
      const wrapper = mount(WorldMap, {
        props: { locations, vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('exploring')).toBe(false)
      expect(marker.props('status')).toBeUndefined()
    })
  })

  describe('Cleared location markers', () => {
    it('passes cleared=true to a location whose clear_state is cleared', async () => {
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
      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('cleared')).toBe(true)
    })

    it('passes cleared=false when clear_state is absent', async () => {
      const wrapper = mount(WorldMap, {
        props: { locations: createLocations(1), vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
      })
      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('cleared')).toBe(false)
    })
  })

  describe('Player vaults on the shared atlas', () => {
    it('shows the user own vaults but not other players identities', () => {
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

      const markers = wrapper.findAllComponents(MapMarkerStub)
      const mine = markers.find((m) => m.props('name') === 'Vault 121')
      expect(mine!.props('type')).toBe('home_vault')
      expect(mine!.props('label')).toBe('Your Vault')
      expect(markers.some((m) => m.props('name') === 'Vault 200')).toBe(false)
    })

    it('emits vault-info with the vault id when an own-vault marker is clicked', async () => {
      const wrapper = mount(WorldMap, {
        props: {
          locations: [],
          vaultMarkers: [],
          playerVaults: [
            { vault_id: 'v-mine', number: 121, coord_x: 40, coord_y: 8, is_mine: true },
          ],
          selectedMarkerId: null,
        },
        global: { stubs: defaultStubs },
      })

      const mine = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Vault 121')
      await mine!.trigger('click')

      expect(wrapper.emitted('vault-info')).toEqual([['v-mine']])
      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })
  })
})
