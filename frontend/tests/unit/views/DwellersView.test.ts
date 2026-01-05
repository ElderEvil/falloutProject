import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import { createRouter, createMemoryHistory } from 'vue-router'
import DwellersView from '@/views/DwellersView.vue'
import { useAuthStore } from '@/stores/auth'
import { useDwellerStore } from '@/stores/dweller'
import { useVaultStore } from '@/stores/vault'
import { useRoomStore } from '@/stores/room'
import axios from '@/plugins/axios'

vi.mock('@/plugins/axios')

describe('DwellersView', () => {
  let router: any
  let authStore: any
  let dwellerStore: any
  let vaultStore: any
  let roomStore: any

  beforeEach(() => {
    setActivePinia(createPinia())

    // Set up auth store
    localStorage.setItem('token', 'test-token')
    localStorage.setItem('user', JSON.stringify({
      id: 'test-user-id',
      username: 'testuser',
      email: 'test@example.com'
    }))

    authStore = useAuthStore()
    dwellerStore = useDwellerStore()
    vaultStore = useVaultStore()
    roomStore = useRoomStore()

    // Mock vault
    vaultStore.loadedVaults['vault-1'] = {
      id: 'vault-1',
      number: 101,
      bottle_caps: 1000
    } as any

    router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/vault/:id/dwellers', component: DwellersView },
        { path: '/vault/:id/dwellers/:dwellerId', name: 'dwellerDetail', component: { template: '<div>Dweller Detail</div>' } },
        { path: '/vault/:id', component: { template: '<div>Vault View</div>' } },
        { path: '/dweller/:id/chat', component: { template: '<div>Chat</div>' } }
      ]
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
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Vault 101 Dwellers')
    })

    it('should fetch dwellers on mount', async () => {
      vi.mocked(axios.get).mockResolvedValue({ data: [] })

      await router.isReady()
      mount(DwellersView, {
        global: {
          plugins: [router]
        }
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
          plugins: [router]
        }
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
          vault_id: 'vault-1'
        }
      ]

      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers }) // fetchDwellersByVault
        .mockResolvedValueOnce({ data: [] }) // fetchRooms

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
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
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: [] }) // fetchDwellersByVault
        .mockResolvedValueOnce({ data: [] }) // fetchRooms

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      const filterPanel = wrapper.findComponent({ name: 'DwellerFilterPanel' })
      expect(filterPanel.exists()).toBe(true)
    })
  })
})
