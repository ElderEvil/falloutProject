import { describe, it, expect, vi, beforeEach } from 'vitest'
import { createIconifyMock, createToastMock } from '../../helpers/mocks'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ArenaModal from '@/modules/rooms/components/ArenaModal.vue'
import type { ArenaRoomState } from '@/modules/rooms/api/arena'

const mockToast = createToastMock()

vi.mock('@iconify/vue', () =>
  createIconifyMock({ template: '<div class="mock-icon" :data-icon="icon"></div>' })
)

vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

vi.mock('@/core/composables/usePolling', () => ({
  usePolling: () => vi.fn(),
}))

vi.mock('@/modules/auth/stores/auth', () => ({
  useAuthStore: () => ({ token: 'test-token' }),
}))

vi.mock('@/modules/dwellers/stores/dweller', () => ({
  useDwellerStore: () => ({
    management: { unassignDwellerFromRoom: vi.fn().mockResolvedValue({}) },
  }),
}))

const storeMock = vi.hoisted(() => {
  const readyRoom: ArenaRoomState = {
    room_id: 'room-1',
    room_name: 'Arena',
    tier: 1,
    fighter_a_id: 'a-1',
    fighter_b_id: 'b-1',
    fighters: [
      { id: 'a-1', name: 'Alpha Dweller', level: 10, health: 80, max_health: 100, power: 42 },
      { id: 'b-1', name: 'Bravo Dweller', level: 8, health: 90, max_health: 100, power: 35 },
    ],
    roster: [
      { id: 'a-1', name: 'Alpha Dweller', level: 10, health: 80, max_health: 100 },
      { id: 'b-1', name: 'Bravo Dweller', level: 8, health: 90, max_health: 100 },
    ],
    fight_ready: true,
    match_done: false,
    fight_started: false,
    countdown_remaining: 0,
    can_start: true,
    winner_name: null,
    events: [],
  }
  return {
    currentRoom: readyRoom as ArenaRoomState | null,
    fetchState: vi.fn(),
    readyRoom,
  }
})

vi.mock('@/modules/rooms/stores/arena', () => ({
  useArenaStore: () => ({
    getRoom: () => storeMock.currentRoom,
    fetchState: storeMock.fetchState,
    setFighters: vi.fn().mockResolvedValue(true),
    startFight: vi.fn().mockResolvedValue(true),
    clearEvents: vi.fn().mockResolvedValue(true),
    reset: vi.fn(),
  }),
}))

describe('ArenaModal', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    storeMock.currentRoom = storeMock.readyRoom
    storeMock.fetchState.mockReset().mockResolvedValue(true)
  })

  it('renders fighter slots with names and power', async () => {
    const wrapper = mount(ArenaModal, {
      props: { vaultId: 'vault-1', roomId: 'room-1' },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Alpha Dweller')
    expect(wrapper.text()).toContain('Bravo Dweller')
    expect(wrapper.text()).toContain('POW 42')
    expect(storeMock.fetchState).toHaveBeenCalledWith('vault-1', 'test-token', false)
  })

  it('shows START FIGHT when the room is ready', async () => {
    const wrapper = mount(ArenaModal, {
      props: { vaultId: 'vault-1', roomId: 'room-1' },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('START FIGHT')
    expect(wrapper.text()).toContain('READY')
  })

  it('keeps room-management actions out of the battle panel', async () => {
    const wrapper = mount(ArenaModal, {
      props: { vaultId: 'vault-1', roomId: 'room-1' },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    expect(wrapper.find('.arena-management').exists()).toBe(false)
    expect(wrapper.text()).not.toContain('Unassign All Dwellers')
    expect(wrapper.text()).not.toContain('Destroy Room')
  })

  it('shows a retry state when loading the arena fails', async () => {
    storeMock.fetchState.mockResolvedValueOnce(false)
    const wrapper = mount(ArenaModal, {
      props: { vaultId: 'vault-1', roomId: 'room-1' },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('Unable to load Arena status.')
    await wrapper.get('button').trigger('click')
    expect(storeMock.fetchState).toHaveBeenCalledTimes(2)
  })

  it('shows the winner banner when a match is done', async () => {
    storeMock.currentRoom = { ...storeMock.readyRoom, match_done: true, winner_name: 'Alpha Dweller' }
    const wrapper = mount(ArenaModal, {
      props: { vaultId: 'vault-1', roomId: 'room-1' },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    expect(wrapper.text()).toContain('MATCH COMPLETE')
    expect(wrapper.text()).toContain('Alpha Dweller wins')
  })

  it('renders the battle journal oldest-first with round numbers and grouping', async () => {
    storeMock.currentRoom = {
      ...storeMock.readyRoom,
      events: [
        { id: 'e4', round_seq: 4, kind: 'finish', message: 'Alpha Dweller defeated Bravo Dweller!' },
        { id: 'e3', round_seq: 3, kind: 'hit', message: 'Alpha Dweller hits Bravo Dweller for 5' },
        { id: 'e2', round_seq: 2, kind: 'hit', message: 'Alpha Dweller hits Bravo Dweller for 5' },
        { id: 'e1', round_seq: 1, kind: 'hit', message: 'Bravo Dweller hits Alpha Dweller for 3' },
      ],
    }
    const wrapper = mount(ArenaModal, {
      props: { vaultId: 'vault-1', roomId: 'room-1' },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    const items = wrapper.findAll('[aria-label="Battle log"] li')
    expect(items).toHaveLength(3)
    expect(items[0].text()).toContain('Bravo Dweller hits Alpha Dweller for 3')
    expect(items[0].text()).toContain('R1')
    expect(items[1].text()).toContain('Alpha Dweller hits Bravo Dweller for 5')
    expect(items[1].text()).toContain('R2')
    expect(items[1].text()).toContain('×2')
    expect(items[2].text()).toContain('FINISH')
    expect(items[2].text()).toContain('R4')
  })

  it('shows a polite empty state when no rounds have been fought', async () => {
    const wrapper = mount(ArenaModal, {
      props: { vaultId: 'vault-1', roomId: 'room-1' },
      global: { plugins: [createPinia()] },
    })
    await flushPromises()

    const journal = wrapper.get('[aria-label="Battle log"]')
    expect(journal.attributes('aria-live')).toBe('polite')
    expect(journal.text()).toContain('No rounds fought yet.')
  })
})
