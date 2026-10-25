import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createToastMock } from '../helpers/mocks'
import { setActivePinia, createPinia } from 'pinia'
import { useArenaStore } from '@/modules/rooms/stores/arena'
import { arenaApi } from '@/modules/rooms/api/arena'
import type { ArenaState, ArenaRoomState } from '@/modules/rooms/api/arena'

vi.mock('@/modules/rooms/api/arena')

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({
  useToast: () => mockToast,
}))

const mockRoom: ArenaRoomState = {
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
  it('queues an active skill and refreshes charge and journal state', async () => {
    const store = useArenaStore()
    expect(await store.queueSkill('vault-1', 'room-1', 'fighter-1', 'token')).toBe(true)
    expect(arenaApi.queueSkill).toHaveBeenCalledWith('vault-1', 'room-1', 'fighter-1', 'token')
    expect(store.getRoom('room-1')).toEqual(mockRoom)
  })

  it('surfaces a rejected active skill', async () => {
    vi.mocked(arenaApi.queueSkill).mockRejectedValueOnce(new Error('Skill is not charged'))
    const store = useArenaStore()
    expect(await store.queueSkill('vault-1', 'room-1', 'fighter-1', 'token')).toBe(false)
    expect(arenaApi.fetchState).not.toHaveBeenCalled()
  })

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

  it('ignores a delayed response after switching vaults', async () => {
    let finishOld!: (state: ArenaState) => void
    vi.mocked(arenaApi.fetchState).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishOld = resolve
        })
    )
    const store = useArenaStore()
    const old = store.fetchState('old-vault', 'old-token')
    await store.fetchState('new-vault', 'new-token')
    finishOld({ rooms: [{ ...mockRoom, room_id: 'old-room' }] })
    expect(await old).toBe(false)
    expect(store.getRoom('old-room')).toBeNull()
    expect(store.getRoom('room-1')).toEqual(mockRoom)
  })

  it('does not restore a cleared account from an in-flight request', async () => {
    let finish!: (state: ArenaState) => void
    vi.mocked(arenaApi.fetchState).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const store = useArenaStore()
    const request = store.fetchState('vault-1', 'token')
    store.reset()
    finish(mockState)
    expect(await request).toBe(false)
    expect(store.rooms.size).toBe(0)
  })

  it('setFighters persists the duel selection and refreshes state', async () => {
    const store = useArenaStore()
    const ok = await store.setFighters(
      'vault-1',
      'room-1',
      { mode: 'duel', fighterAId: 'a-1', fighterBId: 'b-1' },
      'token'
    )

    expect(ok).toBe(true)
    expect(arenaApi.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      { mode: 'duel', fighterAId: 'a-1', fighterBId: 'b-1' },
      'token'
    )
    expect(arenaApi.fetchState).toHaveBeenCalledWith('vault-1', 'token')
  })

  it('setFighters forwards a brawl selection with mode and both second slots', async () => {
    const store = useArenaStore()

    await store.setFighters(
      'vault-1',
      'room-1',
      { mode: 'brawl', fighterAId: 'a-1', fighterBId: 'b-1', fighterCId: 'c-1', fighterDId: 'd-1' },
      'token'
    )

    expect(arenaApi.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      { mode: 'brawl', fighterAId: 'a-1', fighterBId: 'b-1', fighterCId: 'c-1', fighterDId: 'd-1' },
      'token'
    )
  })

  it('setFighters forwards a hunt selection with dwellers and opponent keys', async () => {
    const store = useArenaStore()

    await store.setFighters(
      'vault-1',
      'room-1',
      {
        mode: 'hunt',
        fighterAId: 'a-1',
        fighterBId: null,
        fighterCId: 'c-1',
        fighterDId: null,
        opponentKeys: ['radroach-swarm', 'deathclaw'],
      },
      'token'
    )

    expect(arenaApi.setFighters).toHaveBeenCalledWith(
      'vault-1',
      'room-1',
      {
        mode: 'hunt',
        fighterAId: 'a-1',
        fighterBId: null,
        fighterCId: 'c-1',
        fighterDId: null,
        opponentKeys: ['radroach-swarm', 'deathclaw'],
      },
      'token'
    )
  })

  it('fetchCreatures loads the hunt catalogue', async () => {
    const catalogue = [{ key: 'radroach-swarm', name: 'Radroach swarm', power: 35, max_hp: 35 }]
    vi.mocked(arenaApi.fetchCreatures).mockResolvedValue(catalogue)
    const store = useArenaStore()

    const ok = await store.fetchCreatures('vault-1', 'token')

    expect(ok).toBe(true)
    expect(store.creatures).toEqual(catalogue)
    expect(arenaApi.fetchCreatures).toHaveBeenCalledWith('vault-1', 'token')
  })

  it('fetchCreatures returns false and surfaces the error on failure', async () => {
    vi.mocked(arenaApi.fetchCreatures).mockRejectedValue(new Error('boom'))
    const store = useArenaStore()

    const ok = await store.fetchCreatures('vault-1', 'token')

    expect(ok).toBe(false)
  })

  it('setFighters returns false and surfaces the error on failure', async () => {
    vi.mocked(arenaApi.setFighters).mockRejectedValue(new Error('boom'))
    const store = useArenaStore()

    const ok = await store.setFighters(
      'vault-1',
      'room-1',
      { mode: 'duel', fighterAId: 'a-1', fighterBId: 'b-1' },
      'token'
    )

    expect(ok).toBe(false)
  })

  it('startFight calls the API and refreshes state', async () => {
    const store = useArenaStore()
    const ok = await store.startFight('vault-1', 'room-1', 'token')

    expect(ok).toBe(true)
    expect(arenaApi.startFight).toHaveBeenCalledWith('vault-1', 'room-1', 'token', undefined)
  })

  it.each(['before', 'after'])(
    'keeps a successful start when its refresh finishes %s a newer poll',
    async (order) => {
      const store = useArenaStore()
      await store.fetchState('vault-1', 'token')
      let finishRefresh!: (state: ArenaState) => void
      let finishPoll!: (state: ArenaState) => void
      vi.mocked(arenaApi.fetchState)
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              finishRefresh = resolve
            })
        )
        .mockImplementationOnce(
          () =>
            new Promise((resolve) => {
              finishPoll = resolve
            })
        )

      const start = store.startFight('vault-1', 'room-1', 'token')
      await vi.waitFor(() => expect(arenaApi.fetchState).toHaveBeenCalledTimes(2))
      const poll = store.fetchState('vault-1', 'token')
      const freshRoom = { ...mockRoom, fight_started: true, countdown_remaining: 2 }
      if (order === 'after') {
        finishPoll({ rooms: [freshRoom] })
        expect(await poll).toBe(true)
      }
      finishRefresh({ rooms: [{ ...freshRoom, countdown_remaining: 3 }] })
      expect(await start).toBe(true)
      if (order === 'before') {
        expect(store.getRoom('room-1')).toEqual(mockRoom)
        finishPoll({ rooms: [freshRoom] })
        expect(await poll).toBe(true)
      }
      expect(store.getRoom('room-1')).toEqual(freshRoom)
    }
  )

  it('clearEvents returns the cleared count', async () => {
    vi.mocked(arenaApi.clearEvents).mockResolvedValue(4)
    const store = useArenaStore()

    const ok = await store.clearEvents('vault-1', 'room-1', 'token')

    expect(ok).toBe(true)
    expect(arenaApi.clearEvents).toHaveBeenCalledWith('vault-1', 'room-1', 'token')
  })

  it.each([
    [
      'setFighters',
      (store: ReturnType<typeof useArenaStore>) =>
        store.setFighters(
          'vault-1',
          'room-1',
          { mode: 'duel', fighterAId: 'a-1', fighterBId: 'b-1' },
          'token'
        ),
    ],
    [
      'startFight',
      (store: ReturnType<typeof useArenaStore>) => store.startFight('vault-1', 'room-1', 'token'),
    ],
    [
      'clearEvents',
      (store: ReturnType<typeof useArenaStore>) => store.clearEvents('vault-1', 'room-1', 'token'),
    ],
  ] as const)('returns false when the state refresh fails after %s', async (_name, action) => {
    vi.mocked(arenaApi.fetchState).mockResolvedValue(mockState)
    const store = useArenaStore()
    // The mutation succeeds but the post-mutation refresh fails: the refresh
    // failure must propagate as false so callers know the UI is stale.
    vi.mocked(arenaApi.fetchState).mockRejectedValueOnce(new Error('refresh boom'))

    const ok = await action(store)

    expect(ok).toBe(false)
  })

  it('reset clears the room map', async () => {
    const store = useArenaStore()
    await store.fetchState('vault-1', 'token')
    store.reset()

    expect(store.rooms.size).toBe(0)
  })
  it.each(['reset', 'vault switch'])('ignores a delayed start after a %s', async (change) => {
    const store = useArenaStore()
    await store.fetchState('vault-1', 'token')
    let finish!: () => void
    vi.mocked(arenaApi.startFight).mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve
        })
    )
    const pending = store.startFight('vault-1', 'room-1', 'token', {
      mode: 'duel',
      fighterAId: 'a',
      fighterBId: 'b',
    })
    if (change === 'reset') store.reset()
    else await store.fetchState('vault-2', 'new-token')
    const calls = vi.mocked(arenaApi.fetchState).mock.calls.length
    finish()
    expect(await pending).toBe(false)
    expect(arenaApi.fetchState).toHaveBeenCalledTimes(calls)
    if (change === 'reset') expect(store.rooms.size).toBe(0)
  })
})
