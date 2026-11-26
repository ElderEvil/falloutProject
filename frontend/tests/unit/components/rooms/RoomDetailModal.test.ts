import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createIconifyMock, createRouterMock } from '../../helpers/mocks'
import { config, flushPromises, mount, type VueWrapper } from '@vue/test-utils'
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

// The modal composes shadcn primitives; stub them onto the same `mock-*` hooks
// this suite selects on and keep Dialog/DialogContent context-free.
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

// Balance, arena state and rush all serve live numbers, like the backend.
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
      if (url.includes('/arena/') && url.endsWith('/creatures'))
        return Promise.resolve({ data: [] })
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

const { mockRouterPush } = vi.hoisted(() => ({ mockRouterPush: vi.fn() }))
vi.mock('vue-router', () => createRouterMock({ params: { id: 'vault-123' }, push: mockRouterPush }))

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

const workersOnly = mockDwellers.map((dweller) => ({ ...dweller, apprentice_stat: null }))
const radioRoom = { ...mockRoom, name: 'Radio Studio', category: 'SPECIAL', ability: 'CHARISMA' }
const vaultDoor = { ...mockRoom, name: 'Vault Door', category: 'SPECIAL', ability: null }

/** An unassigned adult the room's picker may offer. */
const idleAdult = (
  overrides: Record<string, unknown> = {},
  base: Record<string, unknown> = mockDwellers[0]
) => ({
  ...base,
  age_group: 'adult',
  apprentice_stat: null,
  room_id: null,
  status: 'idle',
  ...overrides,
})

const seedDwellers = (dwellers: unknown[] = mockDwellers, extra: Record<string, unknown> = {}) => {
  const filter = useDwellerStore().filter
  filter.dwellers = dwellers as never
  Object.assign(filter, extra)
  return filter
}

const mountRoom = (
  room: Record<string, unknown> | null = {},
  props: Record<string, unknown> = {}
): VueWrapper =>
  mount(RoomDetailModal, {
    props: {
      room: room === null ? null : { ...mockRoom, ...room },
      modelValue: true,
      // The theme loader needs a real vault id; without it the mount requests /crafting/vault/undefined.
      vaultId: 'vault-123',
      ...props,
    },
  })

const button = (wrapper: VueWrapper, text: string) =>
  wrapper.findAll('button').find((candidate) => candidate.text().includes(text))

const click = async (wrapper: VueWrapper, text: string) => {
  await button(wrapper, text)!.trigger('click')
  await flushPromises()
}

const assignSpy = () =>
  vi.spyOn(useDwellerStore().management, 'assignDwellerToRoom').mockResolvedValue({} as never)

