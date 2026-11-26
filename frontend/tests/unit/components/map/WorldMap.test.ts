import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { nextTick } from 'vue'
import { mount, type VueWrapper } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import WorldMap from '@/modules/map/components/WorldMap.vue'
import { MAX_ZOOM } from '@/modules/map/composables/useMapZoomPan'
import { PLACE_MARKER_BODY_SCALE, PLACE_MARKER_GLYPH_SCALE } from '@/modules/map/models/markerTypeMeta'
import { bearingDegrees } from '@/modules/map/utils/bearing'
import { isExploredTile } from '@/modules/map/utils/fog'
import { ATLAS_TILES, registryToTile } from '@/modules/map/utils/atlasProjection'
import { useMapStore, VIEWED_LOCATIONS_STORAGE_KEY } from '@/modules/map/stores/map'
import { createSite } from '../../helpers/mapFixtures'
import type {
  ExpeditionSiteMarkerRead,
  ExplorerTrack,
  WastelandLocationWithDwellers,
  VaultMarkerRead,
  WorldSnapshotRead,
} from '@/modules/map/models/map'

// Stub child components that need complex DOM (Iconify, UTooltip)
const MapMarkerStub = {
  name: 'MapMarker',
  props: {
    x: null,
    scale: null,
    y: null,
    name: null,
    type: null,
    selected: null,
    unseen: null,
    is_unlocked: null,
    icon: null,
    artSrc: { default: null },
    label: null,
    cleared: null,
    exploring: null,
    status: null,
    interactive: null,
    risk: null,
    baseDifficulty: null,
    iconScale: null,
    bodyScale: null,
  },
  template: '<g class="map-marker map-marker-stub" />',
}

const MarkerListPanelStub = {
  name: 'MarkerListPanel',
  props: [
    'locations',
    'vaultMarkers',
    'expeditionSites',
    'siteTypeFilter',
    'selectedMarkerId',
    'docked',
  ],
  emits: ['marker-select'],
  template:
    '<div class="marker-list-panel-stub"><slot name="filters" /><slot name="legend" /></div>',
}

const ButtonStub = {
  name: 'Button',
  props: ['variant', 'size', 'disabled', 'ariaLabel'],
  template: '<button class="ubutton-stub" :aria-label="ariaLabel"><slot /></button>',
}

const IconStub = { name: 'Icon', props: ['icon'], template: '<span class="icon-stub" />' }
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

