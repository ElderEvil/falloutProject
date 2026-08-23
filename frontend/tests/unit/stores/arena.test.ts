import { describe, it, expect, beforeEach, vi } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useArenaStore } from '@/modules/rooms/stores/arena'
import { arenaApi } from '@/modules/rooms/api/arena'
import type { ArenaState, ArenaRoomState } from '@/modules/rooms/api/arena'

vi.mock('@/modules/rooms/api/arena')

vi.mock('@/core/composables/useToast', () => ({
  useToast: () => ({ success: vi.fn(), error: vi.fn(), warning: vi.fn(), info: vi.fn() }),
}))

const mockRoom: ArenaRoomState = {
  room_id: 'room-1',
  room_name: 'Arena',
  tier: 1,
  fighter_a_id: null,
  fighter_b_id: null,
  fighters: [],
  roster: [],
  fight_ready: false,
  match_done: false,
  fight_started: false,
  countdown_remaining: 0,
  can_start: false,
  winner_name: null,
  events: [],
}

const mockState: ArenaState = { rooms: [mockRoom] }

describe('Arena Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(arenaApi.fetchState).mockResolvedValue(mockState)
  })

  it('loads arena state into the room map', async () => {
    const store = useArenaStore()
    await store.fetchState('vault-1', 'token')

    expect(store.getRoom('room-1')).toEqual(mockRoom)
    expect(store.rooms.size).toBe(1)
  })

  it('returns null for an unknown room', () => {
    const store = useArenaStore()
    expect(store.getRoom('missing')).toBeNull()
  })

  it('setFighters persists the selection and refreshes state', async () => {
    const store = useArenaStore()
    const ok = await store.setFighters('vault-1', 'room-1', 'a-1', 'b-1', 'token')

    expect(ok).toBe(true)
    expect(arenaApi.setFighters).toHaveBeenCalledWith('vault-1', 'room-1', 'a-1', 'b-1', 'token')
    expect(arenaApi.fetchState).toHaveBeenCalledWith('vault-1', 'token')
  })

  it('setFighters returns false and surfaces the error on failure', async () => {
    vi.mocked(arenaApi.setFighters).mockRejectedValue(new Error('boom'))
    const store = useArenaStore()

    const ok = await store.setFighters('vault-1', 'room-1', 'a-1', 'b-1', 'token')

    expect(ok).toBe(false)
  })

  it('startFight calls the API and refreshes state', async () => {
    const store = useArenaStore()
    const ok = await store.startFight('vault-1', 'room-1', 'token')

    expect(ok).toBe(true)
    expect(arenaApi.startFight).toHaveBeenCalledWith('vault-1', 'room-1', 'token')
  })

  it('clearEvents returns the cleared count', async () => {
    vi.mocked(arenaApi.clearEvents).mockResolvedValue(4)
    const store = useArenaStore()

    const ok = await store.clearEvents('vault-1', 'room-1', 'token')

    expect(ok).toBe(true)
    expect(arenaApi.clearEvents).toHaveBeenCalledWith('vault-1', 'room-1', 'token')
  })

  it('reset clears the room map', async () => {
    const store = useArenaStore()
    await store.fetchState('vault-1', 'token')
    store.reset()

    expect(store.rooms.size).toBe(0)
  })
})