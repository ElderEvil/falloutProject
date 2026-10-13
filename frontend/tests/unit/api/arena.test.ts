import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { arenaApi } from '@/modules/rooms/api/arena'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

describe('arenaApi.setFighters', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    ;(axios.post as ReturnType<typeof vi.fn>).mockResolvedValue({ data: {} })
  })

  it('posts the brawl mode with all four slots', async () => {
    await arenaApi.setFighters(
      'vault-1',
      'room-1',
      { mode: 'brawl', fighterAId: 'a-1', fighterBId: 'b-1', fighterCId: 'c-1', fighterDId: 'd-1' },
      'token'
    )

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/arena/vault/vault-1/rooms/room-1/fighters',
      {
        mode: 'brawl',
        fighter_a_id: 'a-1',
        fighter_b_id: 'b-1',
        fighter_c_id: 'c-1',
        fighter_d_id: 'd-1',
        opponent_keys: [],
      },
      { headers: { Authorization: 'Bearer token' } }
    )
  })

  it('sends null second slots for a duel selection', async () => {
    await arenaApi.setFighters(
      'vault-1',
      'room-1',
      { mode: 'duel', fighterAId: 'a-1', fighterBId: null },
      'token'
    )

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/arena/vault/vault-1/rooms/room-1/fighters',
      {
        mode: 'duel',
        fighter_a_id: 'a-1',
        fighter_b_id: null,
        fighter_c_id: null,
        fighter_d_id: null,
        opponent_keys: [],
      },
      { headers: { Authorization: 'Bearer token' } }
    )
  })

  it('posts the hunt mode with dwellers and opponent keys', async () => {
    await arenaApi.setFighters(
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

    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/arena/vault/vault-1/rooms/room-1/fighters',
      {
        mode: 'hunt',
        fighter_a_id: 'a-1',
        fighter_b_id: null,
        fighter_c_id: 'c-1',
        fighter_d_id: null,
        opponent_keys: ['radroach-swarm', 'deathclaw'],
      },
      { headers: { Authorization: 'Bearer token' } }
    )
  })
})

describe('arenaApi.fetchCreatures', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('gets the hunt creature catalogue for a vault', async () => {
    const catalogue = [{ key: 'radroach-swarm', name: 'Radroach swarm', power: 35, max_hp: 35 }]
    ;(axios.get as ReturnType<typeof vi.fn>).mockResolvedValue({ data: catalogue })

    const result = await arenaApi.fetchCreatures('vault-1', 'token')

    expect(result).toEqual(catalogue)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/arena/vault/vault-1/creatures', {
      headers: { Authorization: 'Bearer token' },
    })
  })
})
