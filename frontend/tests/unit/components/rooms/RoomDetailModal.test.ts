import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createIconifyMock, createRouterMock } from '../../helpers/mocks'
import { config, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import RoomDetailModal from '@/modules/rooms/components/RoomDetailModal.vue'
import { useDwellerStore } from '@/modules/dwellers/stores/dweller'
import { useRoomStore } from '@/modules/rooms/stores/room'
import { useArenaStore } from '@/modules/rooms/stores/arena'
import { useAuthStore } from '@/modules/auth/stores/auth'
import { useTrainingStore } from '@/modules/progression/stores/training'
import { useIncidentStore } from '@/modules/combat/stores/incident'
import axios from '@/core/plugins/axios'
import { audioManager } from '@/core/audio/audioManager'

// Mock @iconify/vue
vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<div class="mock-icon" :data-icon="icon"></div>' })
)

vi.mock('@/modules/rooms/components/BarbershopPanel.vue', () => ({
  default: {
    name: 'BarbershopPanel',
    props: ['room', 'assignedDwellers'],
    emits: ['changed'],
    template: '<div class="mock-barbershop-panel"></div>',
  },
}))

// The modal now composes shadcn primitives; stub them onto the same `mock-*`
// hooks this suite already selects on (`mock-modal`, `mock-button`, …) and keep
// Dialog/DialogContent context-free by stubbing both together.
config.global.stubs = {
  Dialog: { props: ['open'], template: '<div v-if="open" class="mock-modal"><slot /></div>' },
  DialogContent: { template: '<div><slot /></div>' },
  DialogHeader: { template: '<div><slot /></div>' },
  DialogTitle: { template: '<div><slot /></div>' },
  DialogDescription: { template: '<p><slot /></p>' },
  Button: {
    props: ['disabled'],
    template: '<button class="mock-button" :disabled="disabled"><slot /></button>',
  },
  Tooltip: { template: '<div class="mock-tooltip"><slot /></div>' },
  TooltipProvider: { template: '<div><slot /></div>' },
  TooltipTrigger: { template: '<div><slot /></div>' },
  TooltipContent: { template: '<div><slot /></div>' },
  Alert: { template: '<div class="mock-alert"><slot /></div>' },
}

const arenaToastError = vi.hoisted(() => vi.fn())

// Mock useToast
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({
    success: vi.fn(),
    error: arenaToastError,
    warning: vi.fn(),
    info: vi.fn(),
    show: vi.fn(),
    toasts: { value: [] },
    remove: vi.fn(),
  }),
}))

// Mock axios (balance endpoint serves the live production rate, like the backend)
vi.mock('@/core/plugins/axios', () => ({
  default: {
    get: vi.fn((url: string) => {
      if (url.includes('/arena/') && url.endsWith('/state')) {
        return Promise.resolve({
          data: {
            rooms: [
              {
                room_id: 'room-1',
                room_name: 'Arena',
                tier: 1,
                mode: 'duel',
                available_modes: ['duel'],
                fighter_a_id: null,
                fighter_b_id: null,
                fighters: [],
                team_a: [],
                team_b: [],
                roster: [],
                events: [],
                fight_ready: false,
                match_done: false,
                fight_started: false,
                countdown_remaining: 0,
                can_start: false,
                winner_name: null,
              },
            ],
          },
        })
      }
      if (url.includes('/arena/') && url.endsWith('/creatures')) {
        return Promise.resolve({ data: [] })
      }
      if (url.includes('/crafting/') && url.includes('/recipes/')) {
        return Promise.resolve({ data: { recipes: [] } })
      }
      if (url.includes('game/balance')) {
        return Promise.resolve({
          data: {
            resource: {
              base_production_rate: 0.0003,
              tier_1_multiplier: 1.0,
              tier_2_multiplier: 1.5,
              tier_3_multiplier: 2.0,
            },
          },
        })
      }
      if (url.endsWith('/rush')) {
        return Promise.resolve({
          data: {
            can_rush: true,
            blocked_reason: null,
            fail_chance: 10,
            success_chance: 90,
            stacks: 0,
            max_stacks: 6,
            avg_ability: 5,
            avg_luck: 5,
            worker_count: 1,
            payout: { power: 0, food: 0, water: 0, stimpack: 0, radaway: 0 },
            caps_chance: 25,
            eligible_incidents: ['fire'],
            next_stack_penalty: 10,
          },
        })
      }
      return Promise.resolve({ data: {} })
    }),
    post: vi.fn().mockResolvedValue({ data: {} }),
    put: vi.fn().mockResolvedValue({ data: {} }),
  },
}))

