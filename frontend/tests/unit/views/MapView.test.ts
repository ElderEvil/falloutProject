import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { reactive } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MapView from '@/modules/map/views/MapView.vue'
import { useMapStore, VIEWED_LOCATIONS_STORAGE_KEY } from '@/modules/map/stores/map'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import type { Exploration } from '@/modules/exploration/stores/exploration'
import type { ExplorerTrack } from '@/modules/map/models/map'

vi.mock('@/modules/map/services/mapService', () => ({
  getVaultMap: vi.fn().mockResolvedValue({ locations: [], vault_markers: [] }),
  getLocationDetail: vi.fn(),
}))

// The auth store refreshes the cached user on boot; resolve it from the seeded
// session so this view test never falls back to a real network call.
vi.mock('@/modules/auth/services/authService', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/modules/auth/services/authService')>()
  return {
    ...actual,
    authService: {
      ...actual.authService,
      getCurrentUser: vi.fn(async () => ({
        data: JSON.parse(localStorage.getItem('user') ?? '{}'),
      })),
    },
  }
})

const mockPush = vi.fn()
const mockReplace = vi.fn()

// Reactive route mock so tests can mutate route.query.place after mount and
// exercise the `watch(() => route.query.place, ...)` in MapView.vue.
const mockRoute = reactive({
  params: { id: 'vault-1' },
  query: {} as Record<string, string>,
})

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ push: mockPush, replace: mockReplace }),
}))

vi.mock('@/core/composables/useSidePanel', () => ({
  useSidePanel: () => ({ isCollapsed: { value: false } }),
}))

const mockLocation = {
  id: 'loc-1',
  name: 'Rusty Depot',
  normalized_name: 'rusty depot',
  type: 'discovery' as const,
  coord_x: 25.5,
  coord_y: 30.2,
  description: 'An old storage facility',
  vault_id: 'vault-1',
  exploration_id: 'expl-1',
  created_at: '2025-01-01T00:00:00Z',
  dwellers: [],
}

const mockLocation2 = {
  id: 'loc-2',
  name: 'Glowing Cave',
  normalized_name: 'glowing cave',
  type: 'visited' as const,
  coord_x: 75.3,
  coord_y: 45.8,
  description: 'Eerie green glow emanates',
  vault_id: 'vault-1',
  exploration_id: null,
  created_at: '2025-01-01T00:00:00Z',
  dwellers: [],
}

const readyState = {
  clearable: true,
  cleared: false,
  clear_count: 0,
  tier: 1,
  time_remaining_seconds: 0,
}

