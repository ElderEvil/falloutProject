import { describe, it, expect, beforeEach, vi } from 'vitest'
import { reactive } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MapView from '@/modules/map/views/MapView.vue'
import { useMapStore, VIEWED_LOCATIONS_STORAGE_KEY } from '@/modules/map/stores/map'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useAuthStore } from '@/modules/auth/stores/auth'
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
            template: '<div class="world-map-stub"></div>',
            props: ['locations', 'vaultMarkers', 'explorerTracks', 'selectedMarkerId', 'fogDisabled'],
            emits: ['marker-click', 'update:selectedMarkerId', 'explore-wasteland'],
          },
          MarkerDetailModal: {
            name: 'MarkerDetailModal',
            template: '<div class="modal-stub"></div>',
            props: ['modelValue', 'location', 'vaultMarker'],
            emits: ['update:modelValue', 'dispatch'],
          },
          ExplorationDurationModal: {
            name: 'ExplorationDurationModal',
            template: '<div class="duration-modal-stub"></div>',
            props: ['show', 'dwellerName', 'maxStimpaks', 'maxRadaways', 'allowRadaway', 'heading'],
            emits: ['confirm', 'cancel'],
          },
          PartySelectionModal: {
            name: 'PartySelectionModal',
            template: '<div class="picker-stub"></div>',
            props: [
              'modelValue',
              'quest',
              'vaultId',
              'dwellers',
              'currentParty',
              'maxPartySize',
              'title',
              'subtitle',
              'details',
              'showSupplies',
              'maxStimpaks',
              'maxRadaways',
            ],
            emits: ['update:modelValue', 'assign', 'start', 'details'],
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
      const { filter: dwellerFilter } = useDwellerStore()
      vi.spyOn(dwellerFilter, 'fetchDwellersByVault').mockResolvedValue(undefined)
      const vaultStore = useVaultStore()
      vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue(undefined)

      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      modal.vm.$emit('dispatch')
      await flushPromises()

      const picker = wrapper.findComponent({ name: 'PartySelectionModal' })
      picker.vm.$emit('assign', ['dweller-1'])
      picker.vm.$emit('assign', ['dweller-1'])
      await flushPromises()

      expect(dispatchSpy).toHaveBeenCalledTimes(1)
      resolveDispatch({ id: 'expl-1' })
      await flushPromises()
      expect(mapStore.refreshMap).toHaveBeenCalledTimes(1)
    })
  })

  describe('direct dispatch from a marker click', () => {
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
      dwellerFilter.dwellers = [{ id: 'dweller-1', first_name: 'Ada' } as never]
      vi.spyOn(dwellerFilter, 'fetchDwellersByVault').mockResolvedValue(undefined)
      const vaultStore = useVaultStore()
      vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue(undefined)
      return clearable
    }

    it('opens the team picker directly for a clearable, uncleared location', async () => {
      const clearable = mountWithClearable()
      const wrapper = mountView()
      await flushPromises()

      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      expect(wrapper.findComponent({ name: 'MarkerDetailModal' }).props('modelValue')).toBe(false)
      const picker = wrapper.findComponent({ name: 'PartySelectionModal' })
      expect(picker.props('modelValue')).toBe(true)
      expect(picker.props('title')).toBe('Rusty Depot')
    })

    it('waits for the vault to hydrate before showing supplies in the picker', async () => {
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

      // Picker must not render on unhydrated vault state (zero supplies).
      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).props('modelValue')).toBe(false)
      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).props('maxStimpaks')).toBe(0)

      resolveVault()
      await flushPromises()

      const picker = wrapper.findComponent({ name: 'PartySelectionModal' })
      expect(picker.props('modelValue')).toBe(true)
      expect(picker.props('maxStimpaks')).toBe(10)
      expect(picker.props('maxRadaways')).toBe(5)
    })

    it('keeps the picker closed when the vault cannot be loaded', async () => {
      const clearable = mountWithClearable()
      const vaultStore = useVaultStore()
      vi.mocked(vaultStore.ensureVaultLoaded).mockRejectedValueOnce(new Error('unloadable'))

      const wrapper = mountView()
      await flushPromises()
      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).props('modelValue')).toBe(false)
      expect(wrapper.findComponent({ name: 'MarkerDetailModal' }).props('modelValue')).toBe(false)
    })

    it('opens details instead of the picker for a clearable ?place= deep link', async () => {
      mountWithClearable()
      mockRoute.query = { place: 'loc-1' }

      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.findComponent({ name: 'MarkerDetailModal' }).props('modelValue')).toBe(true)
      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).props('modelValue')).toBe(false)
      // The shareable deep link survives: the query is neither pushed nor cleared.
      expect(mockReplace).not.toHaveBeenCalled()
      expect(mockPush).not.toHaveBeenCalled()
    })

    it('opens the detail modal from the picker Details action', async () => {
      const clearable = mountWithClearable()
      const wrapper = mountView()
      await flushPromises()
      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('marker-click', { kind: 'location', data: clearable })
      await flushPromises()

      wrapper.findComponent({ name: 'PartySelectionModal' }).vm.$emit('details')
      await flushPromises()

      expect(wrapper.findComponent({ name: 'PartySelectionModal' }).props('modelValue')).toBe(false)
      expect(wrapper.findComponent({ name: 'MarkerDetailModal' }).props('modelValue')).toBe(true)
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

  describe('map departure flow', () => {
    function mountWithDwellers() {
      useAuthStore().token = 'test-token'
      const { filter: dwellerStore } = useDwellerStore()
      dwellerStore.dwellers = [
        {
          id: 'dweller-1',
          first_name: 'Ada',
          last_name: 'Lovelace',
          is_adult: true,
          age_group: 'adult',
        } as any,
      ]
      vi.spyOn(dwellerStore, 'fetchDwellersByVault').mockResolvedValue(undefined)
      const vaultStore = useVaultStore()
      vi.spyOn(vaultStore, 'ensureVaultLoaded').mockResolvedValue(undefined)
      vi.spyOn(vaultStore, 'refreshVault').mockResolvedValue(undefined)
      vaultStore.loadedVaults = { 'vault-1': { stimpack: 10, radaway: 5 } as any }
      return { dwellerStore, vaultStore }
    }

    it('opens the dweller picker when empty wasteland is clicked', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()

      const wrapper = mountView()
      await flushPromises()

      expect(wrapper.find('.departure-picker').exists()).toBe(false)
      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('explore-wasteland')
      await flushPromises()

      expect(wrapper.find('.departure-picker').exists()).toBe(true)
      expect(wrapper.find('.departure-picker').text()).toContain('Explore the wasteland')
      expect(wrapper.find('.departure-dwellers button').text()).toContain('Send Ada')
    })

    it('scrolls the picker into view when it opens', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()

      const scrollSpy = vi.fn()
      const original = Object.getOwnPropertyDescriptor(Element.prototype, 'scrollIntoView')
      Object.defineProperty(Element.prototype, 'scrollIntoView', {
        configurable: true,
        writable: true,
        value: scrollSpy,
      })

      try {
        const wrapper = mountView()
        await flushPromises()

        wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('explore-wasteland')
        await flushPromises()

        expect(scrollSpy).toHaveBeenCalledTimes(1)
        expect(scrollSpy.mock.calls[0]?.[0]).toMatchObject({ block: 'nearest' })
      } finally {
        if (original) Object.defineProperty(Element.prototype, 'scrollIntoView', original)
        else Reflect.deleteProperty(Element.prototype, 'scrollIntoView')
      }
    })

    it('offers only available dwellers, even with no exploration records loaded', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      const { dwellerStore } = mountWithDwellers()
      dwellerStore.dwellers = [
        { id: 'd1', first_name: 'Idle', is_adult: true, age_group: 'adult', is_dead: false, status: 'idle' },
        { id: 'd2', first_name: 'Questing', is_adult: true, age_group: 'adult', is_dead: false, status: 'questing' },
        { id: 'd3', first_name: 'Fallen', is_adult: true, age_group: 'adult', is_dead: true, status: 'dead' },
        { id: 'd4', first_name: 'Roaming', is_adult: true, age_group: 'adult', is_dead: false, status: 'exploring' },
        { id: 'd5', first_name: 'Kid', is_adult: true, age_group: 'child', is_dead: false, status: 'idle' },
      ] as any[]
      useExplorationStore().explorations = []

      const wrapper = mountView()
      await flushPromises()
      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('explore-wasteland')
      await flushPromises()

      const names = wrapper.findAll('.departure-dwellers button').map((b) => b.text())
      expect(names).toEqual(['Send Idle'])
    })

    it('picking a dweller opens the duration modal with their name and vault supplies', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('explore-wasteland')
      await flushPromises()
      await wrapper.find('.departure-dwellers button').trigger('click')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'ExplorationDurationModal' })
      expect(modal.props('show')).toBe(true)
      expect(modal.props('dwellerName')).toBe('Ada')
      expect(modal.props('maxStimpaks')).toBe(10)
      expect(modal.props('maxRadaways')).toBe(5)
      expect(wrapper.find('.departure-picker').exists()).toBe(false)
    })

    it('sends the dweller roaming on confirm and refreshes the map', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()
      const explorationStore = useExplorationStore()
      vi.spyOn(explorationStore, 'sendDwellerToWasteland').mockResolvedValue(
        exploration({ duration: 4 })
      )
      vi.spyOn(mapStore, 'refreshMap').mockResolvedValue(undefined)

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('explore-wasteland')
      await flushPromises()
      await wrapper.find('.departure-dwellers button').trigger('click')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'ExplorationDurationModal' })
      modal.vm.$emit('confirm', { duration: 4, stimpaks: 2, radaways: 1 })
      await flushPromises()

      expect(explorationStore.sendDwellerToWasteland).toHaveBeenCalledWith(
        'vault-1',
        'dweller-1',
        4,
        'test-token',
        2,
        1,
        undefined
      )
      expect(mapStore.refreshMap).toHaveBeenCalled()
      expect(modal.props('show')).toBe(false)
    })

    it('resets the departure picker when switching vaults', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('explore-wasteland')
      await flushPromises()
      expect(wrapper.find('.departure-picker').exists()).toBe(true)

      mockRoute.params.id = 'vault-2'
      await flushPromises()

      expect(wrapper.find('.departure-picker').exists()).toBe(false)
      mockRoute.params.id = 'vault-1'
    })

    it('shows the heading in the picker when the map click carries one', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()

      const wrapper = mountView()
      await flushPromises()

      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('explore-wasteland', { headingDegrees: 90 })
      await flushPromises()

      expect(wrapper.find('.departure-picker').text()).toContain('E / 90°')
      expect(wrapper.find('.departure-dwellers button').text()).toContain('→ E / 90°')
    })

    it('labels the picker as free roam when no heading is chosen', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('explore-wasteland')
      await flushPromises()

      expect(wrapper.find('.departure-picker').text()).toContain('roaming')
      expect(wrapper.find('.departure-dwellers button').text()).not.toContain('→')
    })

    it('passes the heading into the duration modal and sends it on confirm', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()
      const explorationStore = useExplorationStore()
      vi.spyOn(explorationStore, 'sendDwellerToWasteland').mockResolvedValue(
        exploration({ duration: 4 })
      )
      vi.spyOn(mapStore, 'refreshMap').mockResolvedValue(undefined)

      const wrapper = mountView()
      await flushPromises()

      wrapper
        .findComponent({ name: 'WorldMap' })
        .vm.$emit('explore-wasteland', { headingDegrees: 90 })
      await flushPromises()
      await wrapper.find('.departure-dwellers button').trigger('click')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'ExplorationDurationModal' })
      expect(modal.props('heading')).toBe('E / 90°')

      modal.vm.$emit('confirm', { duration: 4, stimpaks: 2, radaways: 1 })
      await flushPromises()

      expect(explorationStore.sendDwellerToWasteland).toHaveBeenCalledWith(
        'vault-1',
        'dweller-1',
        4,
        'test-token',
        2,
        1,
        90
      )
      expect(mapStore.refreshMap).toHaveBeenCalled()
      expect(modal.props('show')).toBe(false)
    })

    it('sends a free-roam run without a heading when none was chosen', async () => {
      vi.spyOn(mapStore, 'fetchMap').mockResolvedValue(undefined)
      mapStore.locations = [mockLocation]
      mapStore.isLoading = false
      mountWithDwellers()
      const explorationStore = useExplorationStore()
      vi.spyOn(explorationStore, 'sendDwellerToWasteland').mockResolvedValue(
        exploration({ duration: 4 })
      )
      vi.spyOn(mapStore, 'refreshMap').mockResolvedValue(undefined)

      const wrapper = mountView()
      await flushPromises()

      wrapper.findComponent({ name: 'WorldMap' }).vm.$emit('explore-wasteland')
      await flushPromises()
      await wrapper.find('.departure-dwellers button').trigger('click')
      await flushPromises()

      const modal = wrapper.findComponent({ name: 'ExplorationDurationModal' })
      expect(modal.props('heading')).toBeNull()

      modal.vm.$emit('confirm', { duration: 4, stimpaks: 2, radaways: 1 })
      await flushPromises()

      expect(explorationStore.sendDwellerToWasteland).toHaveBeenCalledWith(
        'vault-1',
        'dweller-1',
        4,
        'test-token',
        2,
        1,
        undefined
      )
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
})