function mountMap(
  props: Record<string, unknown> = {},
  options: { slots?: Record<string, string> } = {}
) {
  return mount(WorldMap, {
    props: { locations: [], vaultMarkers: [], selectedMarkerId: null, ...props },
    global: { stubs: defaultStubs },
    ...(options.slots ? { slots: options.slots } : {}),
  })
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

function makeExplorerTrack(overrides: Partial<ExplorerTrack> = {}): ExplorerTrack {
  return {
    explorationId: 'expl-1',
    dwellerId: 'dweller-1',
    dwellerName: '',
    partyNames: [],
    status: 'active',
    health: null,
    radiation: null,
    maxHealth: null,
    targetLocationId: null,
    lastKnown: null,
    ...overrides,
  }
}

/** A discovery route fixture whose points are `[x, y]` pairs. */
function makeRoute(
  id: string,
  points: [number, number][],
  is_active = true,
  freeRoam = false
) {
  return {
    exploration_id: id,
    is_active,
    points: points.map(([coord_x, coord_y], index) => ({
      // Free-roam trails carry no location ids and are drawn as movement lines.
      location_id: freeRoam ? null : `loc-${index + 1}`,
      coord_x,
      coord_y,
      timestamp: `2026-01-01T0${index}:00:00Z`,
    })),
  }
}

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

const home: WastelandLocationWithDwellers = {
  ...createLocations(1)[0],
  id: 'home',
  type: 'home_vault',
  coord_x: 112,
  coord_y: 48,
}

describe('WorldMap', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    localStorage.removeItem(VIEWED_LOCATIONS_STORAGE_KEY)
    vi.restoreAllMocks()
  })

  describe('Marker rendering', () => {
    it('hides seeded vault signals until the area is explored', () => {
      const names = mountMap({
        locations: createLocations(3),
        vaultMarkers: createVaultMarkers(4),
      })
        .findAllComponents(MapMarkerStub)
        .map((m) => m.props('name'))
      expect(names).not.toContain('Vault 100')
    })

    it('drops fog and reveals fog-gated markers when fogDisabled', async () => {
      const wrapper = mountMap({ vaultMarkers: createVaultMarkers(1), fogDisabled: true })
      expect(wrapper.findComponent({ name: 'FogLayer' }).exists()).toBe(false)

      await zoomPastDeclutterThreshold(wrapper)
      expect(
        wrapper.findAllComponents(MapMarkerStub).some((m) => m.props('name') === 'Unknown vault')
      ).toBe(true)
    })

    it('should render only location markers when vaultMarkers is empty', async () => {
      const wrapper = mountMap({ locations: createLocations(5) })
      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAll('.map-marker-stub')).toHaveLength(5)
    })

    it('renders place markers at the smaller place glyph and body scale only', async () => {
      const [location] = createLocations(1)
      const place = { ...location, type: 'visited' as const }
      // The home vault rides the same locations list, but it is the player's own
      // marker: it keeps its full body and only follows the place glyph scale.
      const homeMarkerLocation = {
        ...location,
        id: 'loc-home',
        name: 'Home Vault',
        type: 'home_vault' as const,
      }

      const wrapper = mountMap({
        locations: [place, homeMarkerLocation],
        vaultMarkers: createVaultMarkers(1),
        fogDisabled: true,
      })
      await zoomPastDeclutterThreshold(wrapper)

      const markers = wrapper.findAllComponents(MapMarkerStub)
      const placeMarker = markers.find((m) => m.props('name') === place.name)!
      const homeMarker = markers.find((m) => m.props('name') === homeMarkerLocation.name)!
      const vaultMarker = markers.find((m) => m.props('name') === 'Unknown vault')!

      expect(placeMarker.props('iconScale')).toBe(PLACE_MARKER_GLYPH_SCALE)
      expect(placeMarker.props('bodyScale')).toBe(PLACE_MARKER_BODY_SCALE)
      expect(homeMarker.props('bodyScale')).toBe(1)
      expect(vaultMarker.props('iconScale')).toBeUndefined()
      expect(vaultMarker.props('bodyScale')).toBe(PLACE_MARKER_BODY_SCALE)
    })

    it('renders a grouped location marker with its archetype icon and no canvas art', async () => {
      const store = useMapStore()
      store.placeGroups = [
        { key: 'gas_station', label: 'Gas Station', icon: 'mdi:gas-station' },
      ] as (typeof store.placeGroups)[number][]
      const [location] = createLocations(1)
      const grouped = { ...location, type: 'visited' as const, group_key: 'gas_station' }

      const wrapper = mountMap({ locations: [grouped] })
      await zoomPastDeclutterThreshold(wrapper)

      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('icon')).toBe('mdi:gas-station')
      expect(marker.props('artSrc')).toBeNull()
    })

    it('falls back to the neutral place glyph without an archetype', async () => {
      const store = useMapStore()
      store.placeGroups = []
      const [location] = createLocations(1)
      const plain = { ...location, type: 'visited' as const, group_key: null }

      const wrapper = mountMap({ locations: [plain] })
      await zoomPastDeclutterThreshold(wrapper)

      // Discovery state is not identity: an archetype-less place gets a pin,
      // not the "eye" glyph that used to stand in for "visited".
      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('icon')).toBe(
        'mdi:map-marker-outline'
      )
    })

    it('forwards the place-group risk and difficulty to its location marker', async () => {
      const store = useMapStore()
      store.placeGroups = [
        {
          key: 'raider_camp',
          label: 'Raider Camp',
          icon: 'mdi:skull',
          risk: 'high',
          description: 'A fortified camp.',
          base_difficulty: 4,
        },
      ] as (typeof store.placeGroups)[number][]
      const [location] = createLocations(1)
      const grouped = { ...location, type: 'visited' as const, group_key: 'raider_camp' }

      const wrapper = mountMap({ locations: [grouped], fogDisabled: true })
      await zoomPastDeclutterThreshold(wrapper)
      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('risk')).toBe('high')
      expect(marker.props('baseDifficulty')).toBe(4)
    })
  })

  describe('Grid lines', () => {
    it('should not render grid lines (quiet player preview)', () => {
      expect(mountMap().findAll('line.grid-line')).toHaveLength(0)
    })
  })

  describe('Discovery routes', () => {
    it('renders API-projected event routes, including repeated location visits', () => {
      const wrapper = mountMap({
        discoveryRoutes: [makeRoute('expl-1', [[20, 30], [20, 30]])],
      })

      const d = wrapper.find('.discovery-route-line').attributes('d')!
      expect(d.startsWith('M 80 80')).toBe(true)
      expect(d).toContain('C ')
      expect(d.endsWith('20 30')).toBe(true)
    })

    it('anchors trails at the home vault coordinates', () => {
      const wrapper = mountMap({
        locations: [{ id: 'home-1', type: 'home_vault', coord_x: 50, coord_y: 50 } as never],
        discoveryRoutes: [makeRoute('expl-1', [[20, 30], [20, 30]])],
      })

      const d = wrapper.find('.discovery-route-line').attributes('d')!
      expect(d.startsWith('M 50 50')).toBe(true)
      expect(d.endsWith('20 30')).toBe(true)
    })

    it('renders a dark casing path directly beneath the accent line per route', () => {
      const wrapper = mountMap({
        discoveryRoutes: [makeRoute('expl-1', [[20, 30]]), makeRoute('expl-2', [[30, 40]])],
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
      const wrapper = mountMap({
        discoveryRoutes: [makeRoute('active-1', [[10, 10]]), makeRoute('done-1', [[70, 10]], false)],
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
      const wrapper = mountMap({ locations: createLocations(2) })
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(0)

      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(2)
    })

    it('keeps primary markers at overview zoom', () => {
      const types = mountMap({ locations: createLocations(4) })
        .findAllComponents(MapMarkerStub)
        .map((m) => m.props('type'))
      expect(types).toEqual(['discovery', 'home_vault'])
    })

    it('keeps selected and in-progress secondary markers visible at overview zoom', () => {
      const [selected, target] = createLocations(2)
      const markers = mountMap({
        locations: [selected, target],
        selectedMarkerId: `loc-${selected.id}`,
        explorerTracks: [makeExplorerTrack({ dwellerName: 'Ada', targetLocationId: target.id })],
      }).findAllComponents(MapMarkerStub)

      expect(markers).toHaveLength(2)
      expect(markers.find((m) => m.props('name') === selected.name)!.props('selected')).toBe(true)
      expect(markers.find((m) => m.props('name') === target.name)!.props('exploring')).toBe(true)
    })

    it('hides anonymous vault hints at overview zoom and reveals them when zoomed in', async () => {
      const wrapper = mountMap({ vaultMarkers: createVaultMarkers(3), fogDisabled: true })

      const hintCount = () => wrapper.findAllComponents(MapMarkerStub).length
      expect(hintCount()).toBe(0)

      await zoomPastDeclutterThreshold(wrapper)

      expect(hintCount()).toBe(3)
    })
  })

  describe('Discovery clustering', () => {
    it('collapses nearby discoveries into a single ×N badge', () => {
      const badges = mountMap({
        locations: [discoveryLocation('d-1', 20, 24), discoveryLocation('d-2', 30, 24)],
        fogDisabled: true,
      }).findAll('.map-cluster')
      expect(badges).toHaveLength(1)
      expect(badges[0].text()).toContain('×2')
      expect(badges[0].attributes('role')).toBe('button')
      expect(badges[0].attributes('aria-label')).toContain('2')
    })

    it('leaves discoveries in different cells as individual markers', () => {
      const wrapper = mountMap({
        locations: [discoveryLocation('d-1', 20, 24), discoveryLocation('d-2', 100, 100)],
        fogDisabled: true,
      })
      expect(wrapper.findAll('.map-cluster')).toHaveLength(0)
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(2)
    })

    it('never clusters locked discoveries away from their lock pins', () => {
      const wrapper = mountMap({
        locations: [
          discoveryLocation('d-1', 20, 24, { is_unlocked: false }),
          discoveryLocation('d-2', 30, 24, { is_unlocked: false }),
        ],
        fogDisabled: true,
      })
      expect(wrapper.findAll('.map-cluster')).toHaveLength(0)
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(2)
    })

    it('keeps a selected discovery pinned outside the cluster', () => {
      const wrapper = mountMap({
        locations: [
          discoveryLocation('d-1', 20, 24),
          discoveryLocation('d-2', 30, 24),
          discoveryLocation('d-3', 40, 24),
        ],
        selectedMarkerId: 'loc-d-3',
        fogDisabled: true,
      })

      expect(wrapper.find('.map-cluster').text()).toContain('×2')

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers).toHaveLength(1)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[0].props('name')).toBe('Discovery d-3')
    })

    it('zooms in and splits the cluster when the badge is clicked', async () => {
      const wrapper = mountMap({
        locations: [discoveryLocation('d-1', 20, 24), discoveryLocation('d-2', 30, 24)],
        fogDisabled: true,
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
      // grid after the anti-overlap spread, so a badge would persist with no
      // further zoom left for onClusterClick to split it.
      const wrapper = mountMap({
        locations: Array.from({ length: 12 }, (_, i) => discoveryLocation(`d-${i}`, 8, 8)),
        fogDisabled: true,
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
    it('should have the SVG element with correct viewBox at default zoom', () => {
      expect(mountMap().find('svg').attributes('viewBox')).toBe('0 0 160 160')
    })

    it('should NOT have role="img" on the SVG (children must be accessible)', () => {
      const svg = mountMap().find('svg')
      expect(svg.attributes('role')).toBeUndefined()
      expect(svg.attributes('aria-label')).toBeUndefined()
    })
  })

  describe('Initial home-vault focus', () => {
    it('opens on the active vault without selecting it or opening a modal', async () => {
      const wrapper = mountMap({ locations: [home] })
      await nextTick()

      expect(wrapper.get('svg').attributes('viewBox')).toBe('72 8 80 80')
      expect(wrapper.emitted('marker-click')).toBeUndefined()
      expect(wrapper.emitted('vault-info')).toBeUndefined()
      expect(wrapper.emitted('update:selectedMarkerId')).toBeUndefined()
    })

    it('focuses when the home marker arrives after mounting', async () => {
      const wrapper = mountMap()
      await wrapper.setProps({ locations: [home] })

      expect(wrapper.get('svg').attributes('viewBox')).toBe('72 8 80 80')
    })

    it('preserves user navigation on refresh and focuses a newly opened vault', async () => {
      const wrapper = mountMap({ locations: [home] })
      await nextTick()
      await wrapper.get('button[aria-label="Reset zoom"]').trigger('click')
      const navigatedView = wrapper.get('svg').attributes('viewBox')
      await wrapper.setProps({ locations: [{ ...home, name: 'Refreshed vault' }] })
      expect(wrapper.get('svg').attributes('viewBox')).toBe(navigatedView)

      await wrapper.setProps({
        locations: [{ ...home, id: 'other-home', vault_id: 'vault-2', coord_x: 48, coord_y: 112 }],
      })
      expect(wrapper.get('svg').attributes('viewBox')).toBe('8 72 80 80')
    })

    it.each([
      { width: 1200, height: 600, viewBox: '0 -20 80 80' },
      { width: 400, height: 800, viewBox: '-20 0 80 80' },
    ])('keeps an edge vault visible in a $width × $height pane', async ({ width, height, viewBox }) => {
      vi.spyOn(SVGElement.prototype, 'getBoundingClientRect').mockReturnValue({
        width,
        height,
      } as DOMRect)
      const wrapper = mountMap({ locations: [{ ...home, coord_x: 16, coord_y: 16 }] })
      await nextTick()

      expect(wrapper.get('svg').attributes('viewBox')).toBe(viewBox)
    })
  })

  describe('Marker click emission', () => {
    it('should emit marker-click with kind=location when a location marker is clicked', async () => {
      const locations = createLocations(1)
      const wrapper = mountMap({ locations })

      ;(wrapper.vm as unknown as { onLocationClick: (l: unknown) => void }).onLocationClick(
        locations[0]
      )
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('marker-click')![0][0]).toEqual({
        kind: 'location',
        data: locations[0],
      })
    })

    it('renders foreign vaults as non-interactive anonymous hints where explored', async () => {
      const [base] = createLocations(1)
      const homeLocation = { ...base, id: 'home', type: 'home_vault' as const, coord_x: 50, coord_y: 50 }
      const wrapper = mountMap({
        locations: [homeLocation],
        playerVaults: [
          { vault_id: 'v-other', number: 200, coord_x: 50, coord_y: 50, is_mine: false },
        ],
      })
      await zoomPastDeclutterThreshold(wrapper)

      const hint = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Unknown vault')
      expect(hint!.props('interactive')).toBe(false)
    })
  })

  describe('Empty store (failure case)', () => {
    it('should render the SVG with zero markers and no exceptions', () => {
      const wrapper = mountMap()

      expect(wrapper.find('svg').exists()).toBe(true)
      expect(wrapper.findAll('.map-marker-stub')).toHaveLength(0)
      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })
  })

  describe('Zoom controls', () => {
    it('should render zoom in, zoom out, and reset buttons in a labelled group', () => {
      const wrapper = mountMap()
      expect(wrapper.find('.zoom-controls').findAllComponents(ButtonStub)).toHaveLength(3)
      expect(wrapper.find('[role="group"]').attributes('aria-label')).toBe('Map zoom controls')
    })

    it('should show zoom level percentage when zoomed', async () => {
      const wrapper = mountMap()
      expect(wrapper.find('.zoom-level').exists()).toBe(false)

      ;(wrapper.vm as unknown as { zoomIn: () => void }).zoomIn()
      await wrapper.vm.$nextTick()

      expect(wrapper.find('.zoom-level').exists()).toBe(true)
      expect(wrapper.find('.zoom-level').text()).toContain('%')
    })
  })

  describe('Selected marker wiring', () => {
    it('should pass selected=false to all markers by default', async () => {
      const wrapper = mountMap({ locations: createLocations(3) })
      await zoomPastDeclutterThreshold(wrapper)

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers).toHaveLength(3)
      for (const marker of markers) expect(marker.props('selected')).toBe(false)
    })

    it('should pass selected=true to a marker after it is clicked', async () => {
      const locations = createLocations(2)
      const wrapper = mountMap({ locations })

      ;(wrapper.vm as unknown as { onLocationClick: (l: unknown) => void }).onLocationClick(
        locations[0]
      )
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('update:selectedMarkerId')![0][0]).toBe(`loc-${locations[0].id}`)
      await wrapper.setProps({ selectedMarkerId: `loc-${locations[0].id}` })
      await zoomPastDeclutterThreshold(wrapper)

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[1].props('selected')).toBe(false)
    })

    it('does not render the current vault twice (home marker + owned vault)', async () => {
      const homeLocation: WastelandLocationWithDwellers = {
        ...createLocations(1)[0],
        id: 'home-765',
        name: 'Vault 765',
        type: 'home_vault',
        vault_id: 'v-current',
      }
      const wrapper = mountMap({
        locations: [homeLocation],
        playerVaults: [
          {
            vault_id: 'v-current',
            number: 765,
            coord_x: homeLocation.coord_x,
            coord_y: homeLocation.coord_y,
            is_mine: true,
          },
          { vault_id: 'v-other', number: 777, coord_x: 90, coord_y: 60, is_mine: true },
        ],
      })
      const markers = wrapper.findAllComponents(MapMarkerStub)

      const vault765 = markers.filter((m) => m.props('name') === 'Vault 765')
      expect(vault765).toHaveLength(1)
      expect(vault765[0].props('label')).not.toBe('Your Vault')
      expect(markers.some((m) => m.props('name') === 'Vault 777')).toBe(true)

      // The surviving marker is the home-vault location; clicking it must open
      // the summary panel for the current vault, not the generic details modal.
      await vault765[0].trigger('click')

      expect(wrapper.emitted('vault-info')).toEqual([['v-current']])
      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })

    it('suppresses every marker click when hasDragMoved is true', async () => {
      const homeLocation: WastelandLocationWithDwellers = {
        ...createLocations(1)[0],
        id: 'home-765',
        name: 'Vault 765',
        type: 'home_vault',
        vault_id: 'v-current',
      }
      const mine = { vault_id: 'v-mine', number: 121, coord_x: 40, coord_y: 8, is_mine: true }
      const locations = createLocations(1)
      const wrapper = mountMap({ locations: [homeLocation, ...locations], playerVaults: [mine] })

      const vm = wrapper.vm as unknown as Record<string, unknown> & { hasDragMoved: boolean }
      vm.hasDragMoved = true
      ;(vm.onLocationMarkerClick as (arg: unknown) => void)(homeLocation)
      ;(vm.onOwnVaultClick as (arg: unknown) => void)(mine)
      ;(vm.onLocationClick as (arg: unknown) => void)(locations[0])
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('vault-info')).toBeUndefined()
      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })
  })

  describe('Unseen discovery wiring', () => {
    it('passes unseen=true to an unlocked discovery the player has not viewed', () => {
      const markers = mountMap({ locations: [discoveryLocation('loc-1', 10, 20)] }).findAllComponents(
        MapMarkerStub
      )
      expect(markers).toHaveLength(1)
      expect(markers[0].props('unseen')).toBe(true)
    })

    it('should pass unseen=false once the discovery has been viewed', async () => {
      const wrapper = mountMap({ locations: [discoveryLocation('loc-1', 10, 20)] })
      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('unseen')).toBe(true)

      useMapStore().markLocationViewed('vault-1', 'loc-1')
      await wrapper.vm.$nextTick()

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('unseen')).toBe(false)
    })

    it('hides a locked discovery in the fog until its area is explored', () => {
      const wrapper = mountMap({
        locations: [discoveryLocation('loc-1', 10, 20, { is_unlocked: false })],
      })
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(0)
    })

    it('shows a locked discovery as a hint pin once its area is explored', () => {
      const locked = discoveryLocation('loc-1', 10, 20, { is_unlocked: false })
      const revealed = {
        ...discoveryLocation('loc-2', 10, 20),
        coord_x: locked.coord_x,
        coord_y: locked.coord_y,
      }
      const hint = mountMap({ locations: [locked, revealed] })
        .findAllComponents(MapMarkerStub)
        .find((marker) => marker.props('is_unlocked') === false)
      expect(hint!.props('unseen')).toBe(false)
    })

    it('should pass unseen=false to non-discovery locations', async () => {
      const locations = [
        discoveryLocation('loc-1', 10, 20, {
          type: 'visited' as const,
          dwellers: [
            { dweller_id: 'd-1', first_name: 'A', last_name: null, relation: 'visited' },
            { dweller_id: 'd-2', first_name: 'B', last_name: null, relation: 'visited' },
          ],
        }),
      ]
      const wrapper = mountMap({ locations })
      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('unseen')).toBe(false)
    })
  })

  describe('Marker list panel integration', () => {
    it('should render the MarkerListPanel component', () => {
      const wrapper = mountMap({
        locations: createLocations(2),
        vaultMarkers: createVaultMarkers(1),
      })
      expect(wrapper.findComponent(MarkerListPanelStub).exists()).toBe(true)
    })

    it('keeps filter controls above the map instead of inside the index', () => {
      const wrapper = mountMap(
        { locations: createLocations(2) },
        { slots: { filters: '<div class="filter-probe">Filters</div>' } }
      )
      expect(wrapper.find('.map-controls-row .filter-probe').exists()).toBe(true)
      expect(wrapper.findComponent(MarkerListPanelStub).find('.filter-probe').exists()).toBe(false)
    })

    it('offers to clear filters when they hide every non-home place', async () => {
      const base = createLocations(1)[0]
      const wrapper = mountMap({
        locations: [
          { ...base, id: 'home', type: 'home_vault' as const },
          { ...base, id: 'depot', type: 'discovery' as const, group_key: 'military' },
        ],
        siteTypeFilter: 'research',
      })

      const banner = wrapper.get('.map-filter-empty')
      expect(banner.text()).toContain('No other places match these filters.')
      await banner.get('button').trigger('click')
      expect(wrapper.emitted('clear-filters')).toHaveLength(1)
    })

    it('keeps the callout hidden while filters still leave another place', () => {
      const base = createLocations(1)[0]
      const wrapper = mountMap({
        locations: [
          { ...base, id: 'home', type: 'home_vault' as const },
          { ...base, id: 'depot', type: 'discovery' as const, group_key: 'military' },
        ],
        siteTypeFilter: 'military',
      })
      expect(wrapper.find('.map-filter-empty').exists()).toBe(false)
    })

    it('passes locations to the panel and no unrelated vault signals', () => {
      const locations = createLocations(2)
      const panel = mountMap({ locations, vaultMarkers: createVaultMarkers(1) }).findComponent(
        MarkerListPanelStub
      )
      expect(panel.props('locations')).toEqual(locations)
      expect(panel.props('vaultMarkers')).toEqual([])
    })

    it('filters ready locations in the map and index without hiding the home vault', async () => {
      const locations = [
        { ...createLocations(1)[0], id: 'home', type: 'home_vault' as const },
        { ...createLocations(1)[0], id: 'ready', type: 'visited' as const, dwellers: [] },
        { ...createLocations(1)[0], id: 'other', type: 'visited' as const },
        { ...createLocations(1)[0], id: 'locked', is_unlocked: false },
      ]
      const wrapper = mountMap({ locations, readyLocationIds: ['ready', 'locked'] })
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(2)
      expect(
        wrapper
          .findComponent(MarkerListPanelStub)
          .props('locations')
          .map((loc: WastelandLocationWithDwellers) => loc.id)
      ).toEqual(['home', 'ready'])
      await wrapper.setProps({ readyLocationIds: [] })
      expect(wrapper.findAllComponents(MapMarkerStub)).toHaveLength(1)
    })

    it('keeps the location index outside the canvas so it cannot cover markers', () => {
      const wrapper = mountMap({
        locations: createLocations(2),
        vaultMarkers: createVaultMarkers(1),
      })
      expect(wrapper.findComponent(MarkerListPanelStub).props('docked')).toBeFalsy()
      expect(
        wrapper.find('.world-map-container').findComponent(MarkerListPanelStub).exists()
      ).toBe(false)
    })

    it('emits marker-click and selects when the panel emits marker-select', async () => {
      const locations = createLocations(2)
      const wrapper = mountMap({ locations })

      await wrapper
        .findComponent(MarkerListPanelStub)
        .vm.$emit('marker-select', { kind: 'location', data: locations[0] })
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('marker-click')![0][0]).toEqual({
        kind: 'location',
        data: locations[0],
      })
      expect(wrapper.emitted('update:selectedMarkerId')).toBeTruthy()
      await wrapper.setProps({ selectedMarkerId: `loc-${locations[0].id}` })

      const markers = wrapper.findAllComponents(MapMarkerStub)
      expect(markers[0].props('selected')).toBe(true)
      expect(markers[1].props('selected')).toBe(false)
    })
  })

  describe('Touch interaction', () => {
    async function mountZoomed() {
      const wrapper = mount(WorldMap, {
        props: { locations: [], vaultMarkers: [], selectedMarkerId: null },
        global: { stubs: defaultStubs },
        attachTo: document.body,
      })
      ;(wrapper.vm as unknown as { focusOnMarker: (x: number, y: number) => void }).focusOnMarker(
        80,
        80
      )
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
      expect(mountMap().find('.world-map-container').classes()).toContain('touch-none')
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

      const wrapper = mountMap({ locations: [singleVisited, multiVisited, origin, unknown] })
      await zoomPastDeclutterThreshold(wrapper)

      // The locked discovery still renders as a hint; the single visited
      // marker is decluttered.
      expect(wrapper.findAll('.map-marker-stub')).toHaveLength(3)

      const hint = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Unidentified Signal')
      expect(hint!.props('is_unlocked')).toBe(false)

      // The index only receives locations whose names are known to the vault.
      const panel = wrapper.findComponent(MarkerListPanelStub)
      expect(panel.props('locations')).toHaveLength(3)
      expect(panel.props('locations')).not.toContain(unknown)
    })

    it('always renders the home vault even when it is not unlocked', () => {
      const { unknown } = fixture()
      const homeLocation: WastelandLocationWithDwellers = {
        ...unknown,
        id: 'home-1',
        name: 'Vault 121',
        type: 'home_vault',
        is_unlocked: false,
        coord_x: 80,
        coord_y: 80,
      }

      const homeMarker = mountMap({ locations: [homeLocation, unknown] })
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'home_vault')
      expect(homeMarker!.props('name')).toBe('Vault 121')
    })
  })

  describe('Site-type filter', () => {
    function siteLocation(
      id: string,
      name: string,
      group_key: string | null,
      overrides: Partial<WastelandLocationWithDwellers> = {}
    ): WastelandLocationWithDwellers {
      return {
        ...createLocations(1)[0],
        id,
        name,
        type: 'discovery',
        coord_x: 20,
        coord_y: 20,
        is_unlocked: true,
        group_key,
        dwellers: [],
        ...overrides,
      } as WastelandLocationWithDwellers
    }

    const markerNames = (wrapper: VueWrapper) =>
      wrapper.findAllComponents(MapMarkerStub).map((m) => m.props('name'))

    it('renders only locations whose group matches the filter', () => {
      const names = markerNames(
        mountMap({
          locations: [
            siteLocation('g1', 'Gas Stop', 'gas_station'),
            siteLocation('m1', 'Army Base', 'military', { coord_x: 60, coord_y: 60 }),
            siteLocation('g2', 'Second Gas Stop', 'gas_station', { coord_x: 100, coord_y: 100 }),
          ],
          fogDisabled: true,
          siteTypeFilter: 'gas_station',
        })
      )
      expect(names).toContain('Gas Stop')
      expect(names).toContain('Second Gas Stop')
      expect(names).not.toContain('Army Base')
    })

    it('shows every location when the filter is null', () => {
      const names = markerNames(
        mountMap({
          locations: [
            siteLocation('g1', 'Gas Stop', 'gas_station'),
            siteLocation('m1', 'Army Base', 'military', { coord_x: 60, coord_y: 60 }),
          ],
          fogDisabled: true,
          siteTypeFilter: null,
        })
      )
      expect(names).toContain('Gas Stop')
      expect(names).toContain('Army Base')
    })

    it('keeps the home vault and non-place marker families unfiltered', () => {
      const homeLocation = siteLocation('h1', 'Vault 121', null, {
        type: 'home_vault',
        coord_x: 80,
        coord_y: 80,
      })
      const track = makeExplorerTrack({
        explorationId: 'expl-1',
        dwellerName: 'Bob',
        lastKnown: { coord_x: 42, coord_y: 43 },
      })
      const wrapper = mountMap({
        locations: [
          homeLocation,
          siteLocation('g1', 'Gas Stop', 'gas_station'),
          siteLocation('m1', 'Army Base', 'military'),
        ],
        fogDisabled: true,
        siteTypeFilter: 'gas_station',
        expeditionSites: [createSite()],
        explorerTracks: [track],
      })

      const types = wrapper.findAllComponents(MapMarkerStub).map((m) => m.props('type'))
      expect(types).toContain('home_vault')
      expect(types).toContain('expedition_site')
      expect(types).toContain('explorer')
      expect(markerNames(wrapper)).toContain('Gas Stop')
      expect(markerNames(wrapper)).not.toContain('Army Base')
    })

    it('forwards the filter to the index without coupling the state key', () => {
      const wrapper = mountMap({
        locations: [siteLocation('g1', 'Gas Stop', 'gas_station')],
        fogDisabled: true,
        siteTypeFilter: 'gas_station',
      })
      expect(wrapper.findComponent(MarkerListPanelStub).props('siteTypeFilter')).toBe('gas_station')
      expect(wrapper.findComponent({ name: 'MapLegend' }).props('siteTypeFilter')).toBeUndefined()
    })
  })

  describe('Expedition site markers', () => {
    it('renders a site marker per expedition site', () => {
      const siteMarkers = mountMap({
        expeditionSites: [createSite(), createSite({ id: 'site-2', name: 'Crater Store' })],
      })
        .findAllComponents(MapMarkerStub)
        .filter((m) => m.props('type') === 'expedition_site')
      expect(siteMarkers).toHaveLength(2)
      expect(siteMarkers[0].props('name')).toBe('Red Rocket Gas Station')
      expect(siteMarkers[0].props('icon')).toBe('mdi:map-marker-star')
      expect(siteMarkers[0].props('artSrc')).toBeNull()
    })

    it.each([
      ['a ready site', {}, false, ['READY · LVL 5 · 3 ROOMS']],
      ['a cooling-down site', { cleared: true, block_reason: 'cooldown', cooldown_remaining_seconds: 3600 }, true, ['CLEARED', 'COOLDOWN 1h 0m remaining']],
      ['a cooldown-only site that was not cleared', { cleared: false, block_reason: 'cooldown', cooldown_remaining_seconds: 3600 }, false, ['READY · LVL 5 · 3 ROOMS']],
      ['a site with an open run', { block_reason: 'open' }, false, ['IN PROGRESS · LVL 5 · 3 ROOMS']],
    ])('passes cleared + status for %s', (_, overrides, cleared, statuses) => {
      const site = mountMap({
        expeditionSites: [createSite(overrides as Partial<ExpeditionSiteMarkerRead>)],
      }).findAllComponents(MapMarkerStub)[0]
      expect(site.props('cleared')).toBe(cleared)
      for (const status of statuses) expect(site.props('status')).toContain(status)
      if (!cleared) expect(site.props('status')).not.toContain('CLEARED')
    })

    it('emits marker-click with kind=site when a site marker is clicked', async () => {
      const site = createSite()
      const wrapper = mountMap({ expeditionSites: [site] })

      ;(wrapper.vm as unknown as { onSiteClick: (s: unknown) => void }).onSiteClick(site)
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('marker-click')![0][0]).toEqual({ kind: 'site', data: site })
    })

    it('passes expedition sites to the marker list panel', () => {
      const sites = [createSite()]
      expect(
        mountMap({ expeditionSites: sites }).findComponent(MarkerListPanelStub).props('expeditionSites')
      ).toEqual(sites)
    })
  })

  describe('Explorer tracking', () => {
    it('groups overlapping departures and lets each explorer or party be selected', async () => {
      const tracks = [
        makeExplorerTrack({
          explorationId: 'a',
          dwellerName: 'Ada',
          lastKnown: { coord_x: 79, coord_y: 80 },
        }),
        makeExplorerTrack({
          explorationId: 'b',
          dwellerName: 'Bob',
          partyNames: ['Bob', 'Bea'],
          targetLocationId: 'site',
          lastKnown: { coord_x: 81, coord_y: 80 },
        }),
      ]
      const wrapper = mountMap({ explorerTracks: tracks })
      expect(
        wrapper.findAllComponents(MapMarkerStub).filter((m) => m.props('type') === 'explorer')
      ).toHaveLength(0)
      const group = wrapper.find('[aria-label="Choose from 2 nearby explorers or parties"]')
      await group.trigger('keydown', { key: 'Enter' })
      const roster = wrapper.find('[aria-label="Nearby explorers and parties"]')
      expect(roster.text()).toContain('Ada')
      expect(roster.text()).toContain('Bob, Bea')
      await roster
        .findAll('button')
        .find((b) => b.text().includes('Ada'))!
        .trigger('click')
      expect(wrapper.emitted('dweller-click')![0][0]).toMatchObject({ track: tracks[0] })
      await group.trigger('click')
      await wrapper
        .find('[aria-label="Nearby explorers and parties"]')
        .findAll('button')
        .find((b) => b.text().includes('Bob, Bea'))!
        .trigger('click')
      expect(wrapper.emitted('party-click')![0]).toEqual(['b'])
      await wrapper.setProps({ explorerTracks: [tracks[0]] })
      const marker = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')!
      expect(marker.props('x')).toBe(79)
      expect(marker.props('scale')).toBe(0.65)
    })

    it.each([
      ['the dweller name', { dwellerName: 'Ada', partyNames: ['Ada'] }, 'Exploring — Ada'],
      [
        'the whole dispatch party',
        {
          dwellerName: 'Stephanie Boyd',
          partyNames: ['Stephanie Boyd', 'Cooper Howard'],
        },
        'Exploring — Stephanie Boyd, Cooper Howard',
      ],
      ['a solo anchor', { dwellerName: 'Ada', partyNames: ['Ada'] }, 'Exploring — Ada'],
      ['a missing name', { dwellerName: '' }, 'Dispatching'],
    ])('marks the dispatched target as exploring with %s', (_, overrides, status) => {
      const locations = createLocations(1)
      const marker = mountMap({
        locations,
        explorerTracks: [makeExplorerTrack({ targetLocationId: locations[0].id, ...overrides })],
      }).findAllComponents(MapMarkerStub)[0]
      expect(marker.props('exploring')).toBe(true)
      expect(marker.props('status')).toBe(status)
    })

    it('leaves a free-roam explorer marker status on the anchor alone', () => {
      const explorer = mountMap({
        explorerTracks: [
          makeExplorerTrack({
            explorationId: 'expl-2',
            dwellerName: 'Bob',
            partyNames: ['Bob', 'Ann'],
            lastKnown: { coord_x: 42, coord_y: 43 },
          }),
        ],
      })
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')
      expect(explorer!.props('status')).toBe('Last known — Bob')
    })

    it.each(['active', 'returning'] as const)(
      'renders a moving dispatched party while %s',
      async (status) => {
        const track = makeExplorerTrack({
          status,
          targetLocationId: 'target',
          lastKnown: { coord_x: 42, coord_y: 43 },
          partyNames: ['Ada', 'Bob'],
        })
        const wrapper = mountMap({ explorerTracks: [track] })
        const party = wrapper
          .findAllComponents(MapMarkerStub)
          .find((m) => m.props('type') === 'explorer')!
        expect(party.props('x')).toBe(42)
        expect(party.props('y')).toBe(43)
        expect(party.props('icon')).toBe('mdi:account-group')
        expect(party.props('artSrc')).toBeNull()
        await party.trigger('click')
        expect(wrapper.emitted('party-click')![0]).toEqual([track.explorationId])
      }
    )

    it('renders an interactive last-known marker for a free-roam explorer', () => {
      const explorer = mountMap({
        explorerTracks: [
          makeExplorerTrack({
            explorationId: 'expl-2',
            dwellerName: 'Bob',
            lastKnown: { coord_x: 42, coord_y: 43 },
          }),
        ],
      })
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')
      expect(explorer!.props('x')).toBe(42)
      expect(explorer!.props('y')).toBe(43)
      expect(explorer!.props('interactive')).toBe(true)
      expect(explorer!.props('status')).toBe('Last known — Bob')
    })

    it('emits dweller-click with the screen anchor when a free-roam explorer is clicked', async () => {
      const track = makeExplorerTrack({
        explorationId: 'expl-2',
        dwellerName: 'Bob',
        lastKnown: { coord_x: 42, coord_y: 43 },
      })
      const wrapper = mountMap({ explorerTracks: [track] })
      const explorer = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')
      await explorer!.trigger('click', { clientX: 120, clientY: 80 })

      expect(wrapper.emitted('dweller-click')![0][0]).toEqual({ track, x: 120, y: 80 })
    })

    it('renders no explorer marker when a free-roam run has no trail yet', () => {
      const explorers = mountMap({
        explorerTracks: [makeExplorerTrack({ explorationId: 'expl-2', dwellerName: 'Bob' })],
      })
        .findAllComponents(MapMarkerStub)
        .filter((m) => m.props('type') === 'explorer')
      expect(explorers).toHaveLength(0)
    })

    it.each([
      ['an absolute thumbnail', 'https://cdn.example/bob.png', 'https://cdn.example/bob.png'],
      ['a backend-static thumbnail', '/static/portraits/bob.png', '/static/portraits/bob.png'],
      ['no thumbnail', null, null],
    ])('forwards %s as artSrc', (_, thumbnail, artSrc) => {
      const explorer = mountMap({
        explorerTracks: [
          makeExplorerTrack({
            explorationId: 'expl-2',
            dwellerName: 'Bob',
            lastKnown: { coord_x: 42, coord_y: 43 },
            dwellerThumbnailUrl: thumbnail,
          }),
        ],
      })
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('type') === 'explorer')
      expect(explorer!.props('artSrc')).toBe(artSrc)
      if (thumbnail === null) expect(explorer!.props('icon')).toBe('mdi:account')
    })

    it('rotates the heading chevron along the free-roam trail', () => {
      const chevron = mountMap({
        explorerTracks: [
          makeExplorerTrack({
            explorationId: 'expl-2',
            dwellerName: 'Bob',
            lastKnown: { coord_x: 42, coord_y: 43 },
          }),
        ],
        discoveryRoutes: [makeRoute('expl-2', [[0, 10], [10, 10]], true, true)],
      }).find('.explorer-heading')
      expect(chevron.exists()).toBe(true)
      // Due east along the trail.
      expect(chevron.attributes('transform')).toContain('rotate(90)')
    })

    it('points the heading chevron home for a returning run without a usable trail', () => {
      const expected = bearingDegrees({ x: 10, y: 0 }, { x: 0, y: 0 })
      const chevron = mountMap({
        locations: [{ id: 'home', type: 'home_vault', coord_x: 0, coord_y: 0 } as never],
        explorerTracks: [
          makeExplorerTrack({
            explorationId: 'expl-2',
            dwellerName: 'Bob',
            status: 'returning',
            lastKnown: { coord_x: 10, coord_y: 0 },
          }),
        ],
      }).find('.explorer-heading')
      expect(chevron.exists()).toBe(true)
      expect(chevron.attributes('transform')).toContain(`rotate(${expected})`)
    })

    it('renders no heading chevron when a heading cannot be derived', () => {
      const wrapper = mountMap({
        explorerTracks: [
          makeExplorerTrack({ explorationId: 'expl-2', dwellerName: 'Bob' }),
          makeExplorerTrack({
            explorationId: 'expl-3',
            dwellerName: 'Ann',
            targetLocationId: 'loc-1',
          }),
        ],
      })
      expect(wrapper.find('.explorer-heading').exists()).toBe(false)
    })

    it('does not mark locations when no explorer tracks exist', async () => {
      const wrapper = mountMap({ locations: createLocations(1) })
      await zoomPastDeclutterThreshold(wrapper)

      const marker = wrapper.findAllComponents(MapMarkerStub)[0]
      expect(marker.props('exploring')).toBe(false)
      expect(marker.props('status')).toBeUndefined()
    })
  })

  describe('Cleared location markers', () => {
    it.each([
      [
        true,
        { clearable: true, cleared: true, clear_count: 2, tier: 1, time_remaining_seconds: 0, loot_table: null },
      ],
      [false, undefined],
    ])('passes cleared=%s from clear_state', async (cleared, clearState) => {
      const locations = createLocations(1)
      locations[0].clear_state = clearState as never
      const wrapper = mountMap({ locations })
      await zoomPastDeclutterThreshold(wrapper)

      expect(wrapper.findAllComponents(MapMarkerStub)[0].props('cleared')).toBe(cleared)
    })
  })

  describe('Player vaults on the shared atlas', () => {
    it('shows the user own vaults but not other players identities', () => {
      const markers = mountMap({
        playerVaults: [
          { vault_id: 'v-mine', number: 121, coord_x: 40, coord_y: 8, is_mine: true },
          { vault_id: 'v-other', number: 200, coord_x: 90, coord_y: 60, is_mine: false },
        ],
      }).findAllComponents(MapMarkerStub)
      const mine = markers.find((m) => m.props('name') === 'Vault 121')
      expect(mine!.props('type')).toBe('home_vault')
      expect(mine!.props('label')).toBe('Your Vault')
      expect(markers.some((m) => m.props('name') === 'Vault 200')).toBe(false)
    })

    it('emits vault-info with the vault id when an own-vault marker is clicked', async () => {
      const wrapper = mountMap({
        playerVaults: [{ vault_id: 'v-mine', number: 121, coord_x: 40, coord_y: 8, is_mine: true }],
      })
      const mine = wrapper
        .findAllComponents(MapMarkerStub)
        .find((m) => m.props('name') === 'Vault 121')
      await mine!.trigger('click')

      expect(wrapper.emitted('vault-info')).toEqual([['v-mine']])
      expect(wrapper.emitted('marker-click')).toBeUndefined()
    })
  })

  describe('Atlas layer order', () => {
    it('draws roads above terrain and below fog and markers', async () => {
      useMapStore().worldSnapshot = {
        world_id: 'atlas',
        generator_version: 1,
        recipe_fingerprint: 'recipe',
        snapshot_checksum: 'base',
        width: 2,
        height: 2,
        terrain: ['wasteland', 'wasteland', 'wasteland', 'water'],
        slots: [],
        roads: {
          version: 4,
          base_checksum: 'base',
          checksum: 'roads',
          segments: [
            {
              id: 'h',
              kind: 'highway',
              points: [
                [10, 20],
                [70, 40],
              ],
            },
          ],
        },
      } satisfies WorldSnapshotRead

      const wrapper = mountMap({ locations: createLocations(5) })
      await zoomPastDeclutterThreshold(wrapper)

      const order = wrapper
        .findAll('.atlas-terrain-stub, .atlas-roads, .fog-layer-stub, .map-marker-stub')
        .map((el) => el.classes().find((name) => name === 'atlas-roads' || name.endsWith('-stub')))

      expect(order[0]).toBe('atlas-terrain-stub')
      expect(order[1]).toBe('atlas-roads')
      expect(order[2]).toBe('fog-layer-stub')
      expect(order.indexOf('map-marker-stub')).toBeGreaterThan(2)
    })
  })
})