// Mock vue-router with shared mocks so we can spy on router.push
const { mockRouterPush } = vi.hoisted(() => ({ mockRouterPush: vi.fn() }))
vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-123' }, push: mockRouterPush }))

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
    room_style: 'default',
    vault_id: 'vault-123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  }

  it.each(['split', 'merge'])('runs the %s control through the room API', async (action) => {
    const room = { ...mockRoom, size: action === 'split' ? 6 : 3, incremental_cost: 25 }
    const store = useRoomStore()
    store.rooms = [room, { ...room, id: 'neighbor', size: 3, coordinate_x: room.size }]
    useAuthStore().token = 'token'
    const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: action === 'split' ? [room, { ...room, id: 'piece-2' }] : { ...room, size: 6 },
    })
    const wrapper = mount(RoomDetailModal, {
      props: { room, modelValue: true, vaultId: 'vault-123' },
    })
    const button = wrapper
      .findAll('button')
      .find((b) => b.text().includes(action === 'split' ? 'Split into' : 'Merge right'))!
    await button.trigger('click')
    await flushPromises()
    expect(nativeConfirm).not.toHaveBeenCalled()
    expect(axios.post).not.toHaveBeenCalled()
    await wrapper
      .findAll('button')
      .find((button) => button.text() === (action === 'split' ? 'Split room' : 'Merge rooms'))!
      .trigger('click')
    await flushPromises()
    expect(axios.post).toHaveBeenCalledWith(
      `/api/v1/rooms/${action}/room-1`,
      action === 'split' ? {} : { other_room_id: 'neighbor' }
    )
    expect(wrapper.emitted('roomUpdated')).toHaveLength(1)
    expect(wrapper.emitted('close')).toHaveLength(1)
    vi.mocked(window.confirm).mockRestore()
  })

  it('applies the Party theme through the room style API', async () => {
    const room = { ...mockRoom, name: 'Diner', room_style: 'default' }
    const store = useRoomStore()
    store.rooms = [room]
    useAuthStore().token = 'token'
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: { ...room, room_style: 'party', image_url: '/static/room_images/FOS Diner Party.png' },
    })

    const wrapper = mount(RoomDetailModal, {
      props: { room, modelValue: true, vaultId: 'vault-123' },
    })

    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.exists()).toBe(true)
    expect(wrapper.find('.preview-header [data-slot="select-trigger"]').exists()).toBe(true)
    expect(wrapper.find('.room-management [data-slot="select-trigger"]').exists()).toBe(false)
    select.vm.$emit('update:modelValue', 'party')
    await flushPromises()

    expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/style/room-1', {
      style: 'party',
    })
    expect(wrapper.emitted('roomUpdated')).toHaveLength(1)
  })

  it('names any active theme in the header', async () => {
    const room = { ...mockRoom, name: 'Diner', room_style: 'halloween', tier: 3 }

    const wrapper = mount(RoomDetailModal, {
      props: { room, modelValue: true, vaultId: 'vault-123' },
    })
    await flushPromises()

    expect(wrapper.find('.header-metadata').text()).toContain('Halloween theme')
  })

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
            readyActions: [],
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

    it('renders the Barbershop panel only for the Barbershop room', () => {
      const barbershop = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, name: 'Barbershop', category: 'misc.', ability: 'charisma' },
          modelValue: true,
          vaultId: 'vault-123',
        },
      })
      expect(barbershop.find('.mock-barbershop-panel').exists()).toBe(true)
      expect(barbershop.find('.room-preview-section').exists()).toBe(false)

      const other = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, name: 'Radio Studio', category: 'misc.', ability: 'charisma' },
          modelValue: true,
          vaultId: 'vault-123',
        },
      })
      expect(other.find('.mock-barbershop-panel').exists()).toBe(false)
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
      expect(wrapper.find('.room-preview-section .section-title').text()).toContain('Room Preview')
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
      const small = mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, size: 3, size_min: 3 },
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
      expect(small.find('.room-scene').classes()).toContain('room-scene--small')
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
      const fetchSpy = vi.spyOn(useTrainingStore(), 'fetchRoomTrainings').mockResolvedValue([
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
      expect(wrapper.text()).toContain('Strength')
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
    it('should show production stats for production rooms', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })
      await flushPromises()

      expect(wrapper.text()).toContain('Production Statistics')
      expect(wrapper.text()).toContain('Resource Type')
      expect(wrapper.text()).toContain('Power')
    })

    it('should calculate production rate correctly', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })
      await flushPromises()

      // Apprentices learn in a dedicated slot and do not contribute to production yet.
      // Rate comes live from /balance: output = 10, adult Strength = 9,
      // rate = 0.0003, tier1 = 1.0 → 0.027/sec, 1.62/min
      expect(wrapper.text()).toContain('Production Rate')
      expect(wrapper.text()).toContain('1.62')
    })

    it('should calculate efficiency correctly', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })
      await flushPromises()

      // Efficiency counts only normal workers; the apprentice has a dedicated slot.
      expect(wrapper.text()).toContain('Efficiency')
      expect(wrapper.text()).toContain('50%')
    })

    it('should show 100% efficiency when fully staffed', async () => {
      const dwellerStore = useDwellerStore().filter
      dwellerStore.dwellers = mockDwellers.map((dweller) => ({ ...dweller, apprentice_stat: null }))

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })
      await flushPromises()

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

    it('should show correct resource type for AGILITY (Food)', async () => {
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
      await flushPromises()

      expect(wrapper.text()).toContain('Food')
    })

    it('should show correct resource type for PERCEPTION (Water)', async () => {
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
      await flushPromises()

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
      expect(wrapper.find('.dweller-list-row').exists()).toBe(false)
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
        {
          ...mockDwellers[0],
          age_group: 'adult',
          apprentice_stat: null,
          room_id: null,
          status: 'idle',
        },
      ] as never

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: mockRoom,
          modelValue: true,
        },
      })

      await wrapper.get('.scene-empty-worker').trigger('click')

      const pickerCard = wrapper
        .findAll('.dweller-picker .dweller-list-row')
        .find((card) => card.text().includes('John'))
      expect(pickerCard).toBeTruthy()
      await pickerCard!.trigger('click')

      expect(assignSpy).toHaveBeenCalledWith('dweller-1', 'room-1', 'test-token')
    })

    it.each([false, true])(
      'starts a unified Arena lineup and retains it on rejection=%s',
      async (rejected) => {
        const { filter, management } = useDwellerStore()
        useAuthStore().token = 'test-token'
        const assign = vi.spyOn(management, 'assignDwellerToRoom').mockResolvedValue({} as never)
        filter.dwellers = [{ ...mockDwellers[1], age_group: 'child', room_id: null }] as never
        const wrapper = mount(RoomDetailModal, {
          props: {
            room: { ...mockRoom, name: 'Arena', category: 'ARENA', ability: null },
            vaultId: 'vault-123',
            modelValue: true,
          },
        })
        await flushPromises()
        const arena = useArenaStore()
        const candidates = ['Lucy', 'Maximus'].map((name, index) => ({
          id: `fighter-${index}`,
          name,
          level: 5,
          health: 80,
          max_health: 100,
          room_id: 'generator',
          room_name: 'Power Generator',
          age_group: 'adult',
        }))
        arena.rooms.set('room-1', { ...arena.getRoom('room-1')!, candidates })
        await flushPromises()
        for (const [index, side] of ['A', 'B'].entries()) {
          await wrapper
            .get(`button[aria-label="Select fighter 1 for Team ${side}"]`)
            .trigger('click')
          const picker = wrapper.get('[aria-label="Choose fighter"]')
          expect(picker.text()).toContain('Power Generator → Arena')
          await picker
            .findAll('button')
            .find((button) => button.text().includes(candidates[index].name))!
            .trigger('click')
        }
        expect(assign).not.toHaveBeenCalled()
        const post = vi.mocked(axios.post)
        if (rejected) post.mockRejectedValueOnce(new Error('Full'))
        await wrapper
          .findAll('button')
          .find((button) => button.text() === 'START FIGHT')!
          .trigger('click')
        await flushPromises()
        expect(post).toHaveBeenCalledWith(
          expect.stringContaining('/arena/vault/vault-123/rooms/room-1/start'),
          expect.objectContaining({
            fighter_a_id: 'fighter-0',
            fighter_b_id: 'fighter-1',
            mode: 'duel',
          })
        )
        expect(assign).not.toHaveBeenCalled()
        if (rejected) {
          expect(arenaToastError).toHaveBeenCalled()
          expect(wrapper.text()).toContain('Lucy')
          expect(wrapper.text()).toContain('Maximus')
          expect(
            wrapper
              .findAll('button')
              .find((button) => button.text() === 'START FIGHT')!
              .attributes('disabled')
          ).toBeUndefined()
        }
      }
    )

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
      expect(wrapper.findAll('.dweller-picker .dweller-list-row')).toHaveLength(1)
      await wrapper.get('.dweller-picker .dweller-list-row').trigger('click')

      expect(assignSpy).toHaveBeenCalledWith('dweller-1', 'room-1', 'test-token')
    })

    it('offers dwellers sorted by the room stat, best first', async () => {
      const { filter: dwellerStore } = useDwellerStore()
      dwellerStore.dwellers = [
        {
          ...mockDwellers[0],
          id: 'low-str',
          first_name: 'Lowbie',
          age_group: 'adult',
          apprentice_stat: null,
          room_id: null,
          status: 'idle',
          strength: 2,
        },
        {
          ...mockDwellers[1],
          id: 'high-str',
          first_name: 'Strong',
          age_group: 'adult',
          apprentice_stat: null,
          room_id: null,
          status: 'idle',
          strength: 10,
        },
      ] as never

      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })
      await wrapper.get('.scene-empty-worker').trigger('click')

      const cards = wrapper.findAll('.dweller-picker .dweller-list-row')
      expect(cards).toHaveLength(2)
      expect(cards[0].text()).toContain('Strong')
      expect(cards[0].get('.picker-room-stat').text()).toContain('Strength')
      expect(cards[0].get('.picker-room-stat').text()).toContain('10')
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
      expect(
        wrapper.findAll('.mock-button').some((button) => button.text().includes('Upgrade to Tier'))
      ).toBe(false)
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

    it('confirms unassign-all in a themed dialog and cancels without changing dwellers', async () => {
      const { filter, management } = useDwellerStore()
      filter.dwellers = mockDwellers
      useAuthStore().token = 'test-token'
      const unassign = vi
        .spyOn(management, 'unassignDwellerFromRoom')
        .mockResolvedValue({} as never)
      const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      const wrapper = mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true, vaultId: 'vault-123' },
      })
      const request = wrapper
        .findAll('button')
        .find((button) => button.text().includes('Unassign All Dwellers'))!
      await request.trigger('click')
      expect(nativeConfirm).not.toHaveBeenCalled()
      expect(unassign).not.toHaveBeenCalled()
      const confirmation = wrapper
        .findAllComponents({ name: 'TerminalConfirmation' })
        .find((dialog) => dialog.props('title') === 'Unassign dwellers?')!
      expect(confirmation.props('open')).toBe(true)
      expect(confirmation.text()).toContain('Unassign all 2 dwellers from this room?')
      await confirmation
        .findAll('button')
        .find((button) => button.text() === 'Cancel')!
        .trigger('click')
      expect(unassign).not.toHaveBeenCalled()
      await request.trigger('click')
      await confirmation
        .findAll('button')
        .find((button) => button.text() === 'Unassign all')!
        .trigger('click')
      await flushPromises()
      expect(unassign.mock.calls).toEqual([
        ['dweller-1', 'test-token'],
        ['dweller-2', 'test-token'],
      ])
      expect(wrapper.emitted('roomUpdated')).toHaveLength(1)
      expect(confirmation.props('open')).toBe(false)
      wrapper.unmount()
      nativeConfirm.mockRestore()
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
      const unassignSpy = vi
        .spyOn(dwellerManagementStore, 'unassignDwellerFromRoom')
        .mockResolvedValue({} as never)
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

      const upgradeButton = wrapper
        .findAll('.mock-button')
        .find((button) => button.text().includes('Upgrade to Tier'))!
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

      const upgradeButton = wrapper
        .findAll('.mock-button')
        .find((button) => button.text().includes('Upgrade to Tier'))!
      await upgradeButton.trigger('click')
      await wrapper.vm.$nextTick()
      await new Promise((resolve) => setTimeout(resolve, 0))

      expect(wrapper.text()).toContain('Insufficient caps')
    })
  })

  describe('Production Rate with Different Tiers', () => {
    it('should multiply production by 1.5 for tier 2', async () => {
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
      await flushPromises()

      // Rate comes live from /balance: 10 * 17 * 0.0003 * 1.5 = 0.0765/sec, 4.59/min
      expect(wrapper.text()).toContain('4.59')
    })

    it('should multiply production by 2.0 for tier 3', async () => {
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
      await flushPromises()

      // Rate comes live from /balance: 10 * 17 * 0.0003 * 2.0 = 0.102/sec, 6.12/min
      expect(wrapper.text()).toContain('6.12')
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
        query: { roomId: 'room-1', dweller: 'dweller-2' },
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
        query: { roomId: 'room-1', dweller: 'dweller-1' },
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

        const upgradeButton = wrapper
          .findAll('.mock-button')
          .find((button) => button.text().includes('Upgrade to Tier'))!
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
      expect(tooltip.text()).toContain('The Vault Door is vital and cannot be destroyed.')
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

  describe('Live incident overlay', () => {
    const room = {
      id: 'room-1',
      name: 'Power Generator',
      category: 'PRODUCTION',
      ability: 'STRENGTH',
      tier: 1,
      capacity: 4,
      size: 3,
      size_min: 3,
      size_max: 9,
    }

    const liveIncident = {
      id: 'incident-1',
      vault_id: 'vault-1',
      room_id: 'room-1',
      room_name: 'Power Generator',
      type: 'raider_attack',
      status: 'active',
      difficulty: 4,
      progress: { current: 30, target: 100, label: 'Threat' },
      risk: { kind: 'casualties', rooms_affected: 1 },
      family: 'intrusion',
      objective: 'defeat',
      response: { label: 'Send defenders' },
      events: [],
    }

    const seedIncident = () => {
      const incidentStore = useIncidentStore()
      incidentStore.incidents.set('incident-1', liveIncident as never)
      incidentStore.activeIncidentIds = ['incident-1']
    }

    it('replaces the generic sections with the incident overlay', () => {
      seedIncident()

      const wrapper = mount(RoomDetailModal, {
        props: { room: room as never, modelValue: true, vaultId: 'vault-1' },
      })

      expect(wrapper.text()).toContain('RAIDER ATTACK')
      expect(wrapper.text()).not.toContain('Unassign All Dwellers')
      expect(wrapper.text()).not.toContain('Destroy Room')
    })

    it('renders the generic sections when the incident is for another room', () => {
      seedIncident()

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...room, id: 'room-2' } as never,
          modelValue: true,
          vaultId: 'vault-1',
        },
      })

      expect(wrapper.text()).not.toContain('RAIDER ATTACK')
    })

    it('keeps arena precedence when an arena room has a live incident', () => {
      seedIncident()

      const wrapper = mount(RoomDetailModal, {
        props: {
          room: { ...room, name: 'Arena', category: 'ARENA' } as never,
          modelValue: true,
          vaultId: 'vault-1',
        },
      })

      expect(wrapper.text()).not.toContain('RAIDER ATTACK')
      expect(wrapper.text()).toContain('Arena')
    })

    it('replaces the generic sections with the aftermath once the incident is over', () => {
      const incidentStore = useIncidentStore()
      incidentStore.aftermaths.set('room-1', {
        incidentId: 'incident-1',
        roomId: 'room-1',
        type: 'raider_attack',
        roomName: 'Power Generator',
        outcome: 'defeat',
        capsEarned: 0,
        experienceEarned: 0,
        loot: null,
        enemiesDefeated: 2,
        damageDealt: 10,
        rounds: 4,
      })

      const wrapper = mount(RoomDetailModal, {
        props: { room: room as never, modelValue: true, vaultId: 'vault-1' },
      })

      expect(wrapper.text()).toContain('Incident lost')
      expect(wrapper.text()).not.toContain('Unassign All Dwellers')
      expect(wrapper.text()).not.toContain('Destroy Room')
    })

    it('prefers a live incident over a lingering aftermath', () => {
      seedIncident()
      const incidentStore = useIncidentStore()
      incidentStore.aftermaths.set('room-1', {
        incidentId: 'incident-0',
        roomId: 'room-1',
        type: 'fire',
        roomName: 'Power Generator',
        outcome: 'unknown',
        capsEarned: 0,
        experienceEarned: 0,
        loot: null,
        enemiesDefeated: 0,
        damageDealt: 0,
        rounds: 0,
      })

      const wrapper = mount(RoomDetailModal, {
        props: { room: room as never, modelValue: true, vaultId: 'vault-1' },
      })

      expect(wrapper.text()).toContain('RAIDER ATTACK')
      expect(wrapper.text()).not.toContain('INCIDENT ENDED')
    })

    it('keeps the incident scene through the final journal fetch and attack playback', async () => {
      vi.useFakeTimers()
      seedIncident()
      const store = useIncidentStore()
      const wrapper = mount(RoomDetailModal, {
        props: { room: room as never, modelValue: true, vaultId: 'vault-1' },
      })
      try {
        store.aftermaths.set('room-1', {
          incidentId: liveIncident.id,
          roomId: 'room-1',
          type: 'raider_attack',
          outcome: 'victory',
          capsEarned: 0,
          experienceEarned: 0,
          roomName: 'Generator',
          loot: null,
          unclaimed: [],
          enemiesDefeated: 8,
          damageDealt: 0,
          rounds: 1,
          scene: liveIncident,
          sceneLoading: true,
        } as never)
        store.activeIncidentIds = []
        await flushPromises()
        expect(wrapper.find('.incident-scene').exists()).toBe(true)
        const aftermath = store.aftermaths.get('room-1')!
        aftermath.scene = {
          ...liveIncident,
          status: 'resolved',
          events: [
            {
              id: 'last-hit',
              kind: 'hit',
              message: 'Final hit',
              data: null,
              action: { actor_id: 'd1', targets: [{ target_id: 'threat', damage: 1 }] },
            },
          ],
        } as never
        aftermath.sceneLoading = false
        await flushPromises()
        expect(wrapper.find('.incident-scene').exists()).toBe(true)
        await vi.advanceTimersByTimeAsync(350)
        expect(wrapper.find('.incident-scene').exists()).toBe(false)
        expect(wrapper.text()).toContain('Incident contained')
      } finally {
        wrapper.unmount()
        vi.useRealTimers()
      }
    })
  })

  describe('Ambience', () => {
    it('starts the per-room ambience for an initially-open modal', () => {
      const ambienceSpy = vi.spyOn(audioManager, 'playAmbience')
      mount(RoomDetailModal, {
        props: { room: mockRoom, modelValue: true },
      })

      expect(ambienceSpy).toHaveBeenCalledWith('power generator')
      ambienceSpy.mockRestore()
    })

    it('switches ambience between two rooms of the same category', async () => {
      const ambienceSpy = vi.spyOn(audioManager, 'playAmbience')
      const playSpy = vi.spyOn(audioManager, 'play')
      const wrapper = mount(RoomDetailModal, {
        props: { room: { ...mockRoom, name: 'Armory', category: 'TRAINING' }, modelValue: true },
      })
      expect(ambienceSpy).toHaveBeenCalledWith('armory')

      await wrapper.setProps({
        room: { ...mockRoom, id: 'room-2', name: 'Classroom', category: 'TRAINING' },
      })

      expect(ambienceSpy).toHaveBeenCalledWith('classroom')
      const modalOpenCalls = playSpy.mock.calls.filter(([key]) => key === 'modalOpen')
      expect(modalOpenCalls).toHaveLength(1)
      ambienceSpy.mockRestore()
      playSpy.mockRestore()
    })

    it('falls back to the category loop for a room with no per-room ambience', () => {
      const ambienceSpy = vi.spyOn(audioManager, 'playAmbience')
      mount(RoomDetailModal, {
        props: {
          room: { ...mockRoom, name: 'Broom Closet', category: 'TRAINING' },
          modelValue: true,
        },
      })

      expect(ambienceSpy).toHaveBeenCalledWith('training')
      ambienceSpy.mockRestore()
    })
  })
})

