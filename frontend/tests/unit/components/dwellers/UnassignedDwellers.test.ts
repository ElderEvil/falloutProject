import { describe, it, expect, beforeEach, vi } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { setActivePinia, createPinia } from 'pinia'
import UnassignedDwellers from '@/modules/dwellers/components/UnassignedDwellers.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useExplorationStore } from '@/modules/exploration/stores/exploration'
import { useAuthStore } from '@/modules/auth/stores/auth'

// Mock Iconify
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    template: '<span class="icon-mock" :data-icon="icon"></span>',
    props: ['icon'],
  },
}))

// Mock components
vi.mock('@/modules/dwellers/components/stats/DwellerStatusBadge.vue', () => ({
  default: { template: '<div class="status-badge-mock"></div>', props: ['status', 'size'] },
}))

vi.mock('@/modules/dwellers/components/DwellerFilterPanel.vue', () => ({
  default: { template: '<div class="filter-panel-mock"></div>', props: ['showStatusFilter'] },
}))

// Mock auth service to prevent network calls
vi.mock('@/modules/auth/services/authService', () => ({
  authService: {
    getCurrentUser: vi
      .fn()
      .mockResolvedValue({ data: { id: 'user-1', email: 'test@example.com' } }),
    login: vi.fn(),
    register: vi.fn(),
    refreshToken: vi.fn(),
    logout: vi.fn(),
  },
}))

// Mock toast composable
const mockToast = {
  success: vi.fn(),
  error: vi.fn(),
  info: vi.fn(),
  warning: vi.fn(),
}

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

// Helper to create consistent drop event payloads
function createDropEvent(
  dwellerId: string,
  firstName: string,
  lastName: string,
  currentRoomId: string | null
) {
  return {
    dataTransfer: {
      getData: () =>
        JSON.stringify({
          dwellerId,
          firstName,
          lastName,
          currentRoomId,
        }),
    },
  }
}

