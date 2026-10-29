import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { arenaApi } from '@/modules/rooms/api/arena'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const fightersUrl = '/api/v1/arena/vault/vault-1/rooms/room-1/fighters'

const selectionPayload = (overrides: Record<string, unknown> = {}) => ({
  mode: 'duel',
  fighter_a_id: 'a-1',
  fighter_b_id: null,
  fighter_c_id: null,
  fighter_d_id: null,
  opponent_keys: [],
  team_a_bot_key: null,
  team_b_bot_key: null,
  ...overrides,
})

describe('arenaApi.setFighters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(axios.post).mockResolvedValue({ data: {} })
  })

  it('posts the brawl mode with all four slots', async () => {
    await arenaApi.setFighters('vault-1', 'room-1', {
      mode: 'brawl',
      fighterAId: 'a-1',
      fighterBId: 'b-1',
      fighterCId: 'c-1',
      fighterDId: 'd-1',
    })

    expect(axios.post).toHaveBeenCalledWith(
      fightersUrl,
      selectionPayload({
        mode: 'brawl',
        fighter_b_id: 'b-1',
        fighter_c_id: 'c-1',
        fighter_d_id: 'd-1',
      })
    )
  })

  it('sends null second slots for a duel selection', async () => {
    await arenaApi.setFighters('vault-1', 'room-1', {
      mode: 'duel',
      fighterAId: 'a-1',
      fighterBId: null,
    })

    expect(axios.post).toHaveBeenCalledWith(fightersUrl, selectionPayload())
  })

  it('posts both training bot partners for a brawl', async () => {
    await arenaApi.setFighters('vault-1', 'room-1', {
      mode: 'brawl',
      fighterAId: 'a-1',
      fighterBId: 'b-1',
      teamABotKey: 'training-eyebot',
      teamBBotKey: 'training-protectron',
    })

    expect(axios.post).toHaveBeenCalledWith(
      fightersUrl,
      selectionPayload({
        mode: 'brawl',
        fighter_b_id: 'b-1',
        team_a_bot_key: 'training-eyebot',
        team_b_bot_key: 'training-protectron',
      })
    )
  })

  it('posts the hunt mode with dwellers and opponent keys', async () => {
    await arenaApi.setFighters('vault-1', 'room-1', {
      mode: 'hunt',
      fighterAId: 'a-1',
      fighterBId: null,
      fighterCId: 'c-1',
      fighterDId: null,
      opponentKeys: ['radroach-swarm', 'deathclaw'],
    })

    expect(axios.post).toHaveBeenCalledWith(
      fightersUrl,
      selectionPayload({
        mode: 'hunt',
        fighter_c_id: 'c-1',
        opponent_keys: ['radroach-swarm', 'deathclaw'],
      })
    )
  })
})

describe('arenaApi vault reads', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('gets the hunt creature catalogue', async () => {
    const catalogue = [{ key: 'radroach-swarm', name: 'Radroach swarm', power: 35, max_hp: 35 }]
    vi.mocked(axios.get).mockResolvedValue({ data: catalogue })

    await expect(arenaApi.fetchCreatures('vault-1')).resolves.toEqual(catalogue)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/arena/vault/vault-1/creatures')
  })

  it('gets the arena state', async () => {
    const state = { rooms: [], vault_id: 'vault-1' }
    vi.mocked(axios.get).mockResolvedValue({ data: state })

    await expect(arenaApi.fetchState('vault-1')).resolves.toEqual(state)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/arena/vault/vault-1/state')
  })
})

describe('arenaApi match controls', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(axios.post).mockResolvedValue({ data: undefined })
  })

  it('starts a fight with and without a selection', async () => {
    await arenaApi.startFight('vault-1', 'room-1', {
      mode: 'duel',
      fighterAId: 'a-1',
      fighterBId: null,
    })
    await arenaApi.startFight('vault-1', 'room-1')

    expect(axios.post).toHaveBeenNthCalledWith(
      1,
      '/api/v1/arena/vault/vault-1/rooms/room-1/start',
      selectionPayload()
    )
    expect(axios.post).toHaveBeenNthCalledWith(
      2,
      '/api/v1/arena/vault/vault-1/rooms/room-1/start',
      null
    )
  })

  it('stops a fight', async () => {
    await arenaApi.stopFight('vault-1', 'room-1')

    expect(axios.post).toHaveBeenCalledWith('/api/v1/arena/vault/vault-1/rooms/room-1/stop', null)
  })

  it('queues a charged skill', async () => {
    await arenaApi.queueSkill('vault-1', 'room-1', 'fighter-1')

    expect(axios.post).toHaveBeenCalledWith('/api/v1/arena/vault/vault-1/rooms/room-1/skill', {
      fighter_id: 'fighter-1',
    })
  })

  it('clears events and returns the cleared count', async () => {
    vi.mocked(axios.delete).mockResolvedValue({ data: { cleared: 3 } })

    await expect(arenaApi.clearEvents('vault-1', 'room-1')).resolves.toBe(3)
    expect(axios.delete).toHaveBeenCalledWith('/api/v1/arena/vault/vault-1/rooms/room-1/events')
  })
})
