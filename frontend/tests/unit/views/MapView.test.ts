import { describe, it, expect, beforeEach, vi } from 'vitest'
import { reactive } from 'vue'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import MapView from '@/modules/map/views/MapView.vue'
import { useMapStore } from '@/modules/map/stores/map'

vi.mock('@/modules/map/services/mapService', () => ({
  getVaultMap: vi.fn().mockResolvedValue({ locations: [], vault_markers: [] }),
  getLocationDetail: vi.fn(),
}))

const mockPush = vi.fn()

// Reactive route mock so tests can mutate route.query.place after mount and
// exercise the `watch(() => route.query.place, ...)` in MapView.vue.
const mockRoute = reactive({
  params: { id: 'vault-1' },
  query: {} as Record<string, string>,
})

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  useRouter: () => ({ push: mockPush }),
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

  beforeEach(() => {
    localStorage.setItem('token', 'test-token')
    localStorage.setItem(
      'user',
      JSON.stringify({ id: 'u1', username: 'test', email: 'test@test.com' })
    )
    setActivePinia(createPinia())
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
            template: '<div class="world-map-stub"></div>',
            props: ['locations', 'vaultMarkers'],
          },
          MarkerDetailModal: {
            name: 'MarkerDetailModal',
            template: '<div class="modal-stub"></div>',
            props: ['modelValue', 'location', 'vaultMarker'],
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
  })
})