describe('MapView', () => {
  let mapStore: ReturnType<typeof useMapStore>

  function exploration(overrides: Partial<Exploration> = {}): Exploration {
    return {
      id: 'expl-1',
      vault_id: 'vault-1',
      dweller_id: 'dweller-1',
      status: 'active',
      duration: 4,
      start_time: '2026-01-01T00:00:00Z',
      end_time: null,
      events: [],
      loot_collected: [],
      total_distance: 0,
      total_caps_found: 0,
      enemies_encountered: 0,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-01T00:00:00Z',
      dweller_strength: 1,
      dweller_perception: 1,
      dweller_endurance: 1,
      dweller_charisma: 1,
      dweller_intelligence: 1,
      dweller_agility: 1,
      dweller_luck: 1,
      stimpaks: 0,
      radaways: 0,
      ...overrides,
    }
  }

  /** Seed the map store and stub its fetch so the view mounts without a request. */
  function seed(locations: unknown[] = [mockLocation, mockLocation2]) {
    vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
    mapStore.locations = locations as never
    mapStore.isLoading = false
  }

  const detail = (wrapper: ReturnType<typeof mountView>) =>
    wrapper.findComponent({ name: 'MarkerDetailModal' })
  const map = (wrapper: ReturnType<typeof mountView>) =>
    wrapper.findComponent({ name: 'WorldMap' })

  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 'u1', username: 'test', email: 'test@test.com' })
    )
    setActivePinia(createPinia())
    localStorage.removeItem(VIEWED_LOCATIONS_STORAGE_KEY)
    localStorage.removeItem('map:site-type-filter')
    mapStore = useMapStore()
    mockRoute.query = {}
    vi.clearAllMocks()
    vi.spyOn(console, 'error').mockImplementation(() => {})
  })

  function mountView(withRealHeader = false) {
    return mount(MapView, {
      global: {
        stubs: {
          SidePanel: true,
          ...(withRealHeader
            ? {}
            : {
                PageHeader: {
                  name: 'PageHeader',
                  template: '<header class="page-header-stub"><slot name="actions" /></header>',
                },
              }),
          USkeleton: true,
          WorldMap: {
            name: 'WorldMap',
            template:
              '<div class="world-map-stub"><slot name="filters" /><slot name="tools" /></div>',
            props: [
              'locations',
              'vaultMarkers',
              'explorerTracks',
              'siteTypeFilter',
              'selectedMarkerId',
              'fogDisabled',
              'readyLocationIds',
            ],
            emits: ['marker-click', 'update:selectedMarkerId', 'vault-info', 'clear-filters'],
          },
          MarkerDetailModal: {
            name: 'MarkerDetailModal',
            template: '<div class="modal-stub"></div>',
            props: [
              'modelValue',
              'location',
              'vaultMarker',
              'site',
              'dwellers',
              'maxPartySize',
              'maxStimpaks',
              'maxRadaways',
              'suppliesLoading',
            ],
            emits: ['update:modelValue', 'dispatch'],
          },
          VaultInfoModal: {
            name: 'VaultInfoModal',
            template: '<div class="vault-info-stub"></div>',
            props: ['open', 'vault', 'loading'],
            emits: ['update:open'],
          },
          teleport: true,
        },
      },
    })
  }

  describe('?place= query param handling', () => {
    it.each([[undefined], ['nonexistent']])(
      'should not open the modal for place=%s',
      async (place) => {
        seed()
        mockRoute.query = place ? { place } : {}

        const wrapper = mountView()
        await flushPromises()

        expect(detail(wrapper).props('modelValue')).toBe(false)
      }
    )

    it.each([
      ['loc-1', mockLocation],
      ['loc-2', mockLocation2],
    ])('should open the detail modal when ?place=%s matches', async (place, expected) => {
      seed()
      mockRoute.query = { place }

      const wrapper = mountView()
      await flushPromises()

      const modal = detail(wrapper)
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('location')).toEqual(expected)
    })

    it('should show refreshed location data in the modal after the store reloads', async () => {
      seed()
      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      expect(detail(wrapper).props('location')).toEqual(mockLocation)

      mapStore.locations = [{ ...mockLocation, name: 'Renamed Ruins' }, mockLocation2]
      await flushPromises()

      expect(detail(wrapper).props('location')).toEqual({
        ...mockLocation,
        name: 'Renamed Ruins',
      })
    })

    it('should open the modal when ?place= changes after mount', async () => {
      seed()
      const wrapper = mountView()
      await flushPromises()
      expect(detail(wrapper).props('modelValue')).toBe(false)

      mockRoute.query = { place: 'loc-2' }
      await flushPromises()

      expect(detail(wrapper).props('modelValue')).toBe(true)
      expect(detail(wrapper).props('location')).toEqual(mockLocation2)
    })

    it('should mark the location viewed when ?place= opens its modal', async () => {
      seed()
      mockRoute.query = { place: 'loc-1' }
      mountView()
      await flushPromises()

      expect(mapStore.isLocationViewed('vault-1', 'loc-1')).toBe(true)
      expect(mapStore.hasUnseenDiscoveries).toBe(false)
    })

    it('should push ?place= when a marker is clicked and ignore the watcher echo', async () => {
      seed()
      const viewedSpy = vi.spyOn(mapStore, 'markLocationViewed')
      const wrapper = mountView()
      await flushPromises()

      map(wrapper).vm.$emit('marker-click', { kind: 'location', data: mockLocation })
      await flushPromises()

      expect(mockPush).toHaveBeenCalledWith({ query: { place: 'loc-1' } })
      expect(detail(wrapper).props('modelValue')).toBe(true)

      // Simulate the router applying the pushed query: the watcher echo must
      // not re-open or double-count the already-open location.
      mockRoute.query = { place: 'loc-1' }
      await flushPromises()

      expect(viewedSpy).toHaveBeenCalledTimes(1)
      expect(mockPush).toHaveBeenCalledTimes(1)
    })

    it('should not push a duplicate entry when ?place= already matches', async () => {
      seed()
      mockRoute.query = { place: 'loc-1' }
      mountView()
      await flushPromises()
      expect(mockPush).not.toHaveBeenCalled()
    })

    it('should clear ?place= when the modal closes', async () => {
      seed()
      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()
      expect(detail(wrapper).props('modelValue')).toBe(true)

      detail(wrapper).vm.$emit('update:modelValue', false)
      await flushPromises()

      expect(mockReplace).toHaveBeenCalledWith({ query: {} })
    })

    it('should clear ?place= when a vault marker is clicked', async () => {
      seed()
      const vaultMarker = {
        name: 'Vault 101',
        coord_x: 30,
        coord_y: 40,
        type: 'vault' as const,
        description: 'Unexplored vault signal',
      }
      mapStore.vaultMarkers = [vaultMarker]
      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      map(wrapper).vm.$emit('marker-click', { kind: 'vault', data: vaultMarker })
      await flushPromises()

      expect(mockReplace).toHaveBeenCalledWith({ query: {} })
      const modal = detail(wrapper)
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('vaultMarker')).toEqual(vaultMarker)
    })
  })

  describe('Own-vault info panel', () => {
    const vaultSummary = {
      id: 'vault-2',
      number: 121,
      bottle_caps: 1500,
      happiness: 82,
      power: 40,
      power_max: 80,
      food: 30,
      food_max: 60,
      water: 20,
      water_max: 50,
      population_max: null,
      radio_mode: 'recruitment',
      incidents_disabled: false,
      created_at: '2026-01-01T00:00:00Z',
      updated_at: '2026-01-02T03:04:05Z',
      room_count: 12,
      dweller_count: 18,
      stimpack: 5,
      radaway: 3,
    }

    function seedVaults(vaults: unknown[]) {
      const vaultStore = useVaultStore()
      vaultStore.vaults = vaults as never
      return vaultStore
    }

    /** Mount with the seeded vault list, then open the summary for vault-2. */
    async function openVaultInfo(
      vaults: unknown[],
      beforeSelect?: (vaultStore: ReturnType<typeof useVaultStore>) => void
    ) {
      seed()
      const vaultStore = seedVaults(vaults)
      const wrapper = mountView()
      await flushPromises()
      beforeSelect?.(vaultStore)
      map(wrapper).vm.$emit('vault-info', 'vault-2')
      await flushPromises()
      const modal = wrapper.findComponent({ name: 'VaultInfoModal' })
      return { wrapper, vaultStore, modal }
    }

    it('opens the summary panel from store data without navigating', async () => {
      const { wrapper, modal } = await openVaultInfo([vaultSummary])
      expect(modal.props('open')).toBe(true)
      expect(modal.props('vault')).toEqual(vaultSummary)
      expect(modal.props('loading')).toBe(false)
      expect(detail(wrapper).props('modelValue')).toBe(false)
      expect(mockPush).not.toHaveBeenCalled()
    })

    it.each([
      ['an empty store', []],
      ['a stale store missing the selected vault', [{ ...vaultSummary, id: 'vault-other', number: 999 }]],
    ])('hydrates the vault list from %s', async (_, seeded) => {
      let fetchSpy!: ReturnType<typeof vi.spyOn>
      const { modal } = await openVaultInfo(seeded, (vaultStore) => {
        fetchSpy = vi.spyOn(vaultStore, 'fetchVaults').mockImplementation(async () => {
          vaultStore.vaults = [vaultSummary] as never
          return true
        })
      })

      expect(fetchSpy).toHaveBeenCalledWith()
      expect(modal.props('vault')).toEqual(vaultSummary)
      expect(modal.props('loading')).toBe(false)
      expect(mockPush).not.toHaveBeenCalled()
    })

    it('keeps loading until the newest request resolves (A to B race)', async () => {
      const pending: Array<(value: boolean) => void> = []
      const vaultSummaryB = { ...vaultSummary, id: 'vault-3', number: 122 }
      const { wrapper, vaultStore, modal } = await openVaultInfo([], (store) => {
        vi.spyOn(store, 'fetchVaults').mockImplementation(
          () => new Promise<boolean>((resolve) => pending.push(resolve))
        )
      })
      // A second selection while the first request is still open.
      map(wrapper).vm.$emit('vault-info', 'vault-3')
      await flushPromises()
      expect(modal.props('loading')).toBe(true)

      // The stale request settling first must not clear the newer spinner.
      pending[0]!(true)
      await flushPromises()
      expect(modal.props('loading')).toBe(true)

      vaultStore.vaults = [vaultSummaryB] as never
      pending[1]!(true)
      await flushPromises()

      expect(modal.props('loading')).toBe(false)
      expect(modal.props('vault')).toEqual(vaultSummaryB)
    })

    it('shows the loading state until the vault list resolves', async () => {
      let resolveFetch!: (value: boolean) => void
      const { vaultStore, modal } = await openVaultInfo([], (store) => {
        vi.spyOn(store, 'fetchVaults').mockReturnValue(
          new Promise<boolean>((resolve) => {
            resolveFetch = resolve
          })
        )
      })
      expect(modal.props('open')).toBe(true)
      expect(modal.props('loading')).toBe(true)

      vaultStore.vaults = [vaultSummary] as never
      resolveFetch(true)
      await flushPromises()

      expect(modal.props('loading')).toBe(false)
      expect(modal.props('vault')).toEqual(vaultSummary)
    })

    it('opens the unavailable state when the record cannot be resolved', async () => {
      const { modal } = await openVaultInfo([], (vaultStore) => {
        vi.spyOn(vaultStore, 'fetchVaults').mockResolvedValue(true)
      })
      expect(modal.props('open')).toBe(true)
      expect(modal.props('vault')).toBeNull()
      expect(modal.props('loading')).toBe(false)
    })

    it('closes the panel when it emits update:open false', async () => {
      const { modal } = await openVaultInfo([vaultSummary])
      modal.vm.$emit('update:open', false)
      await flushPromises()
      expect(modal.props('open')).toBe(false)
    })
  })

  describe('dispatch in-flight guard', () => {
    it('sends only one dispatch when confirmed twice while the first is still running', async () => {
      seed([mockLocation])
      const explorationStore = useExplorationStore()
      let resolveDispatch!: (value: unknown) => void
      const gate = new Promise((resolve) => {
        resolveDispatch = resolve
      })
      const dispatchSpy = vi
        .spyOn(explorationStore, 'dispatchToLocation')
        .mockReturnValue(gate as never)
      vi.spyOn(mapStore, 'refreshMap').mockResolvedValue(undefined)

      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      const modal = detail(wrapper)
      const payload = { dwellerIds: ['dweller-1'], supplies: { stimpaks: 0, radaways: 0 } }
      modal.vm.$emit('dispatch', payload)
      modal.vm.$emit('dispatch', payload)
      await flushPromises()

      expect(dispatchSpy).toHaveBeenCalledTimes(1)
      resolveDispatch({ id: 'expl-1' })
      await flushPromises()
      expect(mapStore.refreshMap).toHaveBeenCalledTimes(1)
    })
  })

  describe('dispatch from the location details modal', () => {
    function clearableLocation() {
      return {
        ...mockLocation,
        clear_state: { ...readyState, tier: 0, loot_table: 'low' },
      }
    }

    function mountWithClearable() {
      const clearable = clearableLocation()
      seed([clearable])
      const { filter: dwellerFilter } = useDwellerStore()
      dwellerFilter.dwellers = [
        {
          id: 'dweller-1',
          first_name: 'Ada',
          last_name: 'Lovelace',
          age_group: 'adult',
          is_adult: true,
          status: 'idle',
        } as never,
      ]
      vi.spyOn(dwellerFilter, 'fetchDwellersByVault').mockResolvedValue(undefined)
      vi.spyOn(useVaultStore(), 'ensureVaultLoaded').mockResolvedValue(undefined)
      return clearable
    }

    it('opens the details modal (not the picker) for a clearable location click', async () => {
      const clearable = mountWithClearable()
      const wrapper = mountView()
      await flushPromises()

      map(wrapper).vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      const modal = detail(wrapper)
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('dwellers')).toHaveLength(1)
      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).exists()).toBe(false)
    })

    it.each(['active', 'returning'] as const)(
      'excludes every %s exploration team member even when their cached status is idle',
      async (status) => {
        mountWithClearable()
        const explorationStore = useExplorationStore()
        explorationStore.explorations = [
          exploration({ id: 'team-run', dweller_id: 'leader', status }),
        ]
        explorationStore.explorationPartyMap = {
          'team-run': [{ dweller_id: 'dweller-1' }] as never,
        }
        const wrapper = mountView()
        await flushPromises()
        expect(detail(wrapper).props('dwellers')).toEqual([])
      }
    )

    it('allows members of completed teams and teams in another vault', async () => {
      mountWithClearable()
      const explorationStore = useExplorationStore()
      explorationStore.explorations = [
        exploration({ id: 'done', dweller_id: 'leader', status: 'completed' }),
        exploration({ id: 'other', dweller_id: 'leader', vault_id: 'other-vault' }),
      ]
      explorationStore.explorationPartyMap = {
        done: [{ dweller_id: 'dweller-1' }] as never,
        other: [{ dweller_id: 'dweller-1' }] as never,
      }
      const wrapper = mountView()
      await flushPromises()
      expect(detail(wrapper).props('dwellers')).toHaveLength(1)
    })

    it('refreshes the dweller roster even when cached candidates already exist', async () => {
      const clearable = mountWithClearable()
      const { filter } = useDwellerStore()
      const wrapper = mountView()
      await flushPromises()
      map(wrapper).vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()
      expect(filter.fetchDwellersByVault).toHaveBeenCalledWith('vault-1')
    })

    it('preloads the vault before rendering supplies in the details modal', async () => {
      const clearable = mountWithClearable()
      const vaultStore = useVaultStore()
      let resolveVault!: () => void
      const gate = new Promise<void>((resolve) => {
        resolveVault = () => {
          vaultStore.loadedVaults = { 'vault-1': { stimpack: 10, radaway: 5 } as never } as never
          resolve()
        }
      })
      vi.mocked(vaultStore.ensureVaultLoaded).mockReturnValue(gate)

      const wrapper = mountView()
      await flushPromises()
      map(wrapper).vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      const modal = detail(wrapper)
      expect(modal.props('suppliesLoading')).toBe(true)
      expect(modal.props('maxStimpaks')).toBe(0)

      resolveVault()
      await flushPromises()

      expect(modal.props('suppliesLoading')).toBe(false)
      expect(modal.props('maxStimpaks')).toBe(10)
      expect(modal.props('maxRadaways')).toBe(5)
    })

    it('still opens the details modal when the vault cannot be loaded', async () => {
      const clearable = mountWithClearable()
      vi.mocked(useVaultStore().ensureVaultLoaded).mockRejectedValueOnce(new Error('unloadable'))

      const wrapper = mountView()
      await flushPromises()
      map(wrapper).vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      const modal = detail(wrapper)
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('maxStimpaks')).toBe(0)
      expect(modal.props('suppliesLoading')).toBe(false)
    })

    it('dispatches the selected team and supplies from the details modal', async () => {
      const clearable = mountWithClearable()
      const dispatchSpy = vi
        .spyOn(useExplorationStore(), 'dispatchToLocation')
        .mockResolvedValue(undefined as never)
      vi.spyOn(mapStore, 'refreshMap').mockResolvedValue(undefined)

      const wrapper = mountView()
      await flushPromises()
      map(wrapper).vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      const modal = detail(wrapper)
      expect(modal.props('modelValue')).toBe(true)

      modal.vm.$emit('dispatch', {
        dwellerIds: ['dweller-1'],
        supplies: { stimpaks: 4, radaways: 2 },
        purpose: 'clear',
      })
      await flushPromises()

      expect(dispatchSpy).toHaveBeenCalledWith(
        'vault-1',
        ['dweller-1'],
        'loc-1',
        { stimpaks: 4, radaways: 2 },
        'clear'
      )
      expect(mapStore.refreshMap).toHaveBeenCalled()
      expect(modal.props('modelValue')).toBe(false)
    })

    it('keeps the ?place= deep link working without opening the picker', async () => {
      mountWithClearable()
      mockRoute.query = { place: 'loc-1' }

      const wrapper = mountView()
      await flushPromises()

      expect(detail(wrapper).props('modelValue')).toBe(true)
      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).exists()).toBe(false)
      // The shareable deep link survives: the query is neither pushed nor cleared.
      expect(mockReplace).not.toHaveBeenCalled()
      expect(mockPush).not.toHaveBeenCalled()
    })
  })

  describe('Explorer tracking scoping', () => {
    it('excludes active explorations from other vaults', async () => {
      seed([mockLocation])
      useExplorationStore().explorations = [
        // A stale run from the previous vault targets a location on this map;
        // it must not surface as an "exploring" track.
        exploration({
          id: 'expl-other',
          vault_id: 'vault-2',
          dweller_id: 'dweller-9',
          target_location_id: 'loc-1',
        }),
        exploration({
          id: 'expl-own',
          vault_id: 'vault-1',
          dweller_id: 'dweller-1',
          target_location_id: 'loc-1',
        }),
      ]

      const wrapper = mountView()
      await flushPromises()

      const tracks = map(wrapper).props('explorerTracks') as ExplorerTrack[]
      expect(tracks).toHaveLength(1)
      expect(tracks[0].explorationId).toBe('expl-own')
    })
  })

  describe('map opportunity counters', () => {
    it('counts dispatched parties once and excludes unavailable places from ready sites', async () => {
      seed([
        { ...mockLocation, id: 'ready', clear_state: readyState },
        { ...mockLocation, id: 'busy', clear_state: readyState },
        { ...mockLocation, id: 'locked', is_unlocked: false, clear_state: readyState },
        {
          ...mockLocation,
          id: 'cooldown',
          clear_state: { ...readyState, cleared: true, time_remaining_seconds: 30 },
        },
        { ...mockLocation, id: 'reset', clear_state: { ...readyState, cleared: true } },
      ])
      const store = useExplorationStore()
      vi.spyOn(store, 'fetchExplorationsByVault').mockResolvedValue([])
      store.explorations = [
        exploration({ id: 'party', target_location_id: 'busy' }),
        exploration({ id: 'return', status: 'returning', target_location_id: 'cooldown' }),
        exploration({ id: 'solo', target_location_id: null }),
        exploration({ id: 'other', vault_id: 'another-vault', target_location_id: 'ready' }),
        exploration({ id: 'done', status: 'completed', target_location_id: 'ready' }),
      ]
      const wrapper = mountView()
      await flushPromises()
      const parties = wrapper.find('.page-header-stub')
      expect(parties.findAll('button')).toHaveLength(0)
      const ready = wrapper.findAll('button').find((b) => b.text() === 'Ready to clear')!
      expect(parties.text()).toContain('Parties out')
      expect(parties.text()).toContain('Ready to clear')
      expect(wrapper.find('.world-map-stub').text()).not.toContain('Parties out')
      expect(parties.text()).toContain('2')
      await ready.trigger('click')
      expect(map(wrapper).props('readyLocationIds')).toEqual(['ready', 'reset'])
      expect(ready.attributes('aria-pressed')).toBe('true')
      await ready.trigger('click')
      expect(map(wrapper).props('readyLocationIds')).toBeNull()
    })

    it('makes the header counters actionable', async () => {
      seed([{ ...mockLocation, id: 'ready', clear_state: readyState }])
      const wrapper = mountView(true)
      await flushPromises()

      await wrapper.get('[aria-label="Open expeditions: 0"]').trigger('click')
      expect(mockPush).toHaveBeenCalledWith({ name: 'exploration', params: { id: 'vault-1' } })

      await wrapper.get('[aria-label="Filter ready places: 1"]').trigger('click')
      await flushPromises()
      expect(map(wrapper).props('readyLocationIds')).toEqual(['ready'])

      await wrapper.get('[aria-label="Clear ready filter: 1"]').trigger('click')
      await flushPromises()
      expect(map(wrapper).props('readyLocationIds')).toBeNull()
      wrapper.unmount()
    })
  })

  describe('admin fog debug tool', () => {
    it('is hidden for non-admins', async () => {
      seed([mockLocation])
      const wrapper = mountView()
      await flushPromises()
      expect(wrapper.text()).not.toContain('Reveal fog')
    })

    it('toggles fog removal for admins', async () => {
      localStorage.setItem(
        'user',
        JSON.stringify({ id: 'u1', username: 'admin', email: 'a@a.com', is_superuser: true })
      )
      setActivePinia(createPinia())
      const store = useMapStore()
      vi.spyOn(store, 'fetchMap').mockResolvedValue(undefined)
      store.locations = [mockLocation] as never
      store.isLoading = false

      const wrapper = mountView()
      await flushPromises()

      const button = wrapper.findAll('button').find((b) => b.text().includes('Reveal fog'))!
      await button.trigger('click')
      await flushPromises()

      expect(map(wrapper).props('fogDisabled')).toBe(true)
      expect(button.text()).toContain('Restore fog')
      expect(button.attributes('aria-pressed')).toBe('true')
      expect(wrapper.find('details').exists()).toBe(false)
      await button.trigger('click')
      await flushPromises()
      expect(map(wrapper).props('fogDisabled')).toBe(false)
      expect(button.text()).toContain('Reveal fog')
      expect(button.attributes('aria-pressed')).toBe('false')
    })
  })

  describe('site-type filter', () => {
    function seedSites() {
      seed([{ ...mockLocation, group_key: 'gas_station' }])
      mapStore.placeGroups = [
        {
          key: 'gas_station',
          label: 'Gas Station',
          icon: 'mdi:gas-station',
          risk: 'low',
          description: 'A roadside fuel stop.',
        },
      ] as never
    }

    const worldMapProps = (wrapper: ReturnType<typeof mountView>) => map(wrapper).props()

    async function mountWithReadyFilter() {
      seedSites()
      mapStore.locations[0]!.clear_state = readyState as never
      const wrapper = mountView()
      await flushPromises()
      await wrapper.findAll('button').find((b) => b.text() === 'Ready to clear')!.trigger('click')
      await flushPromises()
      return wrapper
    }

    it('combines the ready filter with a site type and shows removable chips', async () => {
      const wrapper = await mountWithReadyFilter()
      expect(worldMapProps(wrapper).readyLocationIds).not.toBeNull()
      wrapper.findComponent({ name: 'Select' }).vm.$emit('update:modelValue', 'gas_station')
      await flushPromises()
      expect(worldMapProps(wrapper).siteTypeFilter).toBe('gas_station')
      expect(worldMapProps(wrapper).readyLocationIds).not.toBeNull()
      expect(wrapper.findAll('button').find((b) => b.text() === 'Ready to clear')!.attributes('aria-pressed')).toBe('true')
      // Both active filters surface as chips above the map.
      expect(wrapper.find('[aria-label="Clear site type filter"]').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Clear ready-to-clear filter"]').exists()).toBe(true)

      await wrapper.get('[aria-label="Clear site type filter"]').trigger('click')
      await flushPromises()
      expect(worldMapProps(wrapper).siteTypeFilter).toBeNull()
      expect(worldMapProps(wrapper).readyLocationIds).not.toBeNull()

      await wrapper.get('[aria-label="Clear ready-to-clear filter"]').trigger('click')
      await flushPromises()
      expect(worldMapProps(wrapper).readyLocationIds).toBeNull()
      expect(wrapper.find('[aria-label="Clear site type filter"]').exists()).toBe(false)
    })

    it.each([
      ['the command bar', 'clearAllButton'],
      ['the map callout', 'clearFilters'],
    ])('clears every active filter from %s', async (_, source) => {
      localStorage.setItem('map:site-type-filter', 'gas_station')
      const wrapper = await mountWithReadyFilter()
      expect(worldMapProps(wrapper).siteTypeFilter).toBe('gas_station')
      expect(worldMapProps(wrapper).readyLocationIds).not.toBeNull()

      if (source === 'clearAllButton') {
        await wrapper.findAll('button').find((b) => b.text() === 'Clear all')!.trigger('click')
      } else {
        map(wrapper).vm.$emit('clear-filters')
      }
      await flushPromises()

      expect(worldMapProps(wrapper).siteTypeFilter).toBeNull()
      expect(worldMapProps(wrapper).readyLocationIds).toBeNull()
    })

    it('passes a stored site-type filter down and renders the control', async () => {
      // Null default selects the raw "any" serializer: store the bare key.
      localStorage.setItem('map:site-type-filter', 'gas_station')
      seedSites()

      const wrapper = mountView()
      await flushPromises()

      expect(worldMapProps(wrapper).siteTypeFilter).toBe('gas_station')
      expect(wrapper.find('[aria-label="Filter by site type"]').exists()).toBe(true)
    })

    it('degrades a stored filter whose group is absent from this vault to All', async () => {
      localStorage.setItem('map:site-type-filter', 'military')
      seedSites()

      const wrapper = mountView()
      await flushPromises()

      expect(worldMapProps(wrapper).siteTypeFilter).toBeNull()
    })

    it.each([
      ['no site groups', []],
      [
        'only the exclusion-zone easter egg',
        [
          {
            key: 'exclusion_zone',
            label: 'Restricted Exclusion Site',
            icon: 'mdi:fence',
            risk: 'high',
            description: 'A restricted complex.',
          },
        ],
      ],
    ])('does not render the control with %s', async (_, groups) => {
      seed([{ ...mockLocation, group_key: groups[0]?.key as string | undefined }])
      mapStore.placeGroups = groups as never

      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.find('[aria-label="Filter by site type"]').exists()).toBe(false)
    })

    it('degrades a stored exclusion-zone filter to All', async () => {
      localStorage.setItem('map:site-type-filter', 'exclusion_zone')
      seed([{ ...mockLocation, group_key: 'exclusion_zone' }])
      mapStore.placeGroups = [
        {
          key: 'exclusion_zone',
          label: 'Restricted Exclusion Site',
          icon: 'mdi:fence',
          risk: 'high',
          description: 'A restricted complex.',
        },
      ] as never

      const wrapper = mountView()
      await flushPromises()

      expect(worldMapProps(wrapper).siteTypeFilter).toBeNull()
    })
  })

  describe('Dispatch party visibility', () => {
    const adult = (id: string, first: string, last: string) => ({
      id,
      first_name: first,
      last_name: last,
      age_group: 'adult',
      is_adult: true,
      status: 'idle',
    })

    function seedPartyRun() {
      seed([mockLocation])
      const explorationStore = useExplorationStore()
      vi.spyOn(explorationStore, 'fetchExplorationsByVault').mockResolvedValue([])
      vi.spyOn(explorationStore, 'fetchPartiesForActiveExplorations').mockResolvedValue(undefined)
      explorationStore.explorations = [
        exploration({ id: 'expl-own', dweller_id: 'dweller-1', target_location_id: 'loc-1' }),
      ]
      explorationStore.explorationPartyMap = {
        'expl-own': [
          {
            id: 'member-1',
            exploration_id: 'expl-own',
            vault_id: 'vault-1',
            dweller_id: 'dweller-1',
            slot_number: 1,
            status: 'assigned',
            created_at: null,
            updated_at: null,
          },
          {
            id: 'member-2',
            exploration_id: 'expl-own',
            vault_id: 'vault-1',
            dweller_id: 'dweller-2',
            slot_number: 2,
            status: 'assigned',
            created_at: null,
            updated_at: null,
          },
        ],
      } as never
      useDwellerStore().filter.dwellers = [
        adult('dweller-1', 'Stephanie', 'Boyd'),
        adult('dweller-2', 'Cooper', 'Howard'),
      ] as never
      return explorationStore
    }

    it('refreshes dispatch parties when the map reloads explorations', async () => {
      const partySpy = vi
        .spyOn(seedPartyRun(), 'fetchPartiesForActiveExplorations')
        .mockResolvedValue(undefined)

      const wrapper = mountView()
      await flushPromises()
      // The 30s poll replaces the locations array; the watcher then re-syncs
      // active explorations and their parties.
      mapStore.locations = [...mapStore.locations]
      await flushPromises()

      expect(partySpy).toHaveBeenCalledWith('vault-1')
      wrapper.unmount()
    })

    it('threads the dispatch party names into the explorer tracks', async () => {
      seedPartyRun()
      mapStore.locations = [mockLocation] as never

      const wrapper = mountView()
      await flushPromises()

      const tracks = map(wrapper).props('explorerTracks') as ExplorerTrack[]
      expect(tracks).toHaveLength(1)
      expect(tracks[0].partyNames).toEqual(['Stephanie Boyd', 'Cooper Howard'])
      wrapper.unmount()
    })

    it('collapses a solo dispatch track to just the anchor name', async () => {
      seedPartyRun()
      useExplorationStore().explorationPartyMap = {}
      useDwellerStore().filter.dwellers = [adult('dweller-1', 'Stephanie', 'Boyd')] as never

      const wrapper = mountView()
      await flushPromises()

      const tracks = map(wrapper).props('explorerTracks') as ExplorerTrack[]
      expect(tracks[0].partyNames).toEqual(['Stephanie Boyd'])
      wrapper.unmount()
    })
  })

  describe('header help', () => {
    it('offers header help about the world map', async () => {
      seed([])

      const wrapper = mountView(true)
      // PageHelp loads asynchronously on the first header mount of the file, so
      // poll instead of assuming one flush settles the dynamic import.
      await vi.waitFor(() => {
        expect(wrapper.find('button[aria-label="About World Map"]').exists()).toBe(true)
      })
      wrapper.unmount()
    })
  })
})
