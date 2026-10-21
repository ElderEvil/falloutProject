import { beforeEach, describe, expect, it, vi } from 'vitest'
import axios from '@/core/plugins/axios'
import { getWorldSnapshot } from '@/modules/map/services/mapService'

vi.mock('@/core/plugins/axios', () => ({ default: { get: vi.fn() } }))

describe('mapService.getWorldSnapshot', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lets the map store report snapshot failures with fallback context', async () => {
    vi.mocked(axios.get).mockResolvedValueOnce({ data: { width: 1, height: 1, terrain: ['wasteland'] } })

    await getWorldSnapshot('token')

    expect(axios.get).toHaveBeenCalledWith('/api/v1/map/world', {
      headers: { Authorization: 'Bearer token' },
      _skipErrorNotification: true,
    })
  })
})
