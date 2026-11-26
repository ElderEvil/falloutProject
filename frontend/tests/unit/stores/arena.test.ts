import { describe, it, expect, beforeEach, vi } from 'vite-plus/test'
import { createToastMock } from '../helpers/mocks'
import { setActivePinia, createPinia } from 'pinia'
import { useArenaStore } from '@/modules/rooms/stores/arena'
import { arenaApi } from '@/modules/rooms/api/arena'
import type { ArenaState, ArenaRoomState } from '@/modules/rooms/api/arena'

vi.mock('@/modules/rooms/api/arena')

const mockToast = createToastMock()
vi.mock('@/core/composables/useToast', () => ({ useToast: () => mockToast }))

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

const deferred = <T>() => {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((settle) => (resolve = settle))
  return { promise, resolve }
}

const duelSelection = { mode: 'duel' as const, fighterAId: 'a-1', fighterBId: 'b-1' }

describe('Arena Store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    vi.mocked(arenaApi.fetchState).mockResolvedValue(mockState)
  })

  it('queues an active skill and refreshes charge and journal state', async () => {
    const store = useArenaStore()

    expect(await store.queueSkill('vault-1', 'room-1', 'fighter-1')).toBe(true)
    expect(arenaApi.queueSkill).toHaveBeenCalledWith('vault-1', 'room-1', 'fighter-1')
    expect(store.getRoom('room-1')).toEqual(mockRoom)
  })

  it('surfaces a rejected active skill', async () => {
    vi.mocked(arenaApi.queueSkill).mockRejectedValueOnce(new Error('Skill is not charged'))

    expect(await useArenaStore().queueSkill('vault-1', 'room-1', 'fighter-1')).toBe(false)
    expect(arenaApi.fetchState).not.toHaveBeenCalled()
  })

  it('loads arena state into the room map', async () => {
    const store = useArenaStore()
    await store.fetchState('vault-1')

    expect(store.getRoom('room-1')).toEqual(mockRoom)
    expect(store.rooms.size).toBe(1)
  })

  it('returns null for an unknown room', () => {
    expect(useArenaStore().getRoom('missing')).toBeNull()
  })

  it('ignores a delayed response after switching vaults', async () => {
    const old = deferred<ArenaState>()
    vi.mocked(arenaApi.fetchState).mockImplementationOnce(() => old.promise)
    const store = useArenaStore()

    const pending = store.fetchState('old-vault')
    await store.fetchState('new-vault')
    old.resolve({ rooms: [{ ...mockRoom, room_id: 'old-room' }] })

    expect(await pending).toBe(false)
    expect(store.getRoom('old-room')).toBeNull()
    expect(store.getRoom('room-1')).toEqual(mockRoom)
  })

  it('does not restore a cleared account from an in-flight request', async () => {
    const request = deferred<ArenaState>()
    vi.mocked(arenaApi.fetchState).mockImplementationOnce(() => request.promise)
    const store = useArenaStore()

    const pending = store.fetchState('vault-1')
    store.reset()
    request.resolve(mockState)

    expect(await pending).toBe(false)
    expect(store.rooms.size).toBe(0)
  })

  it.each([
    ['a duel', duelSelection],
    [
      'a brawl with both second slots',
      {
        mode: 'brawl' as const,
        fighterAId: 'a-1',
        fighterBId: 'b-1',
        fighterCId: 'c-1',
        fighterDId: 'd-1',
      },
    ],
    [
      'a hunt with dwellers and opponent keys',
      {
        mode: 'hunt' as const,
        fighterAId: 'a-1',
        fighterBId: null,
        fighterCId: 'c-1',
        fighterDId: null,
        opponentKeys: ['radroach-swarm', 'deathclaw'],
      },
    ],
  ])('setFighters persists %s and refreshes state', async (_label, selection) => {
    const store = useArenaStore()

    expect(await store.setFighters('vault-1', 'room-1', selection)).toBe(true)
    expect(arenaApi.setFighters).toHaveBeenCalledWith('vault-1', 'room-1', selection)
    expect(arenaApi.fetchState).toHaveBeenCalledWith('vault-1')
  })

  it('fetchCreatures loads the hunt catalogue', async () => {
    const catalogue = [{ key: 'radroach-swarm', name: 'Radroach swarm', power: 35, max_hp: 35 }]
    vi.mocked(arenaApi.fetchCreatures).mockResolvedValue(catalogue)
    const store = useArenaStore()

    expect(await store.fetchCreatures('vault-1')).toBe(true)
    expect(store.creatures).toEqual(catalogue)
    expect(arenaApi.fetchCreatures).toHaveBeenCalledWith('vault-1')
  })

  it.each([
    [
      'fetchCreatures',
      (store: ReturnType<typeof useArenaStore>) => store.fetchCreatures('vault-1'),
      () => vi.mocked(arenaApi.fetchCreatures).mockRejectedValue(new Error('boom')),
    ],
    [
      'setFighters',
      (store: ReturnType<typeof useArenaStore>) =>
        store.setFighters('vault-1', 'room-1', duelSelection),
      () => vi.mocked(arenaApi.setFighters).mockRejectedValue(new Error('boom')),
    ],
  ] as const)(
    '%s returns false and surfaces the error on failure',
    async (_name, action, breakApi) => {
      breakApi()

      expect(await action(useArenaStore())).toBe(false)
    }
  )

  it('startFight calls the API and refreshes state', async () => {
    const store = useArenaStore()

    expect(await store.startFight('vault-1', 'room-1')).toBe(true)
    expect(arenaApi.startFight).toHaveBeenCalledWith('vault-1', 'room-1', undefined)
  })

  it.each(['before', 'after'])(
    'keeps a successful start when its refresh finishes %s a newer poll',
    async (order) => {
      const store = useArenaStore()
      await store.fetchState('vault-1')
      const refresh = deferred<ArenaState>()
      const pollReply = deferred<ArenaState>()
      vi.mocked(arenaApi.fetchState)
        .mockImplementationOnce(() => refresh.promise)
        .mockImplementationOnce(() => pollReply.promise)

      const start = store.startFight('vault-1', 'room-1')
      await vi.waitFor(() => expect(arenaApi.fetchState).toHaveBeenCalledTimes(2))
      const poll = store.fetchState('vault-1')
      const freshRoom = { ...mockRoom, fight_started: true, countdown_remaining: 2 }
      if (order === 'after') {
        pollReply.resolve({ rooms: [freshRoom] })
        expect(await poll).toBe(true)
      }
      refresh.resolve({ rooms: [{ ...freshRoom, countdown_remaining: 3 }] })
      expect(await start).toBe(true)
      if (order === 'before') {
        expect(store.getRoom('room-1')).toEqual(mockRoom)
        pollReply.resolve({ rooms: [freshRoom] })
        expect(await poll).toBe(true)
      }
      expect(store.getRoom('room-1')).toEqual(freshRoom)
    }
  )

  it('clearEvents returns the cleared count', async () => {
    vi.mocked(arenaApi.clearEvents).mockResolvedValue(4)
    const store = useArenaStore()

    expect(await store.clearEvents('vault-1', 'room-1')).toBe(true)
    expect(arenaApi.clearEvents).toHaveBeenCalledWith('vault-1', 'room-1')
  })

  it.each([
    [
      'setFighters',
      (store: ReturnType<typeof useArenaStore>) =>
        store.setFighters('vault-1', 'room-1', duelSelection),
    ],
    [
      'startFight',
      (store: ReturnType<typeof useArenaStore>) => store.startFight('vault-1', 'room-1'),
    ],
    [
      'clearEvents',
      (store: ReturnType<typeof useArenaStore>) => store.clearEvents('vault-1', 'room-1'),
    ],
  ] as const)('returns false when the state refresh fails after %s', async (_name, action) => {
    const store = useArenaStore()
    // The mutation succeeds but the post-mutation refresh fails: the refresh
    // failure must propagate as false so callers know the UI is stale.
    vi.mocked(arenaApi.fetchState).mockRejectedValueOnce(new Error('refresh boom'))

    expect(await action(store)).toBe(false)
  })

  it('reset clears the room map', async () => {
    const store = useArenaStore()
    await store.fetchState('vault-1')

    store.reset()

    expect(store.rooms.size).toBe(0)
  })

  it.each(['reset', 'vault switch'])('ignores a delayed start after a %s', async (change) => {
    const store = useArenaStore()
    await store.fetchState('vault-1')
    const start = deferred<void>()
    vi.mocked(arenaApi.startFight).mockImplementationOnce(() => start.promise)

    const pending = store.startFight('vault-1', 'room-1', {
      mode: 'duel',
      fighterAId: 'a',
      fighterBId: 'b',
    })
    if (change === 'reset') store.reset()
    else await store.fetchState('vault-2')
    const calls = vi.mocked(arenaApi.fetchState).mock.calls.length
    start.resolve()

    expect(await pending).toBe(false)
    expect(arenaApi.fetchState).toHaveBeenCalledTimes(calls)
    if (change === 'reset') expect(store.rooms.size).toBe(0)
  })
})
