import { describe, it, expect, vi, beforeEach } from 'vitest'
import axios from '@/core/plugins/axios'
import { barbershopApi } from '@/modules/rooms/api/barbershop'

vi.mock('@/core/plugins/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

describe('barbershopApi', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('loads the status without a duplicate error toast', async () => {
    const status = { staffed: true, vault_caps: 800 }
    vi.mocked(axios.get).mockResolvedValue({ data: status })

    await expect(barbershopApi.getStatus('room-1')).resolves.toEqual(status)
    expect(axios.get).toHaveBeenCalledWith('/api/v1/rooms/room-1/barbershop', {
      _skipErrorNotification: true,
    })
  })

  it('changes a dweller appearance without a duplicate error toast', async () => {
    const response = { dweller: { id: 'dweller-1' }, remaining_caps: 700 }
    vi.mocked(axios.post).mockResolvedValue({ data: response })
    const payload = { skin_tone: 'Tan', hair_color: 'Blonde' }

    await expect(barbershopApi.changeAppearance('room-1', 'dweller-1', payload)).resolves.toEqual(
      response
    )
    expect(axios.post).toHaveBeenCalledWith(
      '/api/v1/rooms/room-1/barbershop/dwellers/dweller-1',
      payload,
      { _skipErrorNotification: true }
    )
  })
})
