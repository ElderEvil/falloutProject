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

  describe('Room Badges', () => {
    it('should display room badge for assigned dweller', async () => {
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
          room_id: 'room-1', // Assigned to Power Generator
          vault_id: 'vault-1'
        }
      ]

      const mockRooms = [
        {
          id: 'room-1',
          name: 'Power Generator',
          type: 'power',
          level: 1,
          position_x: 0,
          position_y: 0,
          vault_id: 'vault-1'
        }
      ]

      // Mock API responses
      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers }) // fetchDwellersByVault
        .mockResolvedValueOnce({ data: mockRooms }) // fetchRooms

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.html()).toContain('Power Generator')
      // Room badge should be present and clickable
      const roomBadge = wrapper.find('.room-badge')
      expect(roomBadge.exists()).toBe(true)
    })

    it('should display unassigned badge for dweller without room', async () => {
      const mockDwellers = [
        {
          id: 'dweller-2',
          first_name: 'Jane',
          last_name: 'Smith',
          level: 3,
          health: 100,
          max_health: 100,
          happiness: 70,
          status: 'idle',
          room_id: null, // No room assignment
          vault_id: 'vault-1'
        }
      ]

      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers })
        .mockResolvedValueOnce({ data: [] }) // no rooms

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.html()).toContain('Unassigned')
      // Unassigned badge should be present
      const unassignedBadge = wrapper.find('.room-badge')
      expect(unassignedBadge.exists()).toBe(true)
      expect(unassignedBadge.text()).toContain('Unassigned')
    })

    it('should show tooltip with room name on hover', async () => {
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
          room_id: 'room-2', // Assigned to Diner
          vault_id: 'vault-1'
        }
      ]

      const mockRooms = [
        {
          id: 'room-2',
          name: 'Diner',
          type: 'food',
          level: 1,
          position_x: 1,
          position_y: 0,
          vault_id: 'vault-1'
        }
      ]

      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers })
        .mockResolvedValueOnce({ data: mockRooms })

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      // UTooltip should have text prop
      const tooltips = wrapper.findAllComponents({ name: 'UTooltip' })
      const roomTooltip = tooltips.find(t => t.props('text')?.includes('Assigned to'))
      expect(roomTooltip).toBeDefined()
      expect(roomTooltip?.props('text')).toContain('Assigned to Diner')
    })

    it('should navigate to vault view when clicking room badge', async () => {
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
          room_id: 'room-1',
          vault_id: 'vault-1'
        }
      ]

      const mockRooms = [
        {
          id: 'room-1',
          name: 'Power Generator',
          type: 'power',
          level: 1,
          position_x: 0,
          position_y: 0,
          vault_id: 'vault-1'
        }
      ]

      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers })
        .mockResolvedValueOnce({ data: mockRooms })

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      // Find clickable room badge (not unassigned one)
      const roomBadges = wrapper.findAll('.room-badge')
      const clickableBadge = roomBadges.find(badge =>
        badge.html().includes('Power Generator')
      )

      expect(clickableBadge).toBeDefined()
      await clickableBadge!.trigger('click')
      await flushPromises()

      expect(router.currentRoute.value.path).toBe('/vault/vault-1')
    })
  })

  describe('Dweller List Display', () => {
    it('should display multiple dwellers with different room assignments', async () => {
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
          room_id: 'room-1',
          vault_id: 'vault-1'
        },
        {
          id: 'dweller-2',
          first_name: 'Jane',
          last_name: 'Smith',
          level: 3,
          health: 90,
          max_health: 100,
          happiness: 70,
          status: 'idle',
          room_id: null,
          vault_id: 'vault-1'
        }
      ]

      const mockRooms = [
        {
          id: 'room-1',
          name: 'Power Generator',
          type: 'power',
          level: 1,
          position_x: 0,
          position_y: 0,
          vault_id: 'vault-1'
        }
      ]

      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers })
        .mockResolvedValueOnce({ data: mockRooms })

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.text()).toContain('Jane Smith')
      expect(wrapper.html()).toContain('Power Generator')
      expect(wrapper.html()).toContain('Unassigned')
    })

    it('should display dweller basic stats', async () => {
      const mockDwellers = [
        {
          id: 'dweller-1',
          first_name: 'John',
          last_name: 'Doe',
          level: 7,
          health: 85,
          max_health: 100,
          happiness: 92,
          status: 'working',
          room_id: null,
          vault_id: 'vault-1'
        }
      ]

      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers })
        .mockResolvedValueOnce({ data: [] }) // no rooms

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Level: 7')
      expect(wrapper.text()).toContain('Health: 85 / 100')
      expect(wrapper.text()).toContain('Happiness: 92%')
    })
  })

  describe('Dweller Details Expansion', () => {
    it('should expand dweller details when clicking', async () => {
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

      const mockDetails = {
        id: 'dweller-1',
        first_name: 'John',
        last_name: 'Doe',
        bio: 'A brave vault dweller',
        S: 7,
        P: 5,
        E: 6,
        C: 4,
        I: 8,
        A: 6,
        L: 5
      }

      vi.mocked(axios.get)
        .mockResolvedValueOnce({ data: mockDwellers }) // fetchDwellersByVault
        .mockResolvedValueOnce({ data: [] }) // fetchRooms
        .mockResolvedValueOnce({ data: mockDetails }) // fetchDwellerDetails

      await router.isReady()
      const wrapper = mount(DwellersView, {
        global: {
          plugins: [router]
        }
      })
      await flushPromises()

      // Click the dweller card div to expand
      const dwellerCards = wrapper.findAll('li')
      const dwellerCard = dwellerCards[0]
      const clickableDiv = dwellerCard.find('.flex.w-full.items-center')
      await clickableDiv.trigger('click')
      await flushPromises()

      expect(wrapper.text()).toContain('A brave vault dweller')
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
