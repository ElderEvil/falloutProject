import { describe, it, expect, beforeEach, vi } from 'vitest'
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

  function mountView() {
    return mount(MapView, {
      global: {
        stubs: {
          SidePanel: true,
          PageHeader: true,
          USkeleton: true,
          WorldMap: {
            name: 'WorldMap',
            template: '<div class="world-map-stub"><slot name="status" /></div>',
            props: [
              'locations',
              'vaultMarkers',
              'explorerTracks',
              'siteTypeFilter',
              'selectedMarkerId',
              'fogDisabled',
              'readyLocationIds',
            ],
            emits: ['marker-click', 'update:selectedMarkerId', 'vault-info'],
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
    it('should not open modal without ?place= query param', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      const wrapper = mountView()
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(false)
    })

    it('should open marker detail modal when ?place= matches a location', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('location')).toEqual(mockLocation)
    })

    it('should not open modal when ?place= does not match any location', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      mockRoute.query = { place: 'nonexistent' }
      const wrapper = mountView()
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(false)
    })

    it('should open modal for second location when ?place= matches it', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      mockRoute.query = { place: 'loc-2' }
      const wrapper = mountView()
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('location')).toEqual(mockLocation2)
    })

    it('should show refreshed location data in the modal after the store reloads', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('location')).toEqual(mockLocation)

      mapStore.locations = [{ ...mockLocation, name: 'Renamed Ruins' }, mockLocation2]
      await flushPromises()

      expect(wrapper.findComponent({ name: 'MarkerDetailModal' }).props('location')).toEqual({
        ...mockLocation,
        name: 'Renamed Ruins',
      })
    })

    it('should open modal when ?place= query param changes after mount', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      const wrapper = mountView()
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(false)

      mockRoute.query = { place: 'loc-2' }
      await flushPromises()

      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('location')).toEqual(mockLocation2)
    })

    it('should mark the location viewed when ?place= opens its modal', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      mockRoute.query = { place: 'loc-1' }
      mountView()
      await flushPromises()

      expect(mapStore.isLocationViewed('vault-1', 'loc-1')).toBe(true)
      expect(mapStore.hasUnseenDiscoveries).toBe(false)
    })

    it('should push ?place= when a marker is clicked and ignore the watcher echo', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false
      const viewedSpy = vi.spyOn(mapStore, 'markLocationViewed')

      const wrapper = mountView()
      await flushPromises()

      const worldMap = wrapper.findComponent({ name: 'WorldMap' })
      worldMap.vm.$emit('marker-click', { kind: 'location', data: mockLocation })
      await flushPromises()

      expect(mockPush).toHaveBeenCalledWith({ query: { place: 'loc-1' } })
      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(true)

      // Simulate the router applying the pushed query: the watcher echo must
      // not re-open or double-count the already-open location.
      mockRoute.query = { place: 'loc-1' }
      await flushPromises()

      expect(viewedSpy).toHaveBeenCalledTimes(1)
      expect(mockPush).toHaveBeenCalledTimes(1)
    })

    it('should not push a duplicate entry when ?place= already matches', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      mockRoute.query = { place: 'loc-1' }
      mountView()
      await flushPromises()

      expect(mockPush).not.toHaveBeenCalled()
    })

    it('should clear ?place= when the modal closes', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      mapStore.isLoading = false

      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(true)

      modal.vm.$emit('update:modelValue', false)
      await flushPromises()

      expect(mockReplace).toHaveBeenCalledWith({ query: {} })
    })

    it('should clear ?place= when a vault marker is clicked', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation, mockLocation2]
      const vaultMarker = {
        name: 'Vault 101',
        coord_x: 30,
        coord_y: 40,
        type: 'vault' as const,
        description: 'Unexplored vault signal',
      }
      mapStore.vaultMarkers = [vaultMarker]
      mapStore.isLoading = false

      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      const worldMap = wrapper.findComponent({ name: 'WorldMap' })
      worldMap.vm.$emit('marker-click', { kind: 'vault', data: vaultMarker })
      await flushPromises()

      expect(mockReplace).toHaveBeenCalledWith({ query: {} })
      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
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

    function mountMapWithVaults(vaults: (typeof vaultSummary)[]) {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const vaultStore = useVaultStore()
      vaultStore.vaults = vaults
      return mountView()
    }

    it('opens the summary panel from store data without navigating', async () => {
      const wrapper = mountMapWithVaults([vaultSummary])
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('vault-info', 'vault-2')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'VaultInfoModal' })
      expect(modal.props('open')).toBe(true)
      expect(modal.props('vault')).toEqual(vaultSummary)
      expect(modal.props('loading')).toBe(false)
      expect(wrapper.findComponent({ name: 'MarkerDetailModal' }).props('modelValue')).toBe(false)
      expect(mockPush).not.toHaveBeenCalled()
    })

    it('hydrates the vault list when the store is empty', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const vaultStore = useVaultStore()
      vaultStore.vaults = []
      const fetchSpy = vi.spyOn(vaultStore, 'fetchVaults').mockImplementation(async () => {
        vaultStore.vaults = [vaultSummary]
        return true
      })

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('vault-info', 'vault-2')
      await flushPromises()

      expect(fetchSpy).toHaveBeenCalledWith('test-token')
      expect(wrapper.findComponent({ name: 'VaultInfoModal' }).props('vault')).toEqual(vaultSummary)
      expect(mockPush).not.toHaveBeenCalled()
    })

    it('refetches the vault list when a stale store misses the selected vault', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const vaultStore = useVaultStore()
      vaultStore.vaults = [{ ...vaultSummary, id: 'vault-other', number: 999 }]
      const fetchSpy = vi.spyOn(vaultStore, 'fetchVaults').mockImplementation(async () => {
        vaultStore.vaults = [vaultSummary]
        return true
      })

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('vault-info', 'vault-2')
      await flushPromises()

      expect(fetchSpy).toHaveBeenCalledWith('test-token')
      const modal = wrapper.findComponent({ name: 'VaultInfoModal' })
      expect(modal.props('vault')).toEqual(vaultSummary)
      expect(modal.props('loading')).toBe(false)
    })

    it('keeps loading until the newest request resolves (A to B race)', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const vaultStore = useVaultStore()
      vaultStore.vaults = []
      const pending: Array<(value: boolean) => void> = []
      vi.spyOn(vaultStore, 'fetchVaults').mockImplementation(
        () => new Promise<boolean>((resolve) => pending.push(resolve))
      )
      const vaultSummaryB = { ...vaultSummary, id: 'vault-3', number: 122 }

      const wrapper = mountView()
      await flushPromises()

      const worldMap = wrapper.findComponent({ name: 'WorldMap' })
      worldMap.vm.$emit('vault-info', 'vault-2')
      await flushPromises()
      worldMap.vm.$emit('vault-info', 'vault-3')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'VaultInfoModal' })
      expect(modal.props('loading')).toBe(true)

      // The stale request settling first must not clear the newer spinner.
      pending[0]!(true)
      await flushPromises()
      expect(modal.props('loading')).toBe(true)

      vaultStore.vaults = [vaultSummaryB]
      pending[1]!(true)
      await flushPromises()

      expect(modal.props('loading')).toBe(false)
      expect(modal.props('vault')).toEqual(vaultSummaryB)
    })

    it('shows the loading state until the vault list resolves', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const vaultStore = useVaultStore()
      vaultStore.vaults = []
      let resolveFetch!: (value: boolean) => void
      const gate = new Promise<boolean>((resolve) => {
        resolveFetch = resolve
      })
      vi.spyOn(vaultStore, 'fetchVaults').mockReturnValue(gate)

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('vault-info', 'vault-2')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'VaultInfoModal' })
      expect(modal.props('open')).toBe(true)
      expect(modal.props('loading')).toBe(true)

      vaultStore.vaults = [vaultSummary]
      resolveFetch(true)
      await flushPromises()

      expect(modal.props('loading')).toBe(false)
      expect(modal.props('vault')).toEqual(vaultSummary)
    })

    it('opens the unavailable state when the record cannot be resolved', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const vaultStore = useVaultStore()
      vaultStore.vaults = []
      vi.spyOn(vaultStore, 'fetchVaults').mockResolvedValue(true)

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('vault-info', 'vault-404')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'VaultInfoModal' })
      expect(modal.props('open')).toBe(true)
      expect(modal.props('vault')).toBeNull()
      expect(modal.props('loading')).toBe(false)
    })

    it('closes the panel when it emits update:open false', async () => {
      const wrapper = mountMapWithVaults([vaultSummary])
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('vault-info', 'vault-2')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'VaultInfoModal' })
      modal.vm.$emit('update:open', false)
      await flushPromises()

      expect(modal.props('open')).toBe(false)
    })
  })

  describe('dispatch in-flight guard', () => {
    it('sends only one dispatch when confirmed twice while the first is still running', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
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

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
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
        clear_state: {
          clearable: true,
          cleared: false,
          clear_count: 0,
          tier: 0,
          time_remaining_seconds: 0,
          loot_table: 'low',
        },
      }
    }

    function mountWithClearable() {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      const clearable = clearableLocation()
      mapStore.locations = [clearable]
      mapStore.isLoading = false
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
      const vaultStore = useVaultStore()
      vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue(undefined)
      return clearable
    }

    it('opens the details modal (not the picker) for a clearable location click', async () => {
      const clearable = mountWithClearable()
      const wrapper = mountView()
      await flushPromises()

      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('dwellers')).toHaveLength(1)
      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).exists()).toBe(false)
    })

    it('preloads the vault before rendering supplies in the details modal', async () => {
      const clearable = mountWithClearable()
      const vaultStore = useVaultStore()
      let resolveVault!: () => void
      const gate = new Promise<void>((resolve) => {
        resolveVault = () => {
          vaultStore.loadedVaults = { 'vault-1': { stimpack: 10, radaway: 5 } as any }
          resolve()
        }
      })
      vi.mocked(vaultStore.ensureVaultLoaded).mockReturnValue(gate)

      const wrapper = mountView()
      await flushPromises()
      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      const loading = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(loading.props('suppliesLoading')).toBe(true)
      expect(loading.props('maxStimpaks')).toBe(0)

      resolveVault()
      await flushPromises()

      expect(loading.props('suppliesLoading')).toBe(false)
      expect(loading.props('maxStimpaks')).toBe(10)
      expect(loading.props('maxRadaways')).toBe(5)
    })

    it('still opens the details modal when the vault cannot be loaded', async () => {
      const clearable = mountWithClearable()
      const vaultStore = useVaultStore()
      vi.mocked(vaultStore.ensureVaultLoaded).mockRejectedValueOnce(new Error('unloadable'))

      const wrapper = mountView()
      await flushPromises()
      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('maxStimpaks')).toBe(0)
      expect(modal.props('suppliesLoading')).toBe(false)
    })

    it('dispatches the selected team and supplies from the details modal', async () => {
      const clearable = mountWithClearable()
      const explorationStore = useExplorationStore()
      const dispatchSpy = vi
        .spyOn(explorationStore, 'dispatchToLocation')
        .mockResolvedValue(undefined as never)
      vi.spyOn(mapStore, 'refreshMap').mockResolvedValue(undefined)

      const wrapper = mountView()
      await flushPromises()
      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(true)

      modal.vm.$emit('dispatch', {
        dwellerIds: ['dweller-1'],
        supplies: { stimpaks: 4, radaways: 2 },
      })
      await flushPromises()

      expect(dispatchSpy).toHaveBeenCalledWith('vault-1', ['dweller-1'], 'loc-1', {
        stimpaks: 4,
        radaways: 2,
      })
      expect(mapStore.refreshMap).toHaveBeenCalled()
      expect(modal.props('modelValue')).toBe(false)
    })

    it('keeps the ?place= deep link working without opening the picker', async () => {
      mountWithClearable()
      mockRoute.query = { place: 'loc-1' }

      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.findComponent({ name: 'MarkerDetailModal' }).props('modelValue')).toBe(true)
      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).exists()).toBe(false)
      // The shareable deep link survives: the query is neither pushed nor cleared.
      expect(mockReplace).not.toHaveBeenCalled()
      expect(mockPush).not.toHaveBeenCalled()
    })
  })

  describe('Explorer tracking scoping', () => {
    it('excludes active explorations from other vaults', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const explorationStore = useExplorationStore()
      // A stale run from the previous vault targets a location that exists on
      // this map; it must not surface as an "exploring" track.
      explorationStore.explorations = [
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

      const worldMap = wrapper.findComponent({ name: 'WorldMap' })
      const tracks = worldMap.props('explorerTracks') as ExplorerTrack[]
      expect(tracks).toHaveLength(1)
      expect(tracks[0].explorationId).toBe('expl-own')
    })
  })

  describe('map opportunity counters', () => {
    it('counts dispatched parties once and excludes unavailable places from ready sites', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      const state = {
        clearable: true,
        cleared: false,
        clear_count: 0,
        tier: 1,
        time_remaining_seconds: 0,
      }
      mapStore.locations = [
        { ...mockLocation, id: 'ready', clear_state: state },
        { ...mockLocation, id: 'busy', clear_state: state },
        { ...mockLocation, id: 'locked', is_unlocked: false, clear_state: state },
        {
          ...mockLocation,
          id: 'cooldown',
          clear_state: { ...state, cleared: true, time_remaining_seconds: 30 },
        },
        { ...mockLocation, id: 'reset', clear_state: { ...state, cleared: true } },
      ]
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
      const parties = wrapper.findAll('button').find((b) => b.text().includes('Parties out'))!
      const ready = wrapper.findAll('button').find((b) => b.text().includes('Ready to clear'))!
      expect(parties.text()).toContain('2')
      expect(ready.text()).toContain('2')
      await parties.trigger('click')
      expect(mockPush).toHaveBeenCalledWith({ name: 'exploration', params: { id: 'vault-1' } })
      await ready.trigger('click')
      expect(wrapper.findComponent({ name: 'WorldMap' }).props('readyLocationIds')).toEqual([
        'ready',
        'reset',
      ])
      expect(ready.attributes('aria-pressed')).toBe('true')
      await ready.trigger('click')
      expect(wrapper.findComponent({ name: 'WorldMap' }).props('readyLocationIds')).toBeNull()
    })
  })

  describe('admin fog debug tool', () => {
    it('is hidden for non-admins', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false

      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.text()).not.toContain('Remove fog')
    })

    it('toggles fog removal for admins', async () => {
      localStorage.setItem(
        'user',
        JSON.stringify({ id: 'u1', username: 'admin', email: 'a@a.com', is_superuser: true })
      )
      setActivePinia(createPinia())
      const store = useMapStore()
      vi.spyOn(store, 'fetchMap').mockResolvedValue(undefined)
      store.locations = [mockLocation]
      store.isLoading = false

      const wrapper = mountView()
      await flushPromises()

      const button = wrapper.findAll('button').find((b) => b.text().includes('Remove fog'))
      expect(button).toBeTruthy()
      await button!.trigger('click')
      await flushPromises()

      expect(wrapper.findComponent({ name: 'WorldMap' }).props('fogDisabled')).toBe(true)
    })
  })

  describe('site-type filter', () => {
    function seedSites() {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [{ ...mockLocation, group_key: 'gas_station' }]
      mapStore.placeGroups = [
        {
          key: 'gas_station',
          label: 'Gas Station',
          icon: 'mdi:gas-station',
          risk: 'low',
          description: 'A roadside fuel stop.',
        },
      ] as never
      mapStore.isLoading = false
    }

    const worldMapProps = (wrapper: ReturnType<typeof mountView>) =>
      wrapper.findComponent({ name: 'WorldMap' }).props()

    it('passes a stored site-type filter down to the map', async () => {
      // Null default selects the raw "any" serializer: store the bare key.
      localStorage.setItem('map:site-type-filter', 'gas_station')
      seedSites()

      const wrapper = mountView()
      await flushPromises()

      expect(worldMapProps(wrapper).siteTypeFilter).toBe('gas_station')
    })

    it('degrades a stored filter whose group is absent from this vault to All', async () => {
      localStorage.setItem('map:site-type-filter', 'military')
      seedSites()

      const wrapper = mountView()
      await flushPromises()

      expect(worldMapProps(wrapper).siteTypeFilter).toBeNull()
    })

    it('does not render the control when the map has no site groups', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false

      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.find('[aria-label="Filter by site type"]').exists()).toBe(false)
    })

    it('renders the control with the persisted selection when groups exist', async () => {
      localStorage.setItem('map:site-type-filter', 'gas_station')
      seedSites()

      const wrapper = mountView()
      await flushPromises()

      const trigger = wrapper.find('[aria-label="Filter by site type"]')
      expect(trigger.exists()).toBe(true)
    })

    it('does not offer the exclusion-zone easter egg as a filter option', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [{ ...mockLocation, group_key: 'exclusion_zone' }]
      mapStore.placeGroups = [
        {
          key: 'exclusion_zone',
          label: 'Restricted Exclusion Site',
          icon: 'mdi:fence',
          risk: 'high',
          description: 'A restricted complex.',
        },
      ] as never
      mapStore.isLoading = false

      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.find('[aria-label="Filter by site type"]').exists()).toBe(false)
    })

    it('degrades a stored exclusion-zone filter to All', async () => {
      localStorage.setItem('map:site-type-filter', 'exclusion_zone')
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [{ ...mockLocation, group_key: 'exclusion_zone' }]
      mapStore.placeGroups = [
        {
          key: 'exclusion_zone',
          label: 'Restricted Exclusion Site',
          icon: 'mdi:fence',
          risk: 'high',
          description: 'A restricted complex.',
        },
      ] as never
      mapStore.isLoading = false

      const wrapper = mountView()
      await flushPromises()

      expect(worldMapProps(wrapper).siteTypeFilter).toBeNull()
    })
  })

  describe('Dispatch party visibility', () => {
    function seedPartyRun() {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const explorationStore = useExplorationStore()
      vi.spyOn(explorationStore, 'fetchExplorationsByVault').mockResolvedValue([])
      vi.spyOn(explorationStore, 'fetchPartiesForActiveExplorations').mockResolvedValue(undefined)
      explorationStore.explorations = [
        exploration({
          id: 'expl-own',
          dweller_id: 'dweller-1',
          target_location_id: 'loc-1',
        }),
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
      }
      const { filter: dwellerFilter } = useDwellerStore()
      dwellerFilter.dwellers = [
        {
          id: 'dweller-1',
          first_name: 'Stephanie',
          last_name: 'Boyd',
          age_group: 'adult',
          is_adult: true,
          status: 'idle',
        },
        {
          id: 'dweller-2',
          first_name: 'Cooper',
          last_name: 'Howard',
          age_group: 'adult',
          is_adult: true,
          status: 'idle',
        },
      ] as never
      return explorationStore
    }

    it('refreshes dispatch parties when the map reloads explorations', async () => {
      const explorationStore = seedPartyRun()
      const partySpy = vi
        .spyOn(explorationStore, 'fetchPartiesForActiveExplorations')
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
      mapStore.locations = [mockLocation]

      const wrapper = mountView()
      await flushPromises()

      const tracks = wrapper
        .findComponent({ name: 'WorldMap' })
        .props('explorerTracks') as ExplorerTrack[]
      expect(tracks).toHaveLength(1)
      expect(tracks[0].partyNames).toEqual(['Stephanie Boyd', 'Cooper Howard'])
      wrapper.unmount()
    })

    it('collapses a solo dispatch track to just the anchor name', async () => {
      seedPartyRun()
      const explorationStore = useExplorationStore()
      explorationStore.explorationPartyMap = {}
      const { filter: dwellerFilter } = useDwellerStore()
      dwellerFilter.dwellers = [
        {
          id: 'dweller-1',
          first_name: 'Stephanie',
          last_name: 'Boyd',
          age_group: 'adult',
          is_adult: true,
          status: 'idle',
        },
      ] as never

      const wrapper = mountView()
      await flushPromises()

      const tracks = wrapper
        .findComponent({ name: 'WorldMap' })
        .props('explorerTracks') as ExplorerTrack[]
      expect(tracks[0].partyNames).toEqual(['Stephanie Boyd'])
      wrapper.unmount()
    })
  })
})
