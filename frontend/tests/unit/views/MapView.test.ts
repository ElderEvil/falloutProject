import { describe, it, expect, beforeEach, vi } from 'vitest'
import { reactive } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MapView from '@/modules/map/views/MapView.vue'
import { useMapStore, VIEWED_LOCATIONS_STORAGE_KEY } from '@/modules/map/stores/map'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
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
            props: ['locations', 'vaultMarkers', 'explorerTracks'],
          },
          MarkerDetailModal: {
            name: 'MarkerDetailModal',
            template: '<div class="modal-stub"></div>',
            props: ['modelValue', 'location', 'vaultMarker'],
            emits: ['update:modelValue', 'dispatch'],
          },
          PartySelectionModal: {
            name: 'PartySelectionModal',
            template: '<div class="picker-stub"></div>',
            props: ['modelValue', 'quest', 'vaultId', 'dwellers', 'currentParty', 'maxPartySize'],
            emits: ['update:modelValue', 'assign', 'start'],
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
      mapStore.isLoading = false

      mockRoute.query = { place: 'loc-1' }
      const wrapper = mountView()
      await flushPromises()

      const worldMap = wrapper.findComponent({ name: 'WorldMap' })
      worldMap.vm.$emit('marker-click', { kind: 'vault', data: { id: 'vm-1' } })
      await flushPromises()

      expect(mockReplace).toHaveBeenCalledWith({ query: {} })
      const modal = wrapper.findComponent({ name: 'MarkerDetailModal' })
      expect(modal.props('modelValue')).toBe(true)
      expect(modal.props('vaultMarker')).toEqual({ id: 'vm-1' })
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
})
