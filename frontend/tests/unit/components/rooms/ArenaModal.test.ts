import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import ArenaModal from '@/modules/rooms/components/ArenaModal.vue'
import type { ArenaRoomState } from '@/modules/rooms/api/arena'

vi.mock('@iconify/vue', () => ({
  Icon: {
    name: 'Icon',
    props: ['icon'],
    template: '<div class="mock-icon" :data-icon="icon"></div>',
  },
}))

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }),
}))

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
})
