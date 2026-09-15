import { describe, it, expect, beforeEach, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RoomDetailModal from '@/modules/rooms/components/RoomDetailModal.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useTrainingStore } from '@/modules/progression/stores/training'

// Mock @iconify/vue
vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<div class="mock-icon" :data-icon="icon"></div>',
  },
}))

// Mock UModal and UButton
vi.mock('@/core/components/ui/UModal.vue', () => ({
  default: {
    name: 'UModal',
    props: ['modelValue', 'size'],
    emits: ['update:modelValue', 'close'],
    template: `
      <div v-if="modelValue" class="mock-modal">
        <slot name="header" />
        <slot />
      </div>
    `,
    methods: {
      $emit: (event: string, payload?: any) => {
        // Mock emit method
        console.log('Emitting:', event, payload)
      },
    },
  },
}))

vi.mock('@/core/components/ui/UButton.vue', () => ({
  default: {
    name: 'UButton',
    props: ['disabled', 'variant'],
    template: '<button class="mock-button" :disabled="disabled"><slot /></button>',
  },
}))

vi.mock('@/core/components/ui/UTooltip.vue', () => ({
  default: {
    name: 'UTooltip',
    props: ['text'],
    template: '<div class="mock-tooltip" :data-tooltip="text"><slot /></div>',
  },
}))

vi.mock('@/core/components/ui/UAlert.vue', () => ({
  default: {
    name: 'UAlert',
    props: ['variant'],
    template: '<div class="mock-alert" :data-variant="variant"><slot /></div>',
  },
}))

// Mock useToast
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: vi.fn(),
    warning: vi.fn(),
    info: vi.fn(),
    show: vi.fn(),
    toasts: { value: [] },
    remove: vi.fn(),
  }),
}))

// Mock axios
vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn().mockResolvedValue({ data: {} }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

// Mock vue-router with shared mocks so we can spy on router.push
const mockRouterPush = vi.fn()
vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: { id: 'vault-123' },
  }),
  useRouter: () => ({
    push: mockRouterPush,
  }),
}))