describe('WorldMap marker positions and size', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('keeps nearby markers at their stored coordinates when filtering', async () => {
    const locations = [
      {
        ...createLocations(1)[0],
        type: 'home_vault' as const,
        id: 'a',
        coord_x: 50,
        coord_y: 50,
        group_key: 'gas_station',
      },
      {
        ...createLocations(1)[0],
        type: 'home_vault' as const,
        id: 'b',
        name: 'Second home',
        coord_x: 51,
        coord_y: 50,
        group_key: 'military',
      },
    ]
    const wrapper = mountMap({ locations, fogDisabled: true })
    for (const marker of wrapper.findAllComponents(MapMarkerStub)) {
      const location = locations.find((loc) => loc.name === marker.props('name'))
      expect(marker.props('x')).toBe(location!.coord_x)
      expect(marker.props('y')).toBe(location!.coord_y)
    }
    await wrapper.setProps({ siteTypeFilter: 'gas_station' })
    expect(wrapper.findAllComponents(MapMarkerStub)[0].props('x')).toBe(50)
  })

  it('grows markers more slowly than the map when zooming in', async () => {
    const wrapper = mountMap({
      locations: [{ ...createLocations(1)[0], type: 'home_vault' as const }],
      fogDisabled: true,
    })
    await wrapper.find('[aria-label="Zoom in"]').trigger('click')
    const zoom = Number(wrapper.find('.zoom-level').text().replace('%', '')) / 100
    const scale = wrapper.findAllComponents(MapMarkerStub)[0].props('scale')
    expect(scale).toBeCloseTo(1 / Math.sqrt(zoom))
    expect(zoom * scale).toBeGreaterThan(1)
    expect(zoom * scale).toBeLessThan(zoom)
  })
})
