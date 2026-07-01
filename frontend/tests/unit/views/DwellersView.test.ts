import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DwellersView from '@/modules/dwellers/views/DwellersView.vue'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useVaultStore } from '@/modules/vault/stores/vault'
import { useRoomStore } from '@/modules/rooms/stores/room'
import * as http from '@/core/plugins/httpClient'

vi.mock('@/core/plugins/httpClient')

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
      vi.mocked(http.apiGet).mockResolvedValue([])

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
      vi.mocked(http.apiGet).mockResolvedValue([])

      await router.isReady()
      mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      // Should call fetchDwellersByVault with correct params
      expect(http.apiGet).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/dwellers/vault/vault-1'),
        expect.any(Object)
      )
    })

    it('should fetch rooms on mount', async () => {
      vi.mocked(http.apiGet).mockResolvedValue([])

      await router.isReady()
      mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      // Should fetch both dwellers and rooms (rooms may be called second)
      expect(http.apiGet).toHaveBeenCalled()
      const calls = (http.apiGet as ReturnType<typeof vi.fn>).mock.calls
      const roomCall = calls.find(
        (call: unknown[]) => typeof call[0] === 'string' && call[0].includes('/api/v1/rooms/vault/vault-1')
      )
      expect(roomCall).toBeTruthy()
    })
  })

  describe('Dweller Navigation', () => {
    it('should navigate to dweller detail page when clicking', async () => {
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

      vi.mocked(http.apiGet)
        .mockResolvedValueOnce(mockDwellers) // fetchDwellersByVault
        .mockResolvedValueOnce([]) // fetchRooms

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router, pinia],
        },
      })
      await flushPromises()

      // Click the dweller card to navigate
      const dwellerCards = wrapper.findAll('li')
      const dwellerCard = dwellerCards[0]
      await dwellerCard.trigger('click')
      await flushPromises()

      // Verify router navigation was called
      expect(router.currentRoute.value.name).toBe('dwellerDetail')
      expect(router.currentRoute.value.params.dwellerId).toBe('dweller-1')
    })
  })

  describe('Filter Panel Integration', () => {
    it('should render filter panel', async () => {
      vi.mocked(http.apiGet)
        .mockResolvedValueOnce([]) // fetchDwellersByVault
        .mockResolvedValueOnce([]) // fetchRooms

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