describe('RoomDetailModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  const mockRoom = {
    id: 'room-1',
    name: 'Power Generator',
    category: 'PRODUCTION',
    ability: 'STRENGTH',
    tier: 1,
    capacity: 4,
    output: 10,
    size: 3,
    size_min: 3,
    size_max: 9,
    coordinate_x: 0,
    coordinate_y: 0,
    t2_upgrade_cost: 500,
    t3_upgrade_cost: 1500,
    base_cost: 100,
    incremental_cost: null,
    population_required: null,
    image_url: null,
    vault_id: 'vault-123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  }

  const mockDwellers = [
    {
      id: 'dweller-1',
      first_name: 'John',
      last_name: 'Doe',
      level: 5,
      strength: 8,
      perception: 5,
      endurance: 6,
      charisma: 4,
      intelligence: 7,
      agility: 5,
      luck: 6,
      room_id: 'room-1',
      vault_id: 'vault-123',
      status: 'working',
      age_group: 'child',
      apprentice_stat: 'strength',
    },
    {
      id: 'dweller-2',
      first_name: 'Jane',
      last_name: 'Smith',
      level: 7,
      strength: 9,
      perception: 6,
      endurance: 7,
      charisma: 5,
      intelligence: 6,
      agility: 7,
      luck: 5,
      room_id: 'room-1',
      vault_id: 'vault-123',
      status: 'working',
      age_group: 'teen',
    },
  ]

  describe('Rendering', () => {
    it('shows vault status only in the Overseer’s Office', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, name: "Overseer's Office", ability: null },
          modelValue: true,
          overseerBriefing: {
            vaultNumber: 42,
            activeIncidentCount: 1,
            activeExplorationCount: 2,
            trainingCount: 1,
            questingCount: 0,
            unassignedCount: 0,
            populationUtilization: 64,
            happiness: 82,
            resourceWarnings: [],
            dwellersPath: '/vault/vault-123/dwellers',
          },
        },
      })

      expect(wrapper.text()).toContain('VAULT STATUS')
      expect(wrapper.text()).toContain('1 INCIDENT REQUIRES RESPONSE')
    })

    it('should render when show is true', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.find('.mock-modal').exists()).toBe(true)
      expect(wrapper.text()).toContain('Power Generator')
    })

    it('should not render when show is false', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: false,
        },
      })

      expect(wrapper.find('.mock-modal').exists()).toBe(false)
    })

    it('should display room name and tier', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Power Generator')
      expect(wrapper.text()).toContain('Tier 1')
      expect(wrapper.find('.room-title').classes()).toContain('terminal-glow')
      expect(wrapper.find('.header-metadata').classes()).not.toContain('terminal-glow')
    })

    it('should display room category', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('PRODUCTION')
    })
  })

  describe('Room Information', () => {
    it('keeps staffing in the room scene instead of repeating it in a roster', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.find('.room-scene').exists()).toBe(true)
      expect(wrapper.find('.room-preview-section > .section-title').text()).toContain('Room Preview')
      expect(wrapper.findAll('.slot-filled')).toHaveLength(2)
      expect(wrapper.find('.staffing-summary').exists()).toBe(false)
      expect(wrapper.find('.header-metadata').text()).toContain('Capacity: 4')
    })

    it('scales the room scene for 1u and 6u+ footprints', () => {
      const compact = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, size: 1, size_min: 1 },
          modelValue: true,
        },
      })
      const wide = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, size: 9, size_min: 3 },
          modelValue: true,
        },
      })

      expect(compact.find('.room-scene').classes()).toContain('room-scene--compact')
      expect(wide.find('.room-scene').classes()).toContain('room-scene--wide')
    })

    it('renders one static slot with no assign action for elevators', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, name: 'Elevator', size: 1, size_min: 1 },
          modelValue: true,
        },
      })

      expect(wrapper.find('.room-scene').classes()).toContain('room-scene--compact')
      expect(wrapper.findAll('.dweller-sprite-slot')).toHaveLength(1)
      expect(wrapper.find('.scene-empty-worker').exists()).toBe(false)
      expect(wrapper.find('.scene-unassign').exists()).toBe(false)
    })

    it('should display room size', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Size')
      expect(wrapper.text()).toContain('1×')
      expect(wrapper.text()).not.toContain('merged')
    })

    it('should mark truly merged rooms', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, size: 6, size_min: 3 },
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('2× merged')
    })

    it('labels training rooms with Trains instead of Requires', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, name: 'Weight room', category: 'training', capacity: 0 },
          modelValue: true,
        },
      })

      expect(wrapper.find('.header-metadata').text()).toContain('Trains: S')
      expect(wrapper.find('.header-metadata').text()).not.toContain('Requires')
      expect(wrapper.find('.header-metadata').text()).toContain('Capacity: 2')
    })

    it('shows training progress with cancel and start actions for training rooms', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((dweller) => ({ ...dweller, status: 'training' }))
      useAuthStore().token = 'test-token'
      const fetchSpy = vi
        .spyOn(useTrainingStore(), 'fetchRoomTrainings')
        .mockResolvedValue([
          {
            id: 'training-1',
            dweller_id: 'dweller-2',
            stat_being_trained: 'strength',
            status: 'active',
            progress: 0.5,
            started_at: new Date(Date.now() - 60000).toISOString(),
            estimated_completion_at: new Date(Date.now() + 60000).toISOString(),
            current_stat_value: 9,
            target_stat_value: 10,
          },
        ] as never)

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, name: 'Weight room', category: 'training' },
          modelValue: true,
        },
      })
      await flushPromises()

      expect(fetchSpy).toHaveBeenCalledWith('room-1', 'test-token')
      expect(wrapper.text()).toContain('Training STRENGTH')
      expect(wrapper.text()).toContain('Jane Smith')
      expect(wrapper.text()).toContain('John Doe')
    })

    it('keeps training-status dwellers without an active record startable', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((dweller) => ({ ...dweller, status: 'training' }))
      useAuthStore().token = 'test-token'
      vi.spyOn(useTrainingStore(), 'fetchRoomTrainings').mockResolvedValue([] as never)

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, name: 'Weight room', category: 'training' },
          modelValue: true,
        },
      })
      await flushPromises()

      expect(wrapper.text()).toContain('John Doe')
      expect(wrapper.text()).toContain('Jane Smith')
      expect(wrapper.text()).toContain('No dwellers training right now')
    })

    it('reloads training records when switching training rooms', async () => {
      useAuthStore().token = 'test-token'
      const fetchSpy = vi
        .spyOn(useTrainingStore(), 'fetchRoomTrainings')
        .mockResolvedValue([] as never)

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, id: 'room-1', name: 'Weight room', category: 'training' },
          modelValue: true,
        },
      })
      await flushPromises()
      expect(fetchSpy).toHaveBeenCalledWith('room-1', 'test-token')

      await wrapper.setProps({
        room: { ...mockRoom, id: 'room-2', name: 'Athletics room', category: 'training' },
      })
      await flushPromises()
      expect(fetchSpy).toHaveBeenCalledWith('room-2', 'test-token')
    })

    it('should display room position', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Position')
      expect(wrapper.text()).toContain('(0, 0)')
    })

    it('should display the required room stat', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Requires: S')
    })
  })

  describe('Production Statistics', () => {
    it('should show production stats for production rooms', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Production Statistics')
      expect(wrapper.text()).toContain('Resource Type')
      expect(wrapper.text()).toContain('Power')
    })

    it('should calculate production rate correctly', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      // Apprentices learn in a dedicated slot and do not contribute to production yet.
      // output = 10, adult Strength = 9, BASE = 0.1, tier1 = 1.0 → 9/sec, 540/min
      expect(wrapper.text()).toContain('Production Rate')
      expect(wrapper.text()).toContain('540.00')
    })

    it('should calculate efficiency correctly', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      // Efficiency counts only normal workers; the apprentice has a dedicated slot.
      expect(wrapper.text()).toContain('Efficiency')
      expect(wrapper.text()).toContain('50%')
    })

    it('should show 100% efficiency when fully staffed', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((dweller) => ({ ...dweller, apprentice_stat: null }))

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('100%')
    })

    it('should not show production stats for non-production rooms', () => {
      const nonProductionRoom = {
        ...mockRoom,
        category: 'LIVING',
        ability: null,
      }

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: nonProductionRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).not.toContain('Production Statistics')
    })

    it('should show correct resource type for AGILITY (Food)', () => {
      const foodRoom = {
        ...mockRoom,
        ability: 'AGILITY',
      }

      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: foodRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Food')
    })

    it('should show correct resource type for PERCEPTION (Water)', () => {
      const waterRoom = {
        ...mockRoom,
        ability: 'PERCEPTION',
      }

      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: waterRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Water')
    })
  })

  describe('Assigned Dwellers', () => {
    it('renders assigned dwellers in their scene slots', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.find('[aria-label="Open John Doe"]').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Open Jane Smith"]').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Apprentice training strength"]').exists()).toBe(true)
      expect(wrapper.find('.apprentice-slot.slot-filled').exists()).toBe(true)
      expect(wrapper.findAll('.dweller-sprite-slot:not(.apprentice-slot)')).toHaveLength(2)
    })

    it('does not render a persistent staffing roster', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).not.toContain('Staffing')
      expect(wrapper.find('.dweller-card').exists()).toBe(false)
    })

    it('should show empty state when no dwellers assigned', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = []

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.find('.room-scene').exists()).toBe(true)
      expect(wrapper.findAll('.scene-empty-worker')).toHaveLength(2)
      expect(wrapper.findAll('[aria-label="Assign worker"]')).toHaveLength(2)
      expect(wrapper.find('.scene-empty-apprentice').exists()).toBe(true)
    })

    it('keeps empty worker slots able to show their hover feedback', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = []

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.get('.scene-empty-worker').classes()).toContain('scene-empty-slot')
    })

    it('keeps apprentice assignment exclusive to production rooms', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, category: 'SPECIAL', ability: 'CHARISMA', name: 'Radio Studio' },
          modelValue: true,
        },
      })

      expect(wrapper.find('.scene-empty-worker').exists()).toBe(true)
      expect(wrapper.find('.scene-empty-apprentice').exists()).toBe(false)
    })

    it('assigns a dweller picked from the inline picker', async () => {
      const { filter: dwellerStore, management: dwellerManagementStore } = useDwellerStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'
      const assignSpy = vi
        .spyOn(dwellerManagementStore, 'assignDwellerToRoom')
        .mockResolvedValue({} as never)
      dwellerStore.dwellers = [
        { ...mockDwellers[0], age_group: 'adult', apprentice_stat: null, room_id: null, status: 'idle' },
      ] as never

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      await wrapper.get('.scene-empty-worker').trigger('click')

      const pickerCard = wrapper
        .findAll('.dweller-picker .dweller-card')
        .find((card) => card.text().includes('John'))
      expect(pickerCard).toBeTruthy()
      await pickerCard!.get('.dweller-card__details').trigger('click')

      expect(assignSpy).toHaveBeenCalledWith('dweller-1', 'room-1', 'test-token')
    })

    it('assigns a youth through the dedicated apprentice action', async () => {
      const { filter: dwellerStore, management: dwellerManagementStore } = useDwellerStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'
      const assignSpy = vi
        .spyOn(dwellerManagementStore, 'assignDwellerToRoom')
        .mockResolvedValue({} as never)
      dwellerStore.dwellers = [
        { ...mockDwellers[0], room_id: null, status: 'idle' },
        { ...mockDwellers[1], age_group: 'adult', room_id: null, status: 'idle' },
      ] as never

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      await wrapper.get('.scene-empty-apprentice').trigger('click')
      expect(wrapper.find('.picker-title').text()).toBe('Select Apprentice')
      expect(wrapper.findAll('.dweller-picker .dweller-card')).toHaveLength(1)
      await wrapper.get('.dweller-picker .dweller-card__details').trigger('click')

      expect(assignSpy).toHaveBeenCalledWith('dweller-1', 'room-1', 'test-token')
    })

    it('keeps individual SPECIAL values out of the scene', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).not.toContain('Level 5')
      expect(wrapper.text()).not.toContain('Level 7')
    })
  })

  describe('Management Actions', () => {
    it('should show upgrade button when room can be upgraded', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Upgrade to Tier 2')
      expect(wrapper.text()).toContain('500 caps')
    })

    it('should show a quiet max-tier status instead of a disabled action', () => {
      const maxTierRoom = {
        ...mockRoom,
        tier: 3,
      }

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: maxTierRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Max tier reached')
      expect(wrapper.text()).toContain('(3/3)')
      expect(wrapper.findAll('.mock-button').some((button) => button.text().includes('Upgrade to Tier'))).toBe(false)
    })

    it('should omit upgrade controls for rooms without an upgrade path', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, category: 'SPECIAL', t2_upgrade_cost: null, t3_upgrade_cost: null },
          modelValue: true,
        },
      })

      expect(wrapper.text()).not.toContain('Max tier reached')
      expect(wrapper.text()).not.toContain('Upgrade to Tier')
    })

    it('should show tier 3 upgrade cost at tier 2', () => {
      const tier2Room = {
        ...mockRoom,
        tier: 2,
      }

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: tier2Room,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Upgrade to Tier 3')
      expect(wrapper.text()).toContain('1500 caps')
    })

    it('should show unassign all button', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Unassign All Dwellers')
    })

    it('groups room-wide controls under Management without restoring Staffing', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.find('.room-scene').exists()).toBe(true)
      expect(wrapper.find('.header-metadata').exists()).toBe(true)
      expect(wrapper.find('.room-management').text()).toContain('Management')
      expect(wrapper.text()).not.toContain('Staffing')
    })

    it('should expose an unassign control for every assigned dweller', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.findAll('.scene-unassign')).toHaveLength(mockDwellers.length)
      expect(wrapper.find('[aria-label="Unassign John Doe"]').exists()).toBe(true)
    })

    it('unassigns the selected dweller', async () => {
      const { filter: dwellerStore, management: dwellerManagementStore } = useDwellerStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'
      const unassignSpy = vi.spyOn(dwellerManagementStore, 'unassignDwellerFromRoom').mockResolvedValue({} as never)
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      await wrapper.get('[aria-label="Unassign John Doe"]').trigger('click')

      expect(unassignSpy).toHaveBeenCalledWith('dweller-1', 'test-token')
    })

    it('should show destroy room button', () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      expect(wrapper.text()).toContain('Destroy Room')
    })
  })

  describe('Events', () => {
    it('should emit close event when close button clicked', async () => {
      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      await wrapper.vm.$emit('close')
      expect(wrapper.emitted('close')).toBeTruthy()
    })

    it('should emit roomUpdated event after successful upgrade', async () => {
      const roomStore = useRoomStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'

      vi.spyOn(roomStore, 'upgradeRoom').mockResolvedValue()

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      const upgradeButton = wrapper.findAll('.mock-button')[0]
      await upgradeButton.trigger('click')
      await wrapper.vm.$nextTick()

      expect(wrapper.emitted('roomUpdated')).toBeTruthy()
    })
  })

  describe('Error Handling', () => {
    it('should display error message when action fails', async () => {
      const roomStore = useRoomStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'

      vi.spyOn(roomStore, 'upgradeRoom').mockRejectedValue(new Error('Insufficient caps'))

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      const upgradeButton = wrapper.findAll('.mock-button')[0]
      await upgradeButton.trigger('click')
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(wrapper.text()).toContain('Insufficient caps')
    })
  })

  describe('Production Rate with Different Tiers', () => {
    it('should multiply production by 1.5 for tier 2', () => {
      const tier2Room = {
        ...mockRoom,
        tier: 2,
      }

      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((dweller) => ({ ...dweller, apprentice_stat: null }))

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: tier2Room,
          modelValue: true,
        },
      })

      // Production: 10 * 17 * 0.1 * 1.5 = 25.5 per second, 1530 per minute
      expect(wrapper.text()).toContain('1530.00')
    })

    it('should multiply production by 2.0 for tier 3', () => {
      const tier3Room = {
        ...mockRoom,
        tier: 3,
      }

      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((dweller) => ({ ...dweller, apprentice_stat: null }))

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: tier3Room,
          modelValue: true,
        },
      })

      // Production: 10 * 17 * 0.1 * 2.0 = 34 per second, 2040 per minute
      expect(wrapper.text()).toContain('2040.00')
    })
  })

  describe('Radio Room UI and Mode Switching', () => {
    const mockRadioRoom = {
      ...mockRoom,
      name: 'Radio Studio',
      category: 'SPECIAL',
      ability: 'CHARISMA',
    }

    it('should show radio controls for radio rooms', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      expect(wrapper.text()).toContain('Radio Studio')
      expect(wrapper.text()).toContain('Broadcast Controls')
      expect(wrapper.find('.radio-controls').exists()).toBe(true)
      expect(wrapper.find('.modal-content > .radio-controls').exists()).toBe(true)
    })

    it('should not show radio controls for non-radio rooms', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      expect(wrapper.find('.radio-controls').exists()).toBe(false)
    })

    it('should render recruitment and happiness mode buttons', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      const modeButtons = wrapper.findAll('.mode-btn')
      expect(modeButtons.length).toBe(2)
      expect(modeButtons[0].text()).toContain('Recruitment')
      expect(modeButtons[1].text()).toContain('Happiness')
    })

    it('should show active state on recruitment mode by default', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      const modeButtons = wrapper.findAll('.mode-btn')
      expect(modeButtons[0].classes()).toContain('active')
      expect(modeButtons[1].classes()).not.toContain('active')
    })

    it('should display radio status text', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      expect(wrapper.text()).toContain('Recruiting')
    })

    it('should show staffing warning when no dwellers assigned to radio room', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = []

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      expect(wrapper.find('.mock-alert').exists()).toBe(true)
      expect(wrapper.text()).toContain('Assign at least one dweller')
    })
  })

  describe('Recruitment Button Enable/Disable States', () => {
    const mockRadioRoom = {
      ...mockRoom,
      name: 'Radio Studio',
      category: 'SPECIAL',
      ability: 'CHARISMA',
    }

    it('should disable recruit button when no dwellers assigned', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = []

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      const recruitBtn = wrapper.find('.recruit-btn')
      expect(recruitBtn.exists()).toBe(true)
      expect(recruitBtn.attributes('disabled')).toBeDefined()
    })

    it('should enable recruit button when dwellers assigned and in recruitment mode', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      const recruitBtn = wrapper.find('.recruit-btn')
      expect(recruitBtn.exists()).toBe(true)
      expect(recruitBtn.attributes('disabled')).toBeUndefined()
    })

    it('should show recruit cost in button text', () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((d) => ({
        ...d,
        room_id: mockRadioRoom.id,
      }))

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRadioRoom, modelValue: true },
      })

      expect(wrapper.text()).toContain('Recruit Dweller')
      expect(wrapper.text()).toContain('100 caps')
    })
  })

  describe('Dweller Click Navigation', () => {
    it('should open dweller details from an occupied scene slot', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      await wrapper.get('.scene-dweller').trigger('click')

      expect(mockRouterPush).toHaveBeenCalledWith({
        name: 'dwellerDetail',
        params: { id: 'vault-123', dwellerId: 'dweller-2' },
      })
    })

    it('opens the matching assignment picker from an empty scene slot', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = []

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      await wrapper.get('.scene-empty-worker').trigger('click')
      expect(wrapper.get('.picker-title').text()).toBe('Select Worker')

      await wrapper.get('.picker-close').trigger('click')
      await wrapper.get('.scene-empty-apprentice').trigger('click')
      expect(wrapper.get('.picker-title').text()).toBe('Select Apprentice')
    })

    it('opens apprentice details from the apprentice scene slot', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      await wrapper.get('.apprentice-slot .scene-dweller').trigger('click')

      expect(mockRouterPush).toHaveBeenCalledWith({
        name: 'dwellerDetail',
        params: { id: 'vault-123', dwellerId: 'dweller-1' },
      })
    })
  })

  describe('Error Clearing on Modal Close', () => {
    it('should clear error when modal closes', async () => {
      const roomStore = useRoomStore()
      const authStore = useAuthStore()
      authStore.token = 'test-token'

      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})

      vi.spyOn(roomStore, 'upgradeRoom').mockRejectedValue(new Error('Some error'))

      try {
        const wrapper = mount(RoomDetailModal, {
          props: { room: mockRoom, modelValue: true },
        })

        const upgradeButton = wrapper.findAll('.mock-button')[0]
        await upgradeButton.trigger('click')
        await wrapper.vm.$nextTick()
        await new Promise((resolve) => setTimeout(resolve, 0))

        expect(wrapper.text()).toContain('Some error')

        await wrapper.setProps({ modelValue: false })
        await wrapper.vm.$nextTick()

        await wrapper.setProps({ modelValue: true })
        await wrapper.vm.$nextTick()

        expect(wrapper.text()).not.toContain('Some error')
      } finally {
        consoleSpy.mockRestore()
      }
    })

    it('should not display error banner when no error exists', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      expect(wrapper.find('.error-banner').exists()).toBe(false)
    })
  })

  describe('Vault Door Edge Cases', () => {
    const mockVaultDoor = {
      ...mockRoom,
      name: 'Vault Door',
      category: 'SPECIAL',
      ability: null,
    }

    it('should show disabled destroy button for vault door', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockVaultDoor, modelValue: true },
      })

      expect(wrapper.text()).toContain('Destroy Room')

      const tooltip = wrapper.find('.mock-tooltip')
      expect(tooltip.exists()).toBe(true)
      expect(tooltip.attributes('data-tooltip')).toBe(
        'The Vault Door is vital and cannot be destroyed.'
      )
    })

    it('should wrap vault door destroy button in tooltip', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockVaultDoor, modelValue: true },
      })

      const tooltip = wrapper.find('.mock-tooltip')
      expect(tooltip.exists()).toBe(true)

      const destroyBtn = tooltip.find('.mock-button')
      expect(destroyBtn.exists()).toBe(true)
      expect(destroyBtn.attributes('disabled')).toBeDefined()
    })

    it('should enable destroy button for non-vault-door rooms', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      expect(wrapper.find('.mock-tooltip').exists()).toBe(false)

      const destroyButtons = wrapper.findAll('.mock-button').filter((btn) => {
        return btn.text().includes('Destroy Room')
      })
      expect(destroyButtons.length).toBe(1)
      expect(destroyButtons[0].attributes('disabled')).toBeUndefined()
    })

    it('should not show production stats for vault door', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockVaultDoor, modelValue: true },
      })

      expect(wrapper.text()).not.toContain('Production Statistics')
    })

    it('should not show required stat when ability is null', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockVaultDoor, modelValue: true },
      })

      expect(wrapper.text()).not.toContain('Required Stat')
    })
  })

  describe('Null Room Handling', () => {
    it('should not render modal content when room is null', () => {
      const wrapper = mount(RoomDetailModal, {
        props: { room: null, modelValue: true },
      })

      expect(wrapper.find('.modal-content').exists()).toBe(false)
    })
  })
})