describe('Response Station surface', () => {
  const responseRoom = {
    id: 'station-1',
    name: 'Response Station',
    category: 'response',
    ability: 'endurance',
    tier: 1,
    capacity: null,
    output: null,
    size: 3,
    size_min: 3,
    size_max: 9,
    coordinate_x: 0,
    coordinate_y: 0,
    t2_upgrade_cost: null,
    t3_upgrade_cost: null,
    base_cost: 600,
    incremental_cost: null,
    population_required: 15,
    image_url: null,
    room_style: 'default',
    vault_id: 'vault-123',
    created_at: '2024-01-01T00:00:00Z',
    updated_at: '2024-01-01T00:00:00Z',
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'test-token'
  })

  it('renders the station management surface with standing actions', async () => {
    const wrapper = mount(RoomDetailModal, {
      props: { room: responseRoom as never, modelValue: true, vaultId: 'vault-123' },
    })
    await flushPromises()

    expect(wrapper.find('.response-station').exists()).toBe(true)
    expect(wrapper.text()).toContain('Station Management')
    expect(wrapper.text()).toContain('stationed')
    expect(wrapper.text()).toContain('Destroy Room')
    expect(wrapper.find('.header-metadata').text()).toContain('Capacity: 2')
  })

  it('omits the station surface for other room categories', () => {
    const wrapper = mount(RoomDetailModal, {
      props: {
        room: {
          ...responseRoom,
          id: 'room-1',
          name: 'Power Generator',
          category: 'production',
          ability: 'strength',
          capacity: 4,
        } as never,
        modelValue: true,
      },
    })

    expect(wrapper.find('.response-station').exists()).toBe(false)
  })
})