describe('RoomDetailModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it.each(['split', 'merge'])('runs the %s control through the room API', async (action) => {
    const room = { ...mockRoom, size: action === 'split' ? 6 : 3, incremental_cost: 25 }
    const store = useRoomStore()
    store.rooms = [room, { ...room, id: 'neighbor', size: 3, coordinate_x: room.size }]
    useAuthStore().token = 'token'
    const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: action === 'split' ? [room, { ...room, id: 'piece-2' }] : { ...room, size: 6 },
    })
    const wrapper = mountRoom(room)

    await click(wrapper, action === 'split' ? 'Split into' : 'Merge right')
    expect(nativeConfirm).not.toHaveBeenCalled()
    expect(axios.post).not.toHaveBeenCalled()

    await click(wrapper, action === 'split' ? 'Split room' : 'Merge rooms')
    expect(axios.post).toHaveBeenCalledWith(
      `/api/v1/rooms/${action}/room-1`,
      action === 'split' ? {} : { other_room_id: 'neighbor' }
    )
    expect(wrapper.emitted('roomUpdated')).toHaveLength(1)
    expect(wrapper.emitted('close')).toHaveLength(1)
    nativeConfirm.mockRestore()
  })

  it('applies the Party theme through the room style API', async () => {
    const room = { ...mockRoom, name: 'Diner', room_style: 'default' }
    useRoomStore().rooms = [room]
    useAuthStore().token = 'token'
    vi.mocked(axios.post).mockResolvedValueOnce({
      data: { ...room, room_style: 'party', image_url: '/static/room_images/FOS Diner Party.png' },
    })
    const wrapper = mountRoom(room)

    const select = wrapper.findComponent({ name: 'Select' })
    expect(select.exists()).toBe(true)
    select.vm.$emit('update:modelValue', 'party')
    await flushPromises()

    expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/style/room-1', { style: 'party' })
    expect(wrapper.emitted('roomUpdated')).toHaveLength(1)
  })

  it('names any active theme in the header', async () => {
    const wrapper = mountRoom({ name: 'Diner', room_style: 'halloween', tier: 3 })
    await flushPromises()

    expect(wrapper.find('.header-metadata').text()).toContain('Halloween theme')
  })

  describe('Rendering', () => {
    it('shows vault status only in the Overseer’s Office', () => {
      const wrapper = mountRoom(
        { name: "Overseer's Office", ability: null },
        {
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
        }
      )

      expect(wrapper.text()).toContain('VAULT STATUS')
      expect(wrapper.text()).toContain('1 INCIDENT REQUIRES RESPONSE')
    })

    it.each([true, false])('renders the dialog body only while open=%s', (open) => {
      const wrapper = mountRoom({}, { modelValue: open })

      expect(wrapper.find('.mock-modal').exists()).toBe(open)
      if (!open) return
      expect(wrapper.text()).toContain('Power Generator')
      expect(wrapper.text()).toContain('Tier 1')
      expect(wrapper.text()).toContain('PRODUCTION')
    })

    it('renders the Barbershop panel only for the Barbershop room', () => {
      const barbershop = mountRoom({ name: 'Barbershop', category: 'misc.', ability: 'charisma' })
      expect(barbershop.find('.mock-barbershop-panel').exists()).toBe(true)
      expect(barbershop.find('.room-preview-section').exists()).toBe(false)

      const other = mountRoom({ name: 'Radio Studio', category: 'misc.', ability: 'charisma' })
      expect(other.find('.mock-barbershop-panel').exists()).toBe(false)
    })
  })

  describe('Room Information', () => {
    it('keeps staffing in the room scene instead of repeating it in a roster', () => {
      seedDwellers()

      const wrapper = mountRoom()

      expect(wrapper.find('.room-scene').exists()).toBe(true)
      expect(wrapper.find('.room-preview-section .section-title').text()).toContain('Room Preview')
      expect(wrapper.findAll('.slot-filled')).toHaveLength(2)
      expect(wrapper.find('.staffing-summary').exists()).toBe(false)
      expect(wrapper.find('.header-metadata').text()).toContain('Capacity: 4')
    })

    it.each([
      [1, 1, 'room-scene--compact'],
      [3, 3, 'room-scene--small'],
      [9, 3, 'room-scene--wide'],
    ])('scales the room scene for a %iu footprint', (size, sizeMin, sceneClass) => {
      const wrapper = mountRoom({ size, size_min: sizeMin })

      expect(wrapper.find('.room-scene').classes()).toContain(sceneClass)
    })

    it('renders one static slot with no assign action for elevators', () => {
      const wrapper = mountRoom({ name: 'Elevator', size: 1, size_min: 1 })

      expect(wrapper.find('.room-scene').classes()).toContain('room-scene--compact')
      expect(wrapper.findAll('.dweller-sprite-slot')).toHaveLength(1)
      expect(wrapper.find('.scene-empty-worker').exists()).toBe(false)
      expect(wrapper.find('.scene-unassign').exists()).toBe(false)
    })

    it.each([
      [3, ['1×'], false],
      [6, ['2× merged'], true],
    ])('describes a %iu room footprint', (size, expected, merged) => {
      const text = mountRoom({ size, size_min: 3 }).text()

      expected.forEach((fragment) => expect(text).toContain(fragment))
      if (!merged) expect(text).not.toContain('merged')
    })

    it('labels training rooms with Trains instead of Requires', () => {
      const wrapper = mountRoom({ name: 'Weight room', category: 'training', capacity: 0 })
      const header = wrapper.find('.header-metadata').text()

      expect(header).toContain('Trains: S')
      expect(header).not.toContain('Requires')
      expect(header).toContain('Capacity: 2')
    })

    it('shows training progress with cancel and start actions for training rooms', async () => {
      seedDwellers(mockDwellers.map((dweller) => ({ ...dweller, status: 'training' })))
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

      const wrapper = mountRoom({ name: 'Weight room', category: 'training' })
      await flushPromises()

      expect(fetchSpy).toHaveBeenCalledWith('room-1')
      expect(wrapper.text()).toContain('Strength')
      expect(wrapper.text()).toContain('Jane Smith')
      expect(wrapper.text()).toContain('John Doe')
    })

    it('keeps training-status dwellers without an active record startable', async () => {
      seedDwellers(mockDwellers.map((dweller) => ({ ...dweller, status: 'training' })))
      useAuthStore().token = 'test-token'
      vi.spyOn(useTrainingStore(), 'fetchRoomTrainings').mockResolvedValue([] as never)

      const wrapper = mountRoom({ name: 'Weight room', category: 'training' })
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

      const wrapper = mountRoom({ name: 'Weight room', category: 'training' })
      await flushPromises()
      expect(fetchSpy).toHaveBeenCalledWith('room-1')

      await wrapper.setProps({
        room: { ...mockRoom, id: 'room-2', name: 'Athletics room', category: 'training' },
      })
      await flushPromises()
      expect(fetchSpy).toHaveBeenCalledWith('room-2')
    })

    it('shows the room position and required stat', () => {
      const text = mountRoom().text()

      expect(text).toContain('Position')
      expect(text).toContain('(0, 0)')
      expect(text).toContain('Requires: S')
    })
  })

  describe('Production Statistics', () => {
    it('shows production stats for production rooms', async () => {
      seedDwellers()

      const wrapper = mountRoom()
      await flushPromises()

      expect(wrapper.text()).toContain('Production Statistics')
      expect(wrapper.text()).toContain('Resource Type')
      expect(wrapper.text()).toContain('Power')
    })

    // Rate comes live from /balance: output 10 × room stat × 0.0003 × tier
    // multiplier. Apprentices learn in their own slot and add no production.
    it.each([
      [1, mockDwellers, '1.62'],
      [2, workersOnly, '4.59'],
      [3, workersOnly, '6.12'],
    ])('applies the tier %i production multiplier', async (tier, dwellers, expected) => {
      seedDwellers(dwellers)

      const wrapper = mountRoom({ tier })
      await flushPromises()

      expect(wrapper.text()).toContain('Production Rate')
      expect(wrapper.text()).toContain(expected)
    })

    it.each([
      [mockDwellers, '50%'],
      [workersOnly, '100%'],
    ])('reports efficiency from the working crew only (%#)', async (dwellers, expected) => {
      seedDwellers(dwellers)

      const wrapper = mountRoom()
      await flushPromises()

      expect(wrapper.text()).toContain('Efficiency')
      expect(wrapper.text()).toContain(expected)
    })

    it('does not show production stats for non-production rooms', () => {
      const wrapper = mountRoom({ category: 'LIVING', ability: null })

      expect(wrapper.text()).not.toContain('Production Statistics')
    })

    it.each([
      ['AGILITY', 'Food'],
      ['PERCEPTION', 'Water'],
    ])('maps %s rooms onto the %s resource', async (ability, resource) => {
      seedDwellers()

      const wrapper = mountRoom({ ability })
      await flushPromises()

      expect(wrapper.text()).toContain(resource)
    })
  })

  describe('Assigned Dwellers', () => {
    it('renders assigned dwellers in their scene slots', () => {
      seedDwellers()

      const wrapper = mountRoom()

      expect(wrapper.find('[aria-label="Open John Doe"]').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Open Jane Smith"]').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Apprentice training strength"]').exists()).toBe(true)
      expect(wrapper.find('.apprentice-slot.slot-filled').exists()).toBe(true)
      expect(wrapper.findAll('.dweller-sprite-slot:not(.apprentice-slot)')).toHaveLength(2)
    })

    it('reads assigned occupants from the vault roster when it is loaded', () => {
      seedDwellers([], { allDwellers: mockDwellers, allDwellersLoadedVaultId: 'vault-123' })

      const wrapper = mountRoom()

      expect(wrapper.find('[aria-label="Open John Doe"]').exists()).toBe(true)
      expect(wrapper.find('[aria-label="Open Jane Smith"]').exists()).toBe(true)
    })

    it('shows the empty state with assign actions when nobody is assigned', () => {
      seedDwellers([])

      const wrapper = mountRoom()

      expect(wrapper.find('.room-scene').exists()).toBe(true)
      expect(wrapper.findAll('.scene-empty-worker')).toHaveLength(2)
      expect(wrapper.findAll('[aria-label="Assign worker"]')).toHaveLength(2)
      expect(wrapper.find('.scene-empty-apprentice').exists()).toBe(true)
    })

    it('keeps apprentice assignment exclusive to production rooms', () => {
      const wrapper = mountRoom({ category: 'SPECIAL', ability: 'CHARISMA', name: 'Radio Studio' })

      expect(wrapper.find('.scene-empty-worker').exists()).toBe(true)
      expect(wrapper.find('.scene-empty-apprentice').exists()).toBe(false)
    })

    it('assigns a dweller picked from the inline picker', async () => {
      useAuthStore().token = 'test-token'
      const assign = assignSpy()
      seedDwellers([idleAdult()])

      const wrapper = mountRoom()
      await wrapper.get('.scene-empty-worker').trigger('click')

      const pickerCard = wrapper
        .findAll('.dweller-picker .dweller-list-row')
        .find((card) => card.text().includes('John'))
      expect(pickerCard).toBeTruthy()
      await pickerCard!.trigger('click')

      expect(assign).toHaveBeenCalledWith('dweller-1', 'room-1')
    })

    it.each([false, true])(
      'starts a unified Arena lineup and retains it on rejection=%s',
      async (rejected) => {
        useAuthStore().token = 'test-token'
        const assign = assignSpy()
        seedDwellers([{ ...mockDwellers[1], age_group: 'child', room_id: null }])
        const wrapper = mountRoom(
          { name: 'Arena', category: 'ARENA', ability: null },
          { vaultId: 'vault-123' }
        )
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
            .find((candidate) => candidate.text().includes(candidates[index].name))!
            .trigger('click')
        }
        expect(assign).not.toHaveBeenCalled()
        const post = vi.mocked(axios.post)
        if (rejected) post.mockRejectedValueOnce(new Error('Full'))
        await click(wrapper, 'START FIGHT')
        expect(post).toHaveBeenCalledWith(
          expect.stringContaining('/arena/vault/vault-123/rooms/room-1/start'),
          expect.objectContaining({
            fighter_a_id: 'fighter-0',
            fighter_b_id: 'fighter-1',
            mode: 'duel',
          })
        )
        expect(assign).not.toHaveBeenCalled()
        if (!rejected) return
        expect(arenaToastError).toHaveBeenCalled()
        expect(wrapper.text()).toContain('Lucy')
        expect(wrapper.text()).toContain('Maximus')
        expect(button(wrapper, 'START FIGHT')!.attributes('disabled')).toBeUndefined()
      }
    )

    it('assigns a youth through the dedicated apprentice action', async () => {
      useAuthStore().token = 'test-token'
      const assign = assignSpy()
      seedDwellers([
        { ...mockDwellers[0], room_id: null, status: 'idle' },
        { ...mockDwellers[1], age_group: 'adult', room_id: null, status: 'idle' },
      ])

      const wrapper = mountRoom()
      await wrapper.get('.scene-empty-apprentice').trigger('click')
      expect(wrapper.find('.picker-title').text()).toBe('Select Apprentice')
      expect(wrapper.findAll('.dweller-picker .dweller-list-row')).toHaveLength(1)
      await wrapper.get('.dweller-picker .dweller-list-row').trigger('click')

      expect(assign).toHaveBeenCalledWith('dweller-1', 'room-1')
    })

    it('offers dwellers sorted by the room stat, best first', async () => {
      seedDwellers([
        idleAdult({ id: 'low-str', first_name: 'Lowbie', strength: 2 }),
        idleAdult({ id: 'high-str', first_name: 'Strong', strength: 10 }, mockDwellers[1]),
      ])

      const wrapper = mountRoom()
      await wrapper.get('.scene-empty-worker').trigger('click')

      const cards = wrapper.findAll('.dweller-picker .dweller-list-row')
      expect(cards).toHaveLength(2)
      expect(cards[0].text()).toContain('Strong')
      expect(cards[0].get('.picker-room-stat').text()).toContain('Strength')
      expect(cards[0].get('.picker-room-stat').text()).toContain('10')
    })
  })

  describe('Management Actions', () => {
    it.each([
      [1, 'Upgrade to Tier 2', '500 caps'],
      [2, 'Upgrade to Tier 3', '1500 caps'],
    ])('offers the next tier upgrade from tier %i', (tier, label, cost) => {
      const wrapper = mountRoom({ tier })

      expect(wrapper.text()).toContain(label)
      expect(wrapper.text()).toContain(cost)
    })

    it('shows a quiet max-tier status instead of a disabled action', () => {
      const wrapper = mountRoom({ tier: 3 })

      expect(wrapper.text()).toContain('Max tier reached')
      expect(wrapper.text()).toContain('(3/3)')
      expect(button(wrapper, 'Upgrade to Tier')).toBeUndefined()
    })

    it('omits upgrade controls for rooms without an upgrade path', () => {
      const wrapper = mountRoom({
        category: 'SPECIAL',
        t2_upgrade_cost: null,
        t3_upgrade_cost: null,
      })

      expect(wrapper.text()).not.toContain('Max tier reached')
      expect(wrapper.text()).not.toContain('Upgrade to Tier')
    })

    it('exposes the room-wide actions under Management, without a Staffing roster', () => {
      const wrapper = mountRoom()
      const management = wrapper.find('.room-management')

      expect(wrapper.find('.room-scene').exists()).toBe(true)
      expect(wrapper.find('.header-metadata').exists()).toBe(true)
      expect(management.text()).toContain('Management')
      expect(management.text()).toContain('Unassign All Dwellers')
      expect(management.text()).toContain('Destroy Room')
      expect(wrapper.text()).not.toContain('Staffing')
      expect(wrapper.find('.dweller-list-row').exists()).toBe(false)
    })

    it.each([
      ['Radio Studio', 'SPECIAL', 'CHARISMA', false],
      ['Living quarters', 'LIVING', 'CHARISMA', true],
    ])(
      'shows a split action for %s only when the room allows it',
      (name, category, ability, split) => {
        const wrapper = mountRoom({
          name,
          category,
          ability,
          size: 6,
          size_min: 3,
          size_max: 9,
          incremental_cost: 25,
        })

        expect(Boolean(button(wrapper, 'Split into'))).toBe(split)
      }
    )

    it('confirms unassign-all in a themed dialog and cancels without changing dwellers', async () => {
      seedDwellers()
      useAuthStore().token = 'test-token'
      const unassign = vi
        .spyOn(useDwellerStore().management, 'unassignDwellerFromRoom')
        .mockResolvedValue({} as never)
      const nativeConfirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
      const wrapper = mountRoom({}, { vaultId: 'vault-123' })
      const request = button(wrapper, 'Unassign All Dwellers')!
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
        .find((candidate) => candidate.text() === 'Cancel')!
        .trigger('click')
      expect(unassign).not.toHaveBeenCalled()

      await request.trigger('click')
      await confirmation
        .findAll('button')
        .find((candidate) => candidate.text() === 'Unassign all')!
        .trigger('click')
      await flushPromises()
      expect(unassign.mock.calls).toEqual([['dweller-1'], ['dweller-2']])
      expect(wrapper.emitted('roomUpdated')).toHaveLength(1)
      expect(confirmation.props('open')).toBe(false)
      wrapper.unmount()
      nativeConfirm.mockRestore()
    })

    it('unassigns the selected dweller from its scene control', async () => {
      useAuthStore().token = 'test-token'
      const unassignSpy = vi
        .spyOn(useDwellerStore().management, 'unassignDwellerFromRoom')
        .mockResolvedValue({} as never)
      seedDwellers()

      const wrapper = mountRoom()

      expect(wrapper.findAll('.scene-unassign')).toHaveLength(mockDwellers.length)
      expect(wrapper.find('[aria-label="Unassign John Doe"]').exists()).toBe(true)
      await wrapper.get('[aria-label="Unassign John Doe"]').trigger('click')

      expect(unassignSpy).toHaveBeenCalledWith('dweller-1')
    })
  })

  describe('Events and errors', () => {
    it('emits roomUpdated after a successful upgrade', async () => {
      useAuthStore().token = 'test-token'
      vi.spyOn(useRoomStore(), 'upgradeRoom').mockResolvedValue()

      const wrapper = mountRoom()
      await click(wrapper, 'Upgrade to Tier')

      expect(wrapper.emitted('roomUpdated')).toBeTruthy()
    })

    it('displays and then clears the action error on close', async () => {
      useAuthStore().token = 'test-token'
      const consoleSpy = vi.spyOn(console, 'error').mockImplementation(() => {})
      vi.spyOn(useRoomStore(), 'upgradeRoom').mockRejectedValue(new Error('Insufficient caps'))

      try {
        const wrapper = mountRoom()

        expect(wrapper.find('.error-banner').exists()).toBe(false)
        await click(wrapper, 'Upgrade to Tier')
        expect(wrapper.text()).toContain('Insufficient caps')

        await wrapper.setProps({ modelValue: false })
        await wrapper.vm.$nextTick()
        await wrapper.setProps({ modelValue: true })
        await wrapper.vm.$nextTick()

        expect(wrapper.text()).not.toContain('Insufficient caps')
      } finally {
        consoleSpy.mockRestore()
      }
    })
  })

  describe('Radio Room', () => {
    const seedRadioDwellers = () =>
      seedDwellers(mockDwellers.map((dweller) => ({ ...dweller, room_id: radioRoom.id })))

    it.each([true, false])('renders broadcast controls for a radio room=%s', (radio) => {
      if (radio) seedRadioDwellers()
      const wrapper = mountRoom(radio ? radioRoom : {})

      expect(wrapper.find('.radio-controls').exists()).toBe(radio)
      if (!radio) return
      expect(wrapper.text()).toContain('Radio Studio')
      expect(wrapper.text()).toContain('Broadcast Controls')
    })

    it('offers recruitment and happiness modes with recruitment active by default', () => {
      seedRadioDwellers()

      const wrapper = mountRoom(radioRoom)
      const modeButtons = wrapper.findAll('.mode-btn')

      expect(modeButtons.length).toBe(2)
      expect(modeButtons[0].text()).toContain('Recruitment')
      expect(modeButtons[1].text()).toContain('Happiness')
      expect(modeButtons[0].classes()).toContain('active')
      expect(modeButtons[1].classes()).not.toContain('active')
      expect(wrapper.text()).toContain('Recruiting')
    })

    it('warns and locks recruitment while the room is unstaffed', () => {
      const wrapper = mountRoom(radioRoom)
      const recruitBtn = wrapper.find('.recruit-btn')

      expect(wrapper.find('.mock-alert').exists()).toBe(true)
      expect(wrapper.text()).toContain('Assign at least one dweller')
      expect(recruitBtn.exists()).toBe(true)
      expect(recruitBtn.attributes('disabled')).toBeDefined()
    })

    it('enables recruitment with the cost once the room is staffed', () => {
      seedRadioDwellers()

      const wrapper = mountRoom(radioRoom)
      const recruitBtn = wrapper.find('.recruit-btn')

      expect(recruitBtn.exists()).toBe(true)
      expect(recruitBtn.attributes('disabled')).toBeUndefined()
      expect(wrapper.text()).toContain('Recruit Dweller')
      expect(wrapper.text()).toContain('100 caps')
    })
  })

  describe('Dweller Click Navigation', () => {
    it.each([
      ['.scene-dweller', 'dweller-2'],
      ['.apprentice-slot .scene-dweller', 'dweller-1'],
    ])('opens dweller details from %s', async (selector, dweller) => {
      seedDwellers()

      const wrapper = mountRoom()
      await wrapper.get(selector).trigger('click')

      expect(mockRouterPush).toHaveBeenCalledWith({ query: { roomId: 'room-1', dweller } })
    })

    it('opens the matching assignment picker from an empty scene slot', async () => {
      seedDwellers([])

      const wrapper = mountRoom()

      await wrapper.get('.scene-empty-worker').trigger('click')
      expect(wrapper.get('.picker-title').text()).toBe('Select Worker')

      await wrapper.get('.picker-close').trigger('click')
      await wrapper.get('.scene-empty-apprentice').trigger('click')
      expect(wrapper.get('.picker-title').text()).toBe('Select Apprentice')
    })
  })

  describe('Vault Door Edge Cases', () => {
    it('keeps the vault door destroy action disabled inside its tooltip', () => {
      const wrapper = mountRoom(vaultDoor)
      const tooltip = wrapper.find('.mock-tooltip')

      expect(wrapper.text()).toContain('Destroy Room')
      expect(tooltip.exists()).toBe(true)
      expect(tooltip.text()).toContain('The Vault Door is vital and cannot be destroyed.')
      expect(tooltip.find('.mock-button').attributes('disabled')).toBeDefined()
    })

    it('leaves destroy enabled and un-tooltipped for ordinary rooms', () => {
      const wrapper = mountRoom()

      expect(wrapper.find('.mock-tooltip').exists()).toBe(false)
      const destroy = wrapper
        .findAll('.mock-button')
        .filter((btn) => btn.text().includes('Destroy Room'))
      expect(destroy).toHaveLength(1)
      expect(destroy[0].attributes('disabled')).toBeUndefined()
    })
  })

  it('does not render modal content when room is null', () => {
    const wrapper = mountRoom(null)

    expect(wrapper.find('.modal-content').exists()).toBe(false)
  })

  describe('Live incident overlay', () => {
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
    const seedAftermath = (overrides: Record<string, unknown> = {}) =>
      useIncidentStore().aftermaths.set('room-1', {
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
        ...overrides,
      } as never)

    it('replaces the generic sections with the incident overlay', () => {
      seedIncident()

      const wrapper = mountRoom({}, { vaultId: 'vault-1' })

      expect(wrapper.text()).toContain('RAIDER ATTACK')
      expect(wrapper.text()).not.toContain('Unassign All Dwellers')
      expect(wrapper.text()).not.toContain('Destroy Room')
    })

    it('renders the generic sections when the incident is for another room', () => {
      seedIncident()

      const wrapper = mountRoom({ id: 'room-2' }, { vaultId: 'vault-1' })

      expect(wrapper.text()).not.toContain('RAIDER ATTACK')
    })

    it('keeps arena precedence when an arena room has a live incident', () => {
      seedIncident()

      const wrapper = mountRoom({ name: 'Arena', category: 'ARENA' }, { vaultId: 'vault-1' })

      expect(wrapper.text()).not.toContain('RAIDER ATTACK')
      expect(wrapper.text()).toContain('Arena')
    })

    it('replaces the generic sections with the aftermath once the incident is over', () => {
      seedAftermath()

      const wrapper = mountRoom({}, { vaultId: 'vault-1' })

      expect(wrapper.text()).toContain('Incident lost')
      expect(wrapper.text()).not.toContain('Unassign All Dwellers')
      expect(wrapper.text()).not.toContain('Destroy Room')
    })

    it('prefers a live incident over a lingering aftermath', () => {
      seedIncident()
      seedAftermath({ incidentId: 'incident-0', type: 'fire', outcome: 'unknown', rounds: 0 })

      const wrapper = mountRoom({}, { vaultId: 'vault-1' })

      expect(wrapper.text()).toContain('RAIDER ATTACK')
      expect(wrapper.text()).not.toContain('INCIDENT ENDED')
    })

    it('keeps the incident scene through the final journal fetch and attack playback', async () => {
      vi.useFakeTimers()
      seedIncident()
      const store = useIncidentStore()
      const wrapper = mountRoom({}, { vaultId: 'vault-1' })
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
    it('plays the per-room ambience and re-plays it on a room change', async () => {
      const ambienceSpy = vi.spyOn(audioManager, 'playAmbience')
      const playSpy = vi.spyOn(audioManager, 'play')
      const wrapper = mountRoom({ name: 'Armory', category: 'TRAINING' })
      expect(ambienceSpy).toHaveBeenCalledWith('armory')

      await wrapper.setProps({ room: { ...mockRoom, id: 'room-2', name: 'Classroom' } })

      expect(ambienceSpy).toHaveBeenCalledWith('classroom')
      expect(playSpy.mock.calls.filter(([key]) => key === 'modalOpen')).toHaveLength(1)
      ambienceSpy.mockRestore()
      playSpy.mockRestore()
    })

    it('falls back to the category loop for a room with no per-room ambience', () => {
      const ambienceSpy = vi.spyOn(audioManager, 'playAmbience')
      mountRoom({ name: 'Broom Closet', category: 'TRAINING' })

      expect(ambienceSpy).toHaveBeenCalledWith('training')
      ambienceSpy.mockRestore()
    })

    it('plays the theme music and the plain ambience loop, stopping on close', async () => {
      const musicSpy = vi.spyOn(audioManager, 'playThemedRoomMusic')
      const ambienceSpy = vi.spyOn(audioManager, 'playAmbience')
      const stopSpy = vi.spyOn(audioManager, 'stopThemedRoomMusic')
      const wrapper = mountRoom({ name: 'Diner', category: 'diner', room_style: 'xmas' })

      expect(musicSpy).toHaveBeenCalledWith('diner:xmas')
      expect(ambienceSpy).toHaveBeenCalledWith('diner')
      expect(ambienceSpy).not.toHaveBeenCalledWith('diner:xmas')

      await wrapper.setProps({ modelValue: false })
      expect(stopSpy).toHaveBeenCalled()
      musicSpy.mockRestore()
      ambienceSpy.mockRestore()
      stopSpy.mockRestore()
    })

    it('stops the theme music for a room without a theme', () => {
      const musicSpy = vi.spyOn(audioManager, 'playThemedRoomMusic')
      const stopSpy = vi.spyOn(audioManager, 'stopThemedRoomMusic')
      mountRoom()

      expect(musicSpy).not.toHaveBeenCalled()
      expect(stopSpy).toHaveBeenCalled()
      musicSpy.mockRestore()
      stopSpy.mockRestore()
    })
  })
})

describe('Response Station surface', () => {
  const responseRoom = {
    ...mockRoom,
    id: 'station-1',
    name: 'Response Station',
    category: 'response',
    ability: 'endurance',
    capacity: null,
    output: null,
    t2_upgrade_cost: null,
    t3_upgrade_cost: null,
    base_cost: 600,
    population_required: 15,
  }
  const mountStation = (room: Record<string, unknown> = responseRoom) => mountRoom(room)

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useAuthStore().token = 'test-token'
  })

  it('renders the station management surface with standing actions', async () => {
    const wrapper = mountStation()
    await flushPromises()

    expect(wrapper.find('.response-station').exists()).toBe(true)
    expect(wrapper.text()).toContain('Station Management')
    expect(wrapper.text()).toContain('stationed')
    expect(wrapper.text()).toContain('Destroy Room')
    expect(wrapper.find('.header-metadata').text()).toContain('Capacity: 2')
  })
})
