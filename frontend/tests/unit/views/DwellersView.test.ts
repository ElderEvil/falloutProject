import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DwellersView from '@/modules/dwellers/views/DwellersView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import axios from '@/core/plugins/axios'

vi.mock('@/core/plugins/axios')

describe('DwellersView', () => {
  let router: any
  let _authStore: any
  let _dwellerStore: any
  let vaultStore: any
  let _roomStore: any
  let pinia: ReturnType<typeof createPinia>

  beforeEach(() => {
    pinia = createPinia()
    setActivePinia(pinia)

    // Set up auth store
    localStorage.setItem('token', 'test-token')
    localStorage.setItem(
      'user',
      JSON.stringify({
        id: 'test-user-id',
        username: 'testuser',
        email: 'test@example.com',
      })
    )

    _authStore = useAuthStore()
    _dwellerStore = useDwellerStore()
    vaultStore = useVaultStore()
    _roomStore = useRoomStore()

    // Mock vault
    vaultStore.loadedVaults['vault-1'] = {
      id: 'vault-1',
      number: 101,
      bottle_caps: 1000,
    } as any

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/vault/:id/dwellers', component: DwellersView },
        {
          path: '/vault/:id/dwellers/:dwellerId',
          name: 'dwellerDetail',
          component: { template: '<div>Dweller Detail</div>' },
        },
        { path: '/vault/:id', component: { template: '<div>Vault View</div>' } },
        { path: '/dweller/:id/chat', component: { template: '<div>Chat</div>' } },
      ],
    })

    router.push('/vault/vault-1/dwellers')

    vi.spyOn(console, 'error').mockImplementation(() => {})
    vi.clearAllMocks()
  })

  describe('Initialization', () => {
    it('should render vault title', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Dwellers')
    })

    it('should fetch dwellers on mount', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })

      await router.isReady()
      mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      // Should call fetchDwellersByVault with correct params
      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/dwellers/vault/vault-1'),
        expect.any(Object)
      )
    })

    it('should fetch rooms on mount', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })

      await router.isReady()
      mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      // Should fetch both dwellers and rooms
      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/rooms/vault/vault-1'),
        expect.any(Object)
      )
    })
  })

  describe('Dweller Navigation', () => {
    it('navigates to the full-page detail route when clicking a dweller', async () => {
      const mockDwellers = [
        {
          id: 'dweller-1',
          first_name: 'John',
          last_name: 'Doe',
          level: 5,
          health: 100,
          max_health: 100,
          happiness: 80,
          status: 'working',
          room_id: null,
          vault_id: 'vault-1',
        },
      ]

      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers }) // fetchDwellersByVault
        .mockResolvedValueOnce({ data: [] }) // fetchAllDwellers
        .mockResolvedValueOnce({ data: [] }) // fetchRooms
        .mockResolvedValueOnce({ data: { vault_id: 'vault-1', incident_count: 0, incidents: [] } }) // fetchIncidents

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      const dwellerCard = wrapper.findAll('li')[0]
      await dwellerCard.trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.name).toBe('dwellerDetail')
      expect(router.currentRoute.value.params.dwellerId).toBe('dweller-1')
    })
  })

  describe('Filter Panel Integration', () => {
    it('applies the Socializing query filter', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })
      await router.push('/vault/vault-1/dwellers?filter=resting')
      await router.isReady()

      mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('status=resting'),
        expect.any(Object)
      )
    })

    it('applies the Fighting query filter', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })
      await router.push('/vault/vault-1/dwellers?filter=fighting')
      await router.isReady()

      mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      expect(axios.get).toHaveBeenCalledWith(
        expect.stringContaining('status=fighting'),
        expect.any(Object)
      )
    })

    it('should render filter panel', async () => {
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: [] }) // fetchDwellersByVault
        .mockResolvedValueOnce({ data: [] }) // fetchAllDwellers
        .mockResolvedValueOnce({ data: [] }) // fetchRooms
        .mockResolvedValueOnce({ data: { vault_id: 'vault-1', incident_count: 0, incidents: [] } }) // fetchIncidents

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      const filterPanel = wrapper.findComponent({ name: 'DwellerFilterPanel' })
      expect(filterPanel.exists()).toBe(true)
    })
  })
})