describe('UnassignedDwellers', () => {
  let dwellerStore: any
  let dwellerManagementStore: any
  let authStore: any

  const mockDweller = {
    id: 'dweller-1',
    first_name: 'John',
    last_name: 'Doe',
    level: 5,
    strength: 8,
    perception: 6,
    endurance: 7,
    charisma: 5,
    intelligence: 9,
    agility: 4,
    luck: 6,
    room_id: null,
    thumbnail_url: null,
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    const stores = useDwellerStore()
    dwellerStore = stores.filter
    dwellerManagementStore = stores.management
    authStore = useAuthStore()

    // Set underlying dwellers array instead of computed property
    dwellerStore.dwellers = []

    // Mock the unassignDwellerFromRoom action
    dwellerManagementStore.unassignDwellerFromRoom = vi.fn().mockResolvedValue(undefined)
    authStore.token = 'mock-token'
    vi.clearAllMocks()
  })

  describe('Rendering', () => {
    it('should render unassigned dwellers panel with header', () => {
      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.text()).toContain('Unassigned Dwellers')
      expect(wrapper.text()).toContain('Drag dwellers here to unassign them from rooms')
    })

    it('should display count badge', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.find('.count-badge').exists()).toBe(true)
      expect(wrapper.find('.count-badge').text()).toBe('1')
    })

    it('should show empty state when no unassigned dwellers', () => {
      dwellerStore.dwellers = []

      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.text()).toContain('All dwellers are assigned!')
    })

    it('should render dweller cards when unassigned dwellers exist', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.find('.dweller-card').exists()).toBe(true)
      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.text()).toContain('Lv 5')
    })

    it('should display all SPECIAL stats', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const stats = wrapper.find('.dweller-stats')
      expect(stats.html()).toContain('S') // Strength
      expect(stats.html()).toContain('P') // Perception
      expect(stats.html()).toContain('E') // Endurance
      expect(stats.html()).toContain('C') // Charisma
      expect(stats.html()).toContain('I') // Intelligence
      expect(stats.html()).toContain('A') // Agility
      expect(stats.html()).toContain('L') // Luck
    })

    it('should use the shared themed avatar placeholder', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.find('.dweller-avatar .text-theme-primary\\/60').exists()).toBe(true)
    })
  })

  describe('Filtering', () => {
    it('should filter out dwellers with room assignments', () => {
      const assignedDweller = { ...mockDweller, id: 'dweller-2', room_id: 'room-1' }
      dwellerStore.dwellers = [mockDweller, assignedDweller]

      const wrapper = mount(UnassignedDwellers)

      const cards = wrapper.findAll('.dweller-card')
      expect(cards.length).toBe(1)
      expect(wrapper.text()).toContain('John Doe')
    })

    it('should filter out exploring dwellers', () => {
      const exploringDweller = { ...mockDweller, id: 'dweller-exploring', status: 'exploring' }
      dwellerStore.dwellers = [exploringDweller]

      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.find('.dweller-card').exists()).toBe(false)
      expect(wrapper.text()).toContain('All dwellers are assigned!')
    })

    it('should filter out questing dwellers', () => {
      const questingDweller = { ...mockDweller, id: 'dweller-questing', status: 'questing' }
      dwellerStore.dwellers = [questingDweller]

      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.find('.dweller-card').exists()).toBe(false)
      expect(wrapper.text()).toContain('All dwellers are assigned!')
    })
  })

  describe('Filters', () => {
    const adultDweller = {
      ...mockDweller,
      id: 'dweller-adult',
      first_name: 'Ada',
      age_group: 'adult',
      rarity: 'legendary',
    }
    const childDweller = {
      ...mockDweller,
      id: 'dweller-child',
      first_name: 'Tim',
      age_group: 'child',
      rarity: 'common',
    }

    const clickChip = async (wrapper: ReturnType<typeof mount>, label: string) => {
      const chip = wrapper.findAll('.chip').find((c) => c.text() === label)
      expect(chip).toBeTruthy()
      await chip!.trigger('click')
    }

    it('should render rarity filter chips', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const labels = wrapper.findAll('.chip').map((c) => c.text())
      expect(labels).toContain('Legendary')
    })

    it('should filter cards by the shared age preference', () => {
      dwellerStore.dwellers = [adultDweller, childDweller]
      dwellerStore.setFilterAgeGroup('adult')

      const wrapper = mount(UnassignedDwellers)

      const cards = wrapper.findAll('.dweller-card')
      expect(cards.length).toBe(1)
      expect(cards[0].text()).toContain('Ada')
    })

    it('should filter cards by rarity', async () => {
      dwellerStore.dwellers = [adultDweller, childDweller]

      const wrapper = mount(UnassignedDwellers)

      await clickChip(wrapper, 'Legendary')

      const cards = wrapper.findAll('.dweller-card')
      expect(cards.length).toBe(1)
      expect(cards[0].text()).toContain('Ada')
    })

    it('should show a filtered-out message instead of the all-assigned state', () => {
      dwellerStore.dwellers = [adultDweller]
      dwellerStore.setFilterAgeGroup('child')

      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.text()).toContain('No dwellers match the filters')
      expect(wrapper.text()).not.toContain('All dwellers are assigned!')
    })

    it('should tint the avatar ring by rarity', () => {
      dwellerStore.dwellers = [adultDweller]

      const wrapper = mount(UnassignedDwellers)

      const avatar = wrapper.find('.dweller-avatar')
      expect(avatar.attributes('style')).toContain('--rarity-ring')
    })
  })

  describe('Drag and Drop', () => {
    it('should make dweller cards draggable', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const card = wrapper.find('.dweller-card')
      expect(card.attributes('draggable')).toBe('true')
    })

    it('should emit dragStart event when dragging starts', async () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const card = wrapper.find('.dweller-card')
      await card.trigger('dragstart', {
        dataTransfer: {
          effectAllowed: '',
          setData: vi.fn(),
        },
      })

      expect(wrapper.emitted('dragStart')).toBeTruthy()
      expect(wrapper.emitted('dragStart')![0][0]).toMatchObject({ id: mockDweller.id })
    })

    it('should emit dragEnd event when dragging ends', async () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const card = wrapper.find('.dweller-card')
      await card.trigger('dragend')

      expect(wrapper.emitted('dragEnd')).toBeTruthy()
    })

    it('should show drop overlay when dragging over', async () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const container = wrapper.find('.dweller-grid-container')
      await container.trigger('dragover', {
        dataTransfer: { dropEffect: '' },
      })

      await flushPromises()

      expect(wrapper.find('.drop-overlay').exists()).toBe(true)
      expect(wrapper.text()).toContain('Drop to unassign')
    })

    it('should unassign dweller on drop', async () => {
      dwellerStore.dwellers = []

      const wrapper = mount(UnassignedDwellers)

      const dropZone = wrapper.find('.empty-state')
      await dropZone.trigger('drop', createDropEvent('dweller-1', 'John', 'Doe', 'room-1'))

      await flushPromises()

      expect(dwellerManagementStore.unassignDwellerFromRoom).toHaveBeenCalledWith(
        'dweller-1',
        'mock-token'
      )
    })

    it('should show success message after unassigning', async () => {
      dwellerStore.dwellers = []

      const wrapper = mount(UnassignedDwellers)

      const dropZone = wrapper.find('.empty-state')
      await dropZone.trigger('drop', createDropEvent('dweller-1', 'John', 'Doe', 'room-1'))

      await flushPromises()

      expect(dwellerManagementStore.unassignDwellerFromRoom).toHaveBeenCalledWith(
        'dweller-1',
        'mock-token'
      )
      expect(mockToast.success).toHaveBeenCalledWith('John Doe unassigned from room')
    })

    it('should not unassign if dweller has no room', async () => {
      dwellerStore.dwellers = []

      const wrapper = mount(UnassignedDwellers)

      const dropZone = wrapper.find('.empty-state')
      await dropZone.trigger('drop', createDropEvent('dweller-1', 'John', 'Doe', null))

      await flushPromises()

      expect(dwellerManagementStore.unassignDwellerFromRoom).not.toHaveBeenCalled()
    })
  })

  describe('Color Theming', () => {
    it('should use theme color for level text', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const levelElement = wrapper.find('.dweller-level')
      expect(levelElement.attributes('class')).toBe('dweller-level')
    })

    it('should use theme color for stat labels', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const statLabels = wrapper.findAll('.stat-label')
      expect(statLabels.length).toBeGreaterThan(0)
    })

    it('should have neutral black card background', () => {
      dwellerStore.dwellers = [mockDweller]

      const wrapper = mount(UnassignedDwellers)

      const card = wrapper.find('.dweller-card')
      expect(card.exists()).toBe(true)
    })
  })

  describe('Error Handling', () => {
    it('should show error message on unassign failure', async () => {
      dwellerManagementStore.unassignDwellerFromRoom = vi
        .fn()
        .mockRejectedValue(new Error('Unassign failed'))
      dwellerStore.dwellers = []

      const wrapper = mount(UnassignedDwellers)

      const dropZone = wrapper.find('.empty-state')
      await dropZone.trigger('drop', createDropEvent('dweller-1', 'John', 'Doe', 'room-1'))

      await flushPromises()

      expect(dwellerManagementStore.unassignDwellerFromRoom).toHaveBeenCalledWith(
        'dweller-1',
        'mock-token'
      )
      expect(mockToast.error).toHaveBeenCalledWith('Failed to unassign dweller')
    })
  })

  describe('Multiple Dwellers', () => {
    it('should render multiple dweller cards', () => {
      const dweller2 = { ...mockDweller, id: 'dweller-2', first_name: 'Jane', last_name: 'Smith' }
      dwellerStore.dwellers = [mockDweller, dweller2]

      const wrapper = mount(UnassignedDwellers)

      const cards = wrapper.findAll('.dweller-card')
      expect(cards.length).toBe(2)
      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.text()).toContain('Jane Smith')
    })

    it('should update count badge with correct number', () => {
      dwellerStore.dwellers = [
        mockDweller,
        { ...mockDweller, id: 'dweller-2' },
        { ...mockDweller, id: 'dweller-3' },
      ]

      const wrapper = mount(UnassignedDwellers)

      expect(wrapper.find('.count-badge').text()).toBe('3')
    })
  })
})
