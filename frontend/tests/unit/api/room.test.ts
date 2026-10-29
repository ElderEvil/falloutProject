import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { roomApi } from '@/modules/rooms/api/room'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), delete: vi.fn() },
}))

const room = { id: 'room-1', name: 'Power Generator' }

describe('roomApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads a vault room list with an explicit limit', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: [room] })

    await expect(roomApi.getByVault('vault-1', 40)).resolves.toEqual([room])
    expect(axios.get).toHaveBeenCalledWith('/api/v1/rooms/vault/vault-1/', {
      params: { limit: 40 },
    })
  })

  it('loads buildable rooms', async () => {
    vi.mocked(axios.get).mockResolvedValue({ data: [room] })

    await expect(roomApi.getBuildable('vault-1')).resolves.toEqual([room])
    expect(axios.get).toHaveBeenCalledWith('/api/v1/rooms/buildable/vault-1/')
  })

  it('builds a room', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: room })
    const payload = {
      vault_id: 'vault-1',
      room_name: 'Diner',
      coordinate_x: 3,
      coordinate_y: 1,
    }

    await expect(roomApi.build(payload)).resolves.toEqual(room)
    expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/build/', payload)
  })

  it('destroys a room', async () => {
    vi.mocked(axios.delete).mockResolvedValue({ data: undefined })

    await roomApi.destroy('room-1')
    expect(axios.delete).toHaveBeenCalledWith('/api/v1/rooms/destroy/room-1')
  })

  it('upgrades a room with an empty body', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: room })

    await expect(roomApi.upgrade('room-1')).resolves.toEqual(room)
    expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/upgrade/room-1', {})
  })

  it('splits a room with an empty body', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: [room] })

    await roomApi.remodel('room-1')
    expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/split/room-1', {})
  })

  it('merges a room with the neighbour id', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: room })

    await roomApi.remodel('room-1', 'room-2')
    expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/merge/room-1', {
      other_room_id: 'room-2',
    })
  })

  it('applies a room style', async () => {
    vi.mocked(axios.post).mockResolvedValue({ data: room })

    await roomApi.applyStyle('room-1', 'party')
    expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/style/room-1', { style: 'party' })
  })

  it('loads the grid config', async () => {
    const config = { floor_units: 28, shaft_x: 7 }
    vi.mocked(axios.get).mockResolvedValue({ data: config })

    await expect(roomApi.getGridConfig()).resolves.toEqual(config)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/rooms/grid-config/')
  })

  it('loads a rush quote and rushes a room', async () => {
    const quote = { can_rush: true, success_chance: 77 }
    const result = { outcome: 'success', caps: 120 }
    vi.mocked(axios.get).mockResolvedValue({ data: quote })
    vi.mocked(axios.post).mockResolvedValue({ data: result })

    await expect(roomApi.getRushQuote('room-1')).resolves.toEqual(quote)
    await expect(roomApi.rush('room-1')).resolves.toEqual(result)

    expect(axios.get).toHaveBeenCalledWith('/api/v1/rooms/room-1/rush')
    expect(axios.post).toHaveBeenCalledWith('/api/v1/rooms/room-1/rush', {})
  })
})
